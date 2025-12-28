from dataclasses import dataclass
from typing import List


# GET https://api.hh.ru/negotiations/{nid}/messages
@dataclass
class Author:
    participant_type: str


@dataclass
class NegotiationsMessagesItem:
    text: str
    author: Author


@dataclass
class GetNegotiationsMessagesResponse:
    items: List[NegotiationsMessagesItem]
    pages: int
