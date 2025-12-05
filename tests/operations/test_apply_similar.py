import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.operations.apply_similar import Operation
import pytest
from unittest.mock import MagicMock, patch, call

from src.api.errors import LimitExceeded, ApiError
from src.api.hh_api.schemas.similar_vacancies import Employer, VacancyItem


# ---- Fixtures ----------------------------------------------------------------

@pytest.fixture
def args():
    class A:
        resume_id = "RES"
        config_path = "config.toml"
        use_ai = True
        verify_relevance = False
        message_list = None
        force_message = True
        dry_run = False
        block_irrelevant = False
        apply_interval = (0, 0)
        page_interval = (0, 0)
        param: MagicMock

    return A()


@pytest.fixture
def vacancy():
    """Simple fake vacancy."""
    v = MagicMock(spec=VacancyItem)
    v.id = "123"
    v.name = "Backend Developer"
    v.has_test = False
    v.archived = False
    v.relations = None
    v.employer = Employer
    v.employer.id = "E1"
    v.alternate_url = "https://hh.ru/vacancy/123"
    v.apply_alternate_url = "https://hh.ru/apply/123"
    v.response_letter_required = True
    return v


@pytest.fixture
def operation(args):
    return Operation()


@pytest.fixture
def api():
    api = MagicMock()
    api.negotiations.post.return_value = {"ok": True}
    api.vacancy.get.return_value = {"full": "vacancy"}
    api.me.get.return_value = {"name": "Me"}
    return api


# ---- Run Operation tests -----------------------------------------------------

@patch("src.operations.apply_similar.utils.get_chat")
@patch("src.mixins.get_resume_id")
@patch("src.config.Config.load") 
def test_run_initializes_dependencies(mock_chat, mock_resume, mock_config, operation, args, api):
    """Ensure run() builds LLMs, loads config, sets intervals, then calls _apply_similar()."""
    mock_resume.return_value = "RESUME123"
    mock_config.return_value = MagicMock()

    operation._apply_similar = MagicMock()

    operation.run(args, api)

    assert operation._apply_similar.called
    assert operation.resume_id == "RESUME123"


# ---- Apply Similar -----------------------------------------------------------

@patch("src.operations.apply_similar.utils.get_chat")
@patch("src.utils.BlockedVacanciesDB")
@patch("src.config.Config.load")
@patch("src.operations.apply_similar.utils.get_chat")
@patch("src.operations.apply_similar.random.uniform", lambda *_: 0)
@patch("src.operations.apply_similar.time.sleep", lambda _: None)
def test_apply_similar_calls_apply_vacancy(mock_chat, db_mock, mock_config, operation, args, api, vacancy):
    """Check that each vacancy is passed to `_apply_vacancy`."""
    mock_config.return_value = MagicMock()
    
    api.similar_vacancies.get.return_value = MagicMock(items=[vacancy], pages=1)

    operation._apply_vacancy = MagicMock()
    operation.run(args, api)

    operation._apply_vacancy.assert_called_once_with(vacancy)


# ---- Apply Vacancy -----------------------------------------------------------
@patch("src.config.Config.load")
def test_apply_vacancy_skips_if_archived(operation, args, api, vacancy, mock_config):
    mock_config.return_value = MagicMock()

    vacancy.archived = True

    operation.run(args, api)
    assert operation._apply_vacancy(vacancy) is False


def test_apply_vacancy_skips_if_test(operation, args, api, vacancy):
    vacancy.has_test = True
    assert operation._apply_vacancy(vacancy) is False


def test_apply_vacancy_skips_if_already_applied(operation, args, api, vacancy):
    vacancy.relations = ["already_applied"]
    assert operation._apply_vacancy(vacancy) is False


# ---- Relevance Check ---------------------------------------------------------

@patch("src.operations.apply_similar.BlockedVacanciesDB")
def test_apply_vacancy_skips_if_not_relevant(db_mock, operation, args, api, vacancy):
    args.verify_relevance = True

    operation.vacancy_relevance_llm = MagicMock()
    operation.vacancy_relevance_llm.verify.return_value = False

    assert operation._apply_vacancy(vacancy) is False
    operation.vacancy_relevance_llm.verify.assert_called_once()


# ---- Send Apply --------------------------------------------------------------

@patch("src.operations.apply_similar.random.uniform", lambda *_: 0)
@patch("src.operations.apply_similar.time.sleep", lambda _: None)
@patch("src.config.Config.load")
def test_send_apply_ai_message(operation, args, api, vacancy, mock_config):
    """Message should be generated via NegotiationsLLM."""
    mock_config.return_value = MagicMock()
    
    operation.args = args
    operation.api_client = api
    operation.resume_id = "R"

    operation.negotiations_llm = MagicMock()
    operation.negotiations_llm.get_msg.return_value = "Hello"

    operation._send_apply(vacancy)

    api.negotiations.post.assert_called_once_with({
        "resume_id": "R",
        "vacancy_id": "123",
        "message": "Hello",
    })
    

# ---- Error Handling ----------------------------------------------------------
class FakeResponse:
    status_code = 400
    text = "error"
    def json(self):
        return {}
    
@patch("src.operations.apply_similar.utils.get_chat")
@patch("src.config.Config.load")
def test_apply_vacancy_handles_limit_exceeded(mock_chat, mock_config, operation, args, api, vacancy):
    mock_chat.return_value = MagicMock()
    mock_config.return_value = MagicMock()

    operation.api_client = api
    operation.resume_id = "R"

    operation.run(args, api)
    operation._send_apply = MagicMock(side_effect=LimitExceeded(response=FakeResponse, data={})) # pyright: ignore[reportArgumentType]
    assert operation._apply_vacancy(vacancy) is False


def test_apply_vacancy_handles_api_error(operation, args, api, vacancy):
    operation.api_client = api
    operation.resume_id = "R"

    operation._send_apply = MagicMock(side_effect=ApiError(response=FakeResponse, data={})) # pyright: ignore[reportArgumentType]
    assert operation._apply_vacancy(vacancy) is False
