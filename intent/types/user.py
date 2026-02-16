"""Type definitions for User payloads."""

from typing import TypedDict


class UserPayload(TypedDict):
    """User object from API."""

    id: str
    username: str
    display_name: str
    avatar_url: str | None
    created_at: str
