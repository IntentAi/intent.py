"""Type definitions for Server payloads."""

from typing import TypedDict


class ServerPayload(TypedDict):
    """Server object from API."""

    id: str
    name: str
    owner_id: str
    icon_url: str | None
    description: str | None
    member_count: int
    created_at: str
