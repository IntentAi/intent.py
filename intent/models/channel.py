"""Channel model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..enums import ChannelType
from ._base import StatefulModel

if TYPE_CHECKING:
    from ..state import ConnectionState
    from ..types.channel import ChannelPayload
    from ..types.message import MessagePayload


class Channel(StatefulModel):
    """Represents an Intent channel."""

    __slots__ = (
        "id",
        "server_id",
        "name",
        "type",
        "topic",
        "position",
        "parent_id",
        "created_at",
    )

    def __init__(self, *, data: ChannelPayload, state: ConnectionState) -> None:
        super().__init__(state=state)
        self.id: str = data["id"]
        self.server_id: str = data["server_id"]
        self.name: str = data["name"]
        self.type: ChannelType = ChannelType(data["type"])
        self.topic: str | None = data.get("topic")
        self.position: int = data["position"]
        self.parent_id: str | None = data.get("parent_id")
        self.created_at: str = data["created_at"]

    def __repr__(self) -> str:
        return f"<Channel id={self.id!r} name={self.name!r} type={self.type.name}>"

    def __str__(self) -> str:
        return self.name

    async def send(self, content: str, **kwargs: Any) -> MessagePayload:
        """Send a message to this channel."""
        return cast(
            MessagePayload, await self._state.http.send_message(self.id, content=content, **kwargs)
        )

    async def fetch_messages(
        self,
        *,
        limit: int = 50,
        before: str | None = None,
        after: str | None = None,
    ) -> list[MessagePayload]:
        """Fetch messages from this channel."""
        return cast(
            list[MessagePayload],
            await self._state.http.get_messages(self.id, limit=limit, before=before, after=after),
        )

    async def fetch_message(self, message_id: str) -> MessagePayload:
        """Fetch a specific message from this channel."""
        return cast(MessagePayload, await self._state.http.get_message(self.id, message_id))

    async def edit(self, **kwargs: Any) -> ChannelPayload:
        """Edit this channel."""
        return cast(ChannelPayload, await self._state.http.edit_channel(self.id, **kwargs))

    async def delete(self) -> None:
        """Delete this channel."""
        await self._state.http.delete_channel(self.id)
