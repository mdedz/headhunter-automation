from enum import Enum
import logging
from typing import List, Tuple
from dataclasses import dataclass

from api.hh_api.schemas.negotiations import Employer, NegotiationItem, SalaryRange, Vacancy
from api.hh_api.schemas.negotiations_messages import NegotiationsMessagesItem
from operations.apply_similar.utils import get_chat

from src.api import HHApi
from src.config import Config


logger = logging.getLogger(__name__)


def should_reply_to_negotiation(
    only_invitations: bool,
    only_interviews: bool,
    selected_resume_id: str,
    negotiation: NegotiationItem,
    blacklisted: List[str],
) -> bool:
    """Check if user should reply to this msg"""
    resume = negotiation.resume
    if resume is None:
        logger.debug("Skipping negotiation, resume is none")
        return False

    if selected_resume_id != resume.id:
        logger.debug("Skipping negotiation, different resume")
        return False

    state_id = negotiation.state.id

    # skipping discard
    if state_id == "discard":
        logger.debug("Skipping negotiation, discard")
        return False

    if only_interviews and not state_id.startswith("interview"):
        logger.debug("Skipping negotiation, only invitations, state_id ", state_id)
        return False

    if only_invitations and not state_id.startswith("inv"):
        logger.debug("Skipping negotiation, only invitations, state_id ", state_id)
        return False

    nid = negotiation.id

    vacancy = negotiation.vacancy
    if vacancy is None:
        logger.debug("Skipping negotiation, vacancy isn't defined")
        return False

    employer = vacancy.employer
    if employer is None:
        logger.debug("Skipping: vacancy.employer = None")
        return False

    if employer.id in blacklisted:
        print(
            "🚫 Пропускаем заблокированного работодателя",
            employer.alternate_url,
        )
        return False

    return True


def get_message_history(api_client: HHApi, nid: str) -> Tuple[List[str], NegotiationsMessagesItem]:
    """Get formatted msg history and latest msg of first negotiation page + last page"""
    message_history: list[str] = []
    page: int = 0
    while True:
        messages_res = api_client.negotiations_messages.get(nid, per_page=3, page=page)
        items = messages_res.items

        message_history.extend(
            ("<-" if item.author.participant_type == "employer" else "->") + " " + item.text
            for item in items
            if item.text
        )
        if page + 1 >= messages_res.pages:  # skip to latest page
            last_message = items[-1]
            break

        page = messages_res.pages - 1

    return message_history, last_message


def print_negotiation_header(
    message_history: List[str],
    message_placeholders: dict[str, str],
    vacancy: Vacancy,
    salary: SalaryRange | None,
):
    print("🏢", message_placeholders["employer_name"])
    print("💼", message_placeholders["vacancy_name"])
    print("📅", vacancy.created_at)
    if salary:
        salary_from = salary.from_int or "-"
        salary_to = salary.to_int or "-"
        salary_currency = salary.currency
        print("💵 от", salary_from, "до", salary_to, salary_currency)
    print("")
    print("Последние сообщения:")
    for msg in message_history[:1] + ["..."] + message_history[-3:] if len(message_history) > 5 else message_history:
        print(msg)
    print("-" * 10)
    print()
    print("Отмена отклика: /cancel <необязательное сообщение для отказа>")
    print("Заблокировать работодателя: /ban")
    print("Написать/переписать сообщение через ИИ: /ai [Ваше сообщение или *пустая строка*]")
    print()


class NegotiationCommandType(Enum):
    BAN = "ban"
    CANCEL = "cancel"
    AI = "ai"
    MESSAGE = "message"


@dataclass
class NegotiationCommand:
    type: NegotiationCommandType
    data: dict


def parse_input(
    msg: str,
) -> NegotiationCommand:
    if msg.startswith("/ban"):
        return NegotiationCommand(type=NegotiationCommandType.BAN, data={})
    elif msg.startswith("/cancel"):
        _, decline_allowed = msg.split("/cancel", 1)
        return NegotiationCommand(type=NegotiationCommandType.CANCEL, data={"decline_allowed": decline_allowed})
    elif msg.startswith("/ai"):
        _, msg = msg.split("/ai", 1)
        return NegotiationCommand(type=NegotiationCommandType.AI, data={"msg": msg})
    else:
        return NegotiationCommand(type=NegotiationCommandType.MESSAGE, data={"msg": msg})


def process_ban(api_client: HHApi, employer: Employer, blacklisted: List[str]) -> bool:
    employer_id = employer.id
    if employer_id is None:
        logger.debug("Employer id is none")
        return False

    api_client.blacklisted_employers.put(employer_id)
    blacklisted.append(employer_id)
    print(
        "🚫 Работодатель добавлен в черный список",
        employer.alternate_url,
    )

    return True


def process_cancel(api_client: HHApi, decline_allowed: str, vacancy: Vacancy, negotiation_id: str) -> bool:
    api_client.negotiations.delete(negotiation_id, with_decline_message=decline_allowed.strip())
    print("❌ Отменили заявку", vacancy.alternate_url)

    return True


def process_ai(user_message: str) -> str:
    config = Config.load()
    chat_cfg = config.llm.chat_reply
    chat = get_chat(chat_cfg.prompts, chat_cfg.options, config.candidate)

    msg: str = chat.send_message(user_message, verify_tag_end=False)
    return msg


def process_send_msg(api_client: HHApi, msg_to_send: str, vacancy: Vacancy, nid: str) -> bool:
    api_client.negotiations_messages.post(nid, message=msg_to_send)

    print(
        "📨 Отправили сообщение для",
        vacancy.alternate_url,
    )

    return True
