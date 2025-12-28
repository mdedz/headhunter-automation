from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.api.hh_api.schemas.me import MeResponse
from src.api.hh_api.schemas.similar_vacancies import (
    Employer,
    SimilarVacanciesResponse,
    VacancyItem,
)
from src.api.hh_api.schemas.vacancy import Experience, KeySkills, VacancyFull
from src.operations.apply_similar import Operation


class FakeLLMOptions:
    provider = "groq"
    model_name = "gpt-3"
    api_key = "test"
    temperature = 0.7
    max_tokens = 1000
    top_p = 1.0


class FakeLLMPrompts:
    system = "system prompt"


class FakeLLM:
    def __init__(self):
        self.prompts = FakeLLMPrompts()
        self.options = FakeLLMOptions()
        self.messages = SimpleNamespace(footer_msg="footer")


class FakeLLMConfig:
    def __init__(self):
        self.llm = SimpleNamespace(cover_letters=FakeLLM(), verify_relevance=FakeLLM())
        self.candidate = SimpleNamespace(info="candidate info")


@pytest.fixture
def mock_config():
    return FakeLLMConfig()


@pytest.fixture
def args() -> SimpleNamespace:
    """Mock for Namespace dataclass with all required attributes."""
    return SimpleNamespace(
        data=MagicMock,
        config_path="config_path",
        verbosity=0,
        delay=0.0,
        user_agent="user_agent",
        proxy_url="proxy_url",
        resume_id="RESUME123",
        message_list=None,
        force_message=True,
        use_ai=True,
        verify_relevance=False,
        block_irrelevant=False,
        pre_prompt="",
        apply_interval=(0.0, 0.0),
        page_interval=(0.0, 0.0),
        order_by="ORDER_BY",
        search="SEARCH",
        schedule="SCHEDULE",
        search_field=["SEARCH_FIELD"],
        experience="",
        employment=None,
        area=None,
        metro=None,
        professional_role=None,
        industry=None,
        employer_id=None,
        excluded_employer_id=None,
        currency=None,
        salary=None,
        only_with_salary=False,
        label=None,
        period=None,
        date_from=None,
        date_to=None,
        top_lat=None,
        bottom_lat=None,
        left_lng=None,
        right_lng=None,
        sort_point_lat=None,
        sort_point_lng=None,
        no_magic=False,
        premium=False,
        clusters=False,
        work_format_remote=False,
    )


@pytest.fixture
def vacancy():
    return vacancy_item()


def vacancy_item():
    """Simple fake vacancy."""
    v = MagicMock(spec=VacancyItem)
    v.id = "123"
    v.name = "Backend Developer"
    v.has_test = False
    v.archived = False
    v.relations = []
    v.employer = Employer
    v.employer.id = "E1"
    v.alternate_url = "https://hh.ru/vacancy/123"
    v.apply_alternate_url = "https://hh.ru/apply/123"
    v.response_letter_required = True
    return v


def vacancy_full_item():
    """Simple fake full vacancy."""
    employer = Employer(id="E1", name="Company X")
    key_skills = KeySkills(name="skill")
    experience = Experience(id="1", name="exp")

    v = MagicMock(spec=VacancyFull)
    v.id = "123"
    v.name = "Backend Developer"
    v.description = "desc"
    v.experience = experience
    v.key_skills = [key_skills]
    v.employer = employer

    return v


def me():
    """Simple fake Me response."""
    v = MagicMock(spec=MeResponse)
    v.id = "123"
    v.first_name = "First name"
    v.last_name = "Last name"
    v.middle_name = None
    v.email = None
    v.phone = None
    return v


def similar_vacancies_response():
    resp = MagicMock(spec=SimilarVacanciesResponse)
    _vacancy = vacancy_item()
    resp.pages = 1
    resp.items = [_vacancy]
    return resp


@pytest.fixture
def operation():
    return Operation()


@pytest.fixture
def api():
    api = MagicMock()
    api.negotiations.post.return_value = True
    api.vacancy.get.return_value = vacancy_full_item()
    api.me.get.return_value = me()
    api.similar_vacancies.get.return_value = similar_vacancies_response()
    return api


