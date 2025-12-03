from typing import TypedDict, Literal


class AccessToken(TypedDict):
    access_token: str | None
    refresh_token: str | None
    access_expires_at: int | None
    token_type: Literal["bearer"]

