from dacite import from_dict, Config

from api.hh_api.base import BaseEndpoint
from api.hh_api.schemas.blacklisted_employers import GetBlacklistedEmployersResponse, PutBlacklistedEmployersResponse
from api.hh_api.schemas.me import MeResponse
from api.hh_api.schemas.my_resumes import GetResumesResponse
from api.hh_api.schemas.negotiations import DeleteNegotiationsResponse, GetNegotiationsListResponse
from api.hh_api.schemas.negotiations_messages import GetNegotiationsMessagesResponse
from api.hh_api.schemas.similar_vacancies import SimilarVacanciesResponse
from api.hh_api.schemas.vacancy import VacancyFull
from api.hh_api.schemas.resume_info import ResumeInfoResponse


class BlacklistedEmployers(BaseEndpoint):
    """
    GET: https://api.hh.ru/employers/blacklisted
    PUT: https://api.hh.ru/vacancies/blacklisted/{vacancy_id}
    """

    def get(self, *args, **kwargs) -> GetBlacklistedEmployersResponse:
        data = self.client.get("/employers/blacklisted", *args, **kwargs)

        return from_dict(GetBlacklistedEmployersResponse, data)

    def put(self, employer_id: str, *args, **kwargs) -> PutBlacklistedEmployersResponse:
        data = self.client.put(f"/employers/blacklisted/{employer_id}", *args, **kwargs)

        return from_dict(PutBlacklistedEmployersResponse, data)


class Negotiations(BaseEndpoint):
    """
    GET: https://api.hh.ru/negotiations
    POST: https://api.hh.ru/negotiations
    DELETE: https://api.hh.ru/negotiations/active/{nid}
    """

    def get(self, *args, **kwargs) -> GetNegotiationsListResponse:
        data = self.client.get("/negotiations", *args, **kwargs)

        return from_dict(GetNegotiationsListResponse, data)

    def post(self, *args, **kwargs) -> bool:
        data = self.client.post("/negotiations/", *args, **kwargs)

        return data == []

    def delete(self, item_id: str, *args, **kwargs) -> bool:
        data = self.client.delete(f"/negotiations/active/{item_id}", *args, **kwargs)
        return data == {}


class NegotiationsMessages(BaseEndpoint):
    """
    GET: https://api.hh.ru/negotiations/{nid}/messages
    POST: https://api.hh.ru/negotiations/{nid}/messages
    """

    def get(self, nid: str, *args, **kwargs) -> GetNegotiationsMessagesResponse:
        data = self.client.get(f"/negotiations/{nid}/messages", *args, **kwargs)

        return from_dict(GetNegotiationsMessagesResponse, data)

    def post(self, nid: str, *args, **kwargs) -> bool:
        """this method is supposed to return a huuuge response but we don't need to define it yet so let's leave it blank for now"""
        # TODO: One day, I'll define the response
        _ = self.client.post(f"/negotiations/{nid}/messages", *args, **kwargs)

        return True


class MyResumes(BaseEndpoint):
    """
    GET: https://api.hh.ru/resumes/mine
    """

    def get(self, *args, **kwargs) -> GetResumesResponse:
        data = self.client.get("/resumes/mine", *args, **kwargs)

        return from_dict(GetResumesResponse, data)


class ResumeInfo(BaseEndpoint):
    """
    GET: https://api.hh.ru/resumes/{resume_id}
    """

    def get(self, resume_id: str, *args, **kwargs) -> ResumeInfoResponse:
        data = self.client.get(f"/resumes/{resume_id}", *args, **kwargs)
        print("data", data)
        return from_dict(ResumeInfoResponse, data, config=Config(strict=False))


class PublishResume(BaseEndpoint):
    """
    POST: https://api.hh.ru/resumes/{resume_id}/publish
    """

    def post(self, resume_id: str, *args, **kwargs) -> bool:
        data = self.client.post(f"/resumes/{resume_id}/publish", *args, **kwargs)

        return data == []


class Me(BaseEndpoint):
    """
    GET: https://api.hh.ru/me
    """

    def get(self, *args, **kwargs) -> MeResponse:
        data = self.client.get("/me", *args, **kwargs)

        return from_dict(MeResponse, data)


class SimilarVacancies(BaseEndpoint):
    """
    GET: https://api.hh.ru/resumes/{resume_id}/similar_vacancies
    """

    def get(self, resume_id: str, *args, **kwargs) -> SimilarVacanciesResponse:
        data = self.client.get(f"/resumes/{resume_id}/similar_vacancies", *args, **kwargs)

        return from_dict(SimilarVacanciesResponse, data)


class Vacancy(BaseEndpoint):
    """
    GET: https://api.hh.ru/vacancies/{vacancy_id}
    """

    def get(self, vacancy_id: str, *args, **kwargs) -> VacancyFull:
        data = self.client.get(f"/vacancies/{vacancy_id}", *args, **kwargs)

        return from_dict(VacancyFull, data)
