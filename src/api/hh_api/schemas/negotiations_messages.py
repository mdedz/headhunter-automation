from dataclasses import dataclass
from typing import List, Optional

# GET https://api.hh.ru/negotiations/{nid}/messages
class Author:
    participant_type: str
    
    
class NegotiationsMessagesItem:
    text: str
    author: Author


class GetNegotiationsMessagesResponse:
    items: List[NegotiationsMessagesItem]
    pages: int 