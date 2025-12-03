from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SalaryRange:
    currency: str
    from_int: int | None
    to_int: int | None
    gross: int