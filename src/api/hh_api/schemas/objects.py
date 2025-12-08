from dataclasses import dataclass


@dataclass
class SalaryRange:
    currency: str
    from_int: int | None
    to_int: int | None
    gross: int
