"""Type definitions for Message payloads."""

from typing import TypedDict

from .user import UserPayload


class MessagePayload(TypedDict):
    """Message object from API."""

    id: str
    channel_id: str
    author: UserPayload
    content: str
    created_at: str
    edited_at: str | None
    webhook_id: str | None
