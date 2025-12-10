from api import ApiError
from api.client import HHApi


def get_resume_id(api_client: HHApi) -> str:
    try:
        resumes = api_client.my_resumes.get()
        return str(resumes.items[0].id)
    except (ApiError, KeyError, IndexError) as ex:
        raise Exception("Не могу получить идентификатор резюме") from ex
