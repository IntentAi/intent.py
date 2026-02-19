"""Tests for ConnectionState dispatch parsing and caching."""

from intent.http import HTTPClient
from intent.models import Channel, Message, Server
from intent.state import ConnectionState


def _make_state() -> ConnectionState:
    return ConnectionState(HTTPClient(token="test"))


def _user_payload(
    id: str = "100", username: str = "alice", display_name: str = "Alice"
) -> dict:
    return {
        "id": id,
        "username": username,
        "display_name": display_name,
        "avatar_url": None,
        "created_at": "2025-01-01T00:00:00Z",
    }


def _server_payload(id: str = "1", name: str = "Test Server") -> dict:
    return {
        "id": id,
        "name": name,
        "owner_id": "100",
        "icon_url": None,
        "description": None,
        "member_count": 10,
        "created_at": "2025-01-01T00:00:00Z",
    }


def _channel_payload(id: str = "200", server_id: str = "1") -> dict:
    return {
        "id": id,
        "server_id": server_id,
        "name": "general",
        "type": 0,
        "topic": None,
        "position": 0,
        "parent_id": None,
        "created_at": "2025-01-01T00:00:00Z",
    }


def _message_payload(id: str = "300", channel_id: str = "200") -> dict:
    return {
        "id": id,
        "channel_id": channel_id,
        "author": _user_payload(),
        "content": "hello world",
        "created_at": "2025-01-01T00:00:00Z",
        "edited_at": None,
        "webhook_id": None,
    }


class TestParseDispatch:
    """Routing raw events to the right parser."""

    def test_routes_to_parser(self) -> None:
        state = _make_state()
        result = state.parse_dispatch("MESSAGE_CREATE", _message_payload())
        assert result is not None
        assert result[0] == "message_create"

    def test_returns_none_for_unknown_event(self) -> None:
        state = _make_state()
        result = state.parse_dispatch("UNKNOWN_EVENT", {})
        assert result is None


class TestParseReady:
    """READY event populates self user and server cache."""

    def test_sets_user_and_servers(self) -> None:
        state = _make_state()
        ready = {
            "user": _user_payload(),
            "servers": [_server_payload("1"), _server_payload("2", "Second")],
            "heartbeat_interval": 30000,
        }
        result = state.parse_dispatch("READY", ready)

        assert result is not None
        event, args = result
        assert event == "ready"

        assert state.user is not None
        assert state.user.id == "100"
        assert state.user.username == "alice"

        assert len(state.servers) == 2
        assert state.get_server("1") is not None
        assert state.get_server("2") is not None

    def test_caches_self_user(self) -> None:
        state = _make_state()
        ready = {
            "user": _user_payload(),
            "servers": [],
            "heartbeat_interval": 30000,
        }
        state.parse_dispatch("READY", ready)
        assert state.get_user("100") is not None


class TestParseMessageCreate:
    """MESSAGE_CREATE builds a Message and caches the author."""

    def test_returns_message(self) -> None:
        state = _make_state()
        result = state.parse_dispatch("MESSAGE_CREATE", _message_payload())

        assert result is not None
        event, args = result
        assert event == "message_create"
        msg = args[0]
        assert isinstance(msg, Message)
        assert msg.id == "300"
        assert msg.content == "hello world"

    def test_caches_author(self) -> None:
        state = _make_state()
        state.parse_dispatch("MESSAGE_CREATE", _message_payload())
        assert state.get_user("100") is not None
        assert state.get_user("100").username == "alice"  # type: ignore[union-attr]


class TestParseMessageUpdate:
    """MESSAGE_UPDATE builds a fresh Message and updates the author cache."""

    def test_returns_updated_message(self) -> None:
        state = _make_state()
        payload = _message_payload()
        payload["content"] = "edited content"
        result = state.parse_dispatch("MESSAGE_UPDATE", payload)

        assert result is not None
        msg = result[1][0]
        assert isinstance(msg, Message)
        assert msg.content == "edited content"


class TestParseMessageDelete:
    """MESSAGE_DELETE returns raw id and channel_id."""

    def test_returns_ids(self) -> None:
        state = _make_state()
        result = state.parse_dispatch(
            "MESSAGE_DELETE", {"id": "300", "channel_id": "200"}
        )

        assert result is not None
        event, args = result
        assert event == "message_delete"
        assert args == ["300", "200"]


class TestParseServerCreate:
    """SERVER_CREATE builds a Server and caches it."""

    def test_creates_and_caches(self) -> None:
        state = _make_state()
        result = state.parse_dispatch("SERVER_CREATE", _server_payload("5", "New"))

        assert result is not None
        event, args = result
        assert event == "server_create"
        srv = args[0]
        assert isinstance(srv, Server)
        assert srv.name == "New"
        assert state.get_server("5") is srv


class TestParseChannelCreate:
    """CHANNEL_CREATE builds a Channel and caches it."""

    def test_creates_and_caches(self) -> None:
        state = _make_state()
        result = state.parse_dispatch("CHANNEL_CREATE", _channel_payload("55"))

        assert result is not None
        event, args = result
        assert event == "channel_create"
        ch = args[0]
        assert isinstance(ch, Channel)
        assert ch.id == "55"
        assert state.get_channel("55") is ch


class TestCacheLookups:
    """Cache accessor methods."""

    def test_get_nonexistent_returns_none(self) -> None:
        state = _make_state()
        assert state.get_user("nope") is None
        assert state.get_server("nope") is None
        assert state.get_channel("nope") is None


class TestClear:
    """clear() wipes all state."""

    def test_clears_everything(self) -> None:
        state = _make_state()
        ready = {
            "user": _user_payload(),
            "servers": [_server_payload()],
            "heartbeat_interval": 30000,
        }
        state.parse_dispatch("READY", ready)
        state.parse_dispatch("CHANNEL_CREATE", _channel_payload())
        state.parse_dispatch("MESSAGE_CREATE", _message_payload())

        assert state.user is not None
        assert len(state.servers) == 1

        state.clear()

        assert state.user is None
        assert len(state.servers) == 0
        assert state.get_user("100") is None
        assert state.get_channel("200") is None
