from utils import BlockedVacanciesDB


def block_vacancy(vacancy_id: str):
    db = BlockedVacanciesDB()
    db.add(vacancy_id)
