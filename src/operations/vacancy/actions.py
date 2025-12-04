from api.client import HHApi
from utils import BlockedVacanciesDB
from api.hh_api.schemas.similar_vacancies import VacancyItem



def block_vacancy(vacancy_id: str):
    db = BlockedVacanciesDB()
    db.add(vacancy_id)