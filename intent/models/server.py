"""Server model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ._base import StatefulModel

if TYPE_CHECKING:
    from ..state import ConnectionState
    from ..types.channel import ChannelPayload
    from ..types.server import ServerPayload


class Server(StatefulModel):
    """Represents an Intent server."""

    __slots__ = (
        "id",
        "name",
        "owner_id",
        "icon_url",
        "description",
        "member_count",
        "created_at",
    )

    def __init__(self, *, data: ServerPayload, state: ConnectionState) -> None:
        super().__init__(state=state)
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.owner_id: str = data["owner_id"]
        self.icon_url: str | None = data.get("icon_url")
        self.description: str | None = data.get("description")
        self.member_count: int = data["member_count"]
        self.created_at: str = data["created_at"]

    def __repr__(self) -> str:
        return f"<Server id={self.id!r} name={self.name!r} member_count={self.member_count}>"

    def __str__(self) -> str:
        return self.name

    async def fetch_channels(self) -> list[ChannelPayload]:
        """Fetch all channels in this server."""
        return cast(list[ChannelPayload], await self._state.http.get_channels(self.id))

    async def create_channel(self, *, name: str, **kwargs: Any) -> ChannelPayload:
        """Create a channel in this server."""
        return cast(
            ChannelPayload, await self._state.http.create_channel(self.id, name=name, **kwargs)
        )

    async def edit(self, **kwargs: Any) -> ServerPayload:
        """Edit this server."""
        return cast(ServerPayload, await self._state.http.edit_server(self.id, **kwargs))

    async def delete(self) -> None:
        """Delete this server."""
        await self._state.http.delete_server(self.id)
