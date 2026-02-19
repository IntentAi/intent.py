"""Connection state and cache management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from .models.channel import Channel
from .models.message import Message
from .models.server import Server
from .models.user import User
from .types.channel import ChannelPayload
from .types.message import MessagePayload
from .types.server import ServerPayload

if TYPE_CHECKING:
    from .http import HTTPClient
    from .types.gateway import ReadyPayload

log = logging.getLogger(__name__)

_ParseResult = tuple[str, list[Any]]


class ConnectionState:
    """Central state manager bridging raw gateway events and the model layer.

    Parses dispatch payloads into model objects, maintains ID-keyed caches,
    and returns (event_name, args) tuples for the Client to fire to listeners.

    Parser methods are auto-discovered via ``parse_{event_name_lower}`` so
    adding a new event is just a new method — no routing table to update.
    """

    __slots__ = ("http", "_user", "_users", "_servers", "_channels")

    def __init__(self, http: HTTPClient) -> None:
        self.http = http
        self._user: User | None = None
        self._users: dict[str, User] = {}
        self._servers: dict[str, Server] = {}
        self._channels: dict[str, Channel] = {}

    # -- public accessors --

    @property
    def user(self) -> User | None:
        return self._user

    @property
    def servers(self) -> list[Server]:
        return list(self._servers.values())

    def get_user(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def get_server(self, server_id: str) -> Server | None:
        return self._servers.get(server_id)

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._channels.get(channel_id)

    # -- dispatch router --

    def parse_dispatch(self, event: str, data: dict[str, Any]) -> _ParseResult | None:
        """Route a raw gateway dispatch to the matching parse_* method.

        Returns (event_name, args) for the Client to emit, or None if
        the event type has no parser (not an error — just unhandled).
        """
        method_name = f"parse_{event.lower()}"
        handler: Any = getattr(self, method_name, None)
        if handler is not None:
            result: _ParseResult = handler(data)
            return result
        log.debug("No parser for dispatch event %s", event)
        return None

    # -- individual parsers --

    def parse_ready(self, data: ReadyPayload) -> _ParseResult:
        # Fresh session — wipe stale state from any previous connection
        self.clear()

        self._user = User(data=data["user"], state=self)
        self._users[self._user.id] = self._user

        for raw_server in data["servers"]:
            server = Server(data=raw_server, state=self)
            self._servers[server.id] = server

        return ("ready", [self._user, self.servers])

    def parse_message_create(self, data: dict[str, Any]) -> _ParseResult:
        msg = Message(data=cast(MessagePayload, data), state=self)
        self._users[msg.author.id] = msg.author
        return ("message_create", [msg])

    def parse_message_update(self, data: dict[str, Any]) -> _ParseResult:
        msg = Message(data=cast(MessagePayload, data), state=self)
        self._users[msg.author.id] = msg.author
        return ("message_update", [msg])

    def parse_message_delete(self, data: dict[str, Any]) -> _ParseResult:
        return ("message_delete", [data["id"], data["channel_id"]])

    def parse_server_create(self, data: dict[str, Any]) -> _ParseResult:
        server = Server(data=cast(ServerPayload, data), state=self)
        self._servers[server.id] = server
        return ("server_create", [server])

    def parse_channel_create(self, data: dict[str, Any]) -> _ParseResult:
        channel = Channel(data=cast(ChannelPayload, data), state=self)
        self._channels[channel.id] = channel
        return ("channel_create", [channel])

    # -- cache management --

    def clear(self) -> None:
        """Wipe all caches. Called on full reconnect (non-resume)."""
        self._user = None
        self._users.clear()
        self._servers.clear()
        self._channels.clear()
