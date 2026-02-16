"""User model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._base import StatefulModel

if TYPE_CHECKING:
    from ..state import ConnectionState
    from ..types.user import UserPayload


class User(StatefulModel):
    """Represents an Intent user."""

    __slots__ = (
        "id",
        "username",
        "display_name",
        "avatar_url",
        "created_at",
    )

    def __init__(self, *, data: UserPayload, state: ConnectionState) -> None:
        super().__init__(state=state)
        self.id: str = data["id"]
        self.username: str = data["username"]
        self.display_name: str = data["display_name"]
        self.avatar_url: str | None = data.get("avatar_url")
        self.created_at: str = data["created_at"]

    def __repr__(self) -> str:
        return f"<User id={self.id!r} username={self.username!r} display_name={self.display_name!r}>"

    def __str__(self) -> str:
        return self.display_name
