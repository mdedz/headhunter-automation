from dataclasses import dataclass

# GET https://api.hh.ru/me


@dataclass
class MeResponse:
    id: str
    first_name: str
    last_name: str
    middle_name: str | None
    email: str | None
    phone: str | None
