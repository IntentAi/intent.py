"""Message model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ._base import StatefulModel

if TYPE_CHECKING:
    from ..state import ConnectionState
    from ..types.message import MessagePayload
    from .user import User


class Message(StatefulModel):
    """Represents an Intent message."""

    __slots__ = (
        "id",
        "channel_id",
        "author",
        "content",
        "created_at",
        "edited_at",
        "webhook_id",
    )

    def __init__(self, *, data: MessagePayload, state: ConnectionState) -> None:
        super().__init__(state=state)
        self.id: str = data["id"]
        self.channel_id: str = data["channel_id"]

        # Import here to avoid circular dependency
        from .user import User
        self.author: User = User(data=data["author"], state=state)

        self.content: str = data["content"]
        self.created_at: str = data["created_at"]
        self.edited_at: str | None = data.get("edited_at")
        self.webhook_id: str | None = data.get("webhook_id")

    def __repr__(self) -> str:
        return f"<Message id={self.id!r} author={self.author!r} channel_id={self.channel_id!r}>"

    def __str__(self) -> str:
        return self.content

    @property
    def is_webhook(self) -> bool:
        """Whether this message was sent by a webhook."""
        return self.webhook_id is not None

    async def edit(self, *, content: str, **kwargs: Any) -> MessagePayload:
        """Edit this message."""
        return cast(
            MessagePayload,
            await self._state.http.edit_message(self.channel_id, self.id, content=content, **kwargs),
        )

    async def delete(self) -> None:
        """Delete this message."""
        await self._state.http.delete_message(self.channel_id, self.id)

    async def reply(self, content: str, **kwargs: Any) -> MessagePayload:
        """Reply to this message (same as sending in the channel)."""
        return cast(
            MessagePayload,
            await self._state.http.send_message(self.channel_id, content=content, **kwargs),
        )
