"""Type definitions for Channel payloads."""

from typing import TypedDict


class ChannelPayload(TypedDict):
    """Channel object from API."""

    id: str
    server_id: str
    name: str
    type: int
    topic: str | None
    position: int
    parent_id: str | None
    created_at: str