@patch("src.operations.apply_similar.Config.load", return_value=FakeLLMConfig())
@patch("src.mixins.get_resume_id")
def test_run_initializes_dependencies(mock_resume, mock_config, operation, args, api):
    """Ensure run() builds LLMs, loads config, sets intervals, then calls _apply_similar()."""
    mock_resume.return_value = "RESUME123"
    operation._apply_similar = MagicMock()

    operation.run(args, api)

    assert operation._apply_similar.called
    assert operation.resume_id == "RESUME123"


@patch("src.operations.apply_similar.get_chat")
@patch("src.operations.apply_similar.BlockedVacanciesDB")
@patch("src.operations.apply_similar.Config.load", return_value=FakeLLMConfig())
@patch("src.operations.apply_similar.random.uniform", lambda *_: 0)
@patch("src.operations.apply_similar.time.sleep", lambda _: None)
def test_apply_similar_calls_apply_vacancy(mock_chat, db_mock, mock_config, operation, args, api, vacancy):
    """Check that each vacancy is passed to `_apply_vacancy`."""
    api.similar_vacancies.get.return_value = MagicMock(items=[vacancy], pages=1)

    operation._apply_vacancy = MagicMock()
    operation.run(args, api)

    operation._apply_vacancy.assert_called_once_with(vacancy)


def test_apply_vacancy_skips_if_archived(operation, args, api, vacancy, mock_config):
    vacancy.archived = True
    assert operation._apply_vacancy(vacancy) is False


def test_apply_vacancy_skips_if_test(operation, args, api, vacancy):
    vacancy.has_test = True
    assert operation._apply_vacancy(vacancy) is False


def test_apply_vacancy_skips_if_already_applied(operation, args, api, vacancy):
    vacancy.relations = ["already_applied"]
    assert operation._apply_vacancy(vacancy) is False


@patch("src.operations.apply_similar.BlockedVacanciesDB")
def test_apply_vacancy_skips_if_not_relevant(db_mock, operation, args, api, vacancy):
    args.verify_relevance = True
    operation.args = args

    operation.vacancy_relevance_llm = MagicMock()
    operation.vacancy_relevance_llm.verify.return_value = False

    assert operation._apply_vacancy(vacancy) is False
    operation.vacancy_relevance_llm.verify.assert_called_once()


# @patch("src.operations.apply_similar.random.uniform", lambda *_: 0)
# @patch("src.operations.apply_similar.time.sleep", lambda _: None)
# @patch("src.operations.apply_similar.Config.load", return_value=FakeLLMConfig())
# def test_send_apply_ai_message(operation, args, api, vacancy, mock_config):
#     """Message should be generated via NegotiationsLLM."""
#     operation.run(args, api)
#     operation.resume_id = "R"

#     operation.negotiations_llm = MagicMock()
#     operation.negotiations_llm.get_msg.return_value = "Hello"

#     operation._apply_vacancy(vacancy)

#     api.negotiations.post.assert_called_once_with({
#         "resume_id": "R",
#         "vacancy_id": "123",
#         "message": "Hello",
#     })

# class FakeResponse:
#     status_code = 400
#     text = "error"

#     def json(self):
#         return {}

# @patch("operations.apply_similar.get_chat")
# @patch("src.operations.apply_similar.Config.load", return_value=FakeLLMConfig())
# def test_apply_vacancy_handles_limit_exceeded(mock_chat, mock_config, operation, args, api, vacancy):
#     mock_chat.return_value = MagicMock()

#     operation.api_client = api
#     operation.resume_id = "R"

#     operation.run(args, api)
#     operation._send_apply = MagicMock(
# side_effect=LimitExceeded(response=FakeResponse, data={})) # pyright: ignore[reportArgumentType]
#     assert operation._apply_vacancy(vacancy) is False


# def test_apply_vacancy_handles_api_error(operation, args, api, vacancy):
#     operation.api_client = api
#     operation.resume_id = "R"
#     operation.args = args
#     operation._send_apply =
# MagicMock(side_effect=ApiError(response=FakeResponse, data={})) # pyright: ignore[reportArgumentType]
#     # assert operation._apply_vacancy(vacancy) is False
