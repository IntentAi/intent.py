"""Tests for gateway client."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import msgpack
import pytest

from intent.errors import ConnectionClosed, GatewayError
from intent.gateway import (
    OP_DISPATCH,
    OP_HEARTBEAT,
    OP_HEARTBEAT_ACK,
    OP_IDENTIFY,
    OP_READY,
    GatewayClient,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def pack(op: int, d: Any = None, t: str | None = None, s: int | None = None) -> bytes:
    """Build a msgpack-encoded gateway payload."""
    payload: dict[str, Any] = {"op": op, "d": d}
    if t is not None:
        payload["t"] = t
    if s is not None:
        payload["s"] = s
    return msgpack.packb(payload, use_bin_type=True)


async def noop(event: str, data: Any, seq: int) -> None:
    """No-op dispatch callback."""


class MockWS:
    """Minimal WebSocket stand-in for testing. Supports async iteration and send/close.

    Accepts both bytes and str in the message list to let tests cover the
    non-binary frame guard.
    """

    def __init__(self, messages: list[bytes | str]) -> None:
        self._messages = messages
        self._index = 0
        self.send = AsyncMock()
        self.close = AsyncMock()

    def __aiter__(self) -> MockWS:
        return self

    async def __anext__(self) -> bytes | str:
        if self._index >= len(self._messages):
            raise StopAsyncIteration
        msg = self._messages[self._index]
        self._index += 1
        return msg

    async def __aenter__(self) -> MockWS:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------


class TestBackoff:
    def test_first_attempt_range(self) -> None:
        client = GatewayClient("t", noop)
        delay = client._backoff_delay(0)
        # base=1.0s, jitter ±25% → [0.75, 1.25]
        assert 0.75 <= delay <= 1.25

    def test_scales_with_attempt(self) -> None:
        client = GatewayClient("t", noop)
        d0 = client._backoff_delay(0)
        d3 = client._backoff_delay(3)
        # attempt 3 has base 8.0 vs base 1.0, so d3 should generally be larger
        assert d3 > d0

    def test_capped_at_max_step(self) -> None:
        client = GatewayClient("t", noop)
        # Both should use the 30s max step (±25% → [22.5, 37.5])
        for attempt in (5, 50, 999):
            delay = client._backoff_delay(attempt)
            assert 22.5 <= delay <= 37.5


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


class TestSend:
    async def test_raises_when_not_connected(self) -> None:
        client = GatewayClient("t", noop)
        with pytest.raises(GatewayError, match="Not connected"):
            await client.send(OP_HEARTBEAT)

    async def test_encodes_op_and_data(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        await client.send(OP_HEARTBEAT, 42)

        expected = msgpack.packb({"op": OP_HEARTBEAT, "d": 42}, use_bin_type=True)
        ws.send.assert_called_once_with(expected)

    async def test_none_data_serialized(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        await client.send(OP_HEARTBEAT)

        expected = msgpack.packb({"op": OP_HEARTBEAT, "d": None}, use_bin_type=True)
        ws.send.assert_called_once_with(expected)


# ---------------------------------------------------------------------------
# _handle()
# ---------------------------------------------------------------------------


class TestHandle:
    async def test_dispatch_invokes_callback(self) -> None:
        received: list[tuple[str, Any, int]] = []

        async def capture(event: str, data: Any, seq: int) -> None:
            received.append((event, data, seq))

        client = GatewayClient("t", capture)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        payload = {"op": OP_DISPATCH, "t": "MESSAGE_CREATE", "s": 7, "d": {"content": "hi"}}
        await client._handle(payload)  # type: ignore[arg-type]

        assert received == [("MESSAGE_CREATE", {"content": "hi"}, 7)]

    async def test_dispatch_tracks_sequence(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        await client._handle({"op": OP_DISPATCH, "t": "X", "s": 15, "d": None})  # type: ignore[arg-type]

        assert client._seq == 15

    async def test_heartbeat_ack_resets_missed_counter(self) -> None:
        client = GatewayClient("t", noop)
        client._heartbeat_missed = 3

        await client._handle({"op": OP_HEARTBEAT_ACK, "d": None})  # type: ignore[arg-type]

        assert client._heartbeat_missed == 0

    async def test_server_heartbeat_echoes_seq(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]
        client._seq = 9

        await client._handle({"op": OP_HEARTBEAT, "d": None})  # type: ignore[arg-type]

        expected = msgpack.packb({"op": OP_HEARTBEAT, "d": 9}, use_bin_type=True)
        ws.send.assert_called_once_with(expected)

    async def test_unknown_opcode_is_ignored(self) -> None:
        # Should not raise — just log at debug
        client = GatewayClient("t", noop)
        await client._handle({"op": 99, "d": None})  # type: ignore[arg-type]

    async def test_dispatch_missing_event_name_skipped(self) -> None:
        # Malformed Dispatch with no "t" field must not invoke the callback.
        received: list[Any] = []

        async def capture(event: str, data: Any, seq: int) -> None:
            received.append(event)

        client = GatewayClient("t", capture)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        # Dispatch payload with no "t" key
        await client._handle({"op": OP_DISPATCH, "s": 1, "d": {}})  # type: ignore[arg-type]

        assert received == []

    async def test_dispatch_exception_is_caught_not_propagated(self) -> None:
        # An exception inside the dispatch callback must not crash the recv loop.
        async def bad_dispatch(event: str, data: Any, seq: int) -> None:
            raise RuntimeError("callback blew up")

        client = GatewayClient("t", bad_dispatch)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        # Should not raise — exception is caught and logged.
        payload = {"op": OP_DISPATCH, "t": "MESSAGE_CREATE", "s": 1, "d": {}}
        await client._handle(payload)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _wait_for_ready()
# ---------------------------------------------------------------------------


class TestWaitForReady:
    async def test_returns_ready_payload(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([
            pack(OP_READY, {"heartbeat_interval": 30000, "user": {}, "servers": []}),
        ])
        client._ws = ws  # type: ignore[assignment]

        result = await client._wait_for_ready(ws)  # type: ignore[arg-type]

        assert result["heartbeat_interval"] == 30000

    async def test_skips_messages_before_ready(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([
            pack(OP_DISPATCH, {"foo": 1}, t="OTHER", s=1),
            pack(OP_READY, {"heartbeat_interval": 5000, "user": {}, "servers": []}),
        ])
        client._ws = ws  # type: ignore[assignment]

        result = await client._wait_for_ready(ws)  # type: ignore[arg-type]

        assert result["heartbeat_interval"] == 5000

    async def test_raises_on_connection_close_before_ready(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])  # empty = closed before Ready
        client._ws = ws  # type: ignore[assignment]

        with pytest.raises(GatewayError, match="Connection closed before Ready"):
            await client._wait_for_ready(ws)  # type: ignore[arg-type]

    async def test_ignores_non_binary_frames(self) -> None:
        # A stray text frame before Ready should be skipped; Ready still returned.
        client = GatewayClient("t", noop)
        ws = MockWS([
            "this is a text frame and should be ignored",
            pack(OP_READY, {"heartbeat_interval": 1000, "user": {}, "servers": []}),
        ])
        client._ws = ws  # type: ignore[assignment]

        result = await client._wait_for_ready(ws)  # type: ignore[arg-type]
        assert result["heartbeat_interval"] == 1000

    async def test_ignores_non_dict_msgpack_frame(self) -> None:
        # A valid msgpack frame that is not a dict (e.g., a bare int) must be skipped.
        import msgpack as mp

        client = GatewayClient("t", noop)
        ws = MockWS([
            mp.packb(42, use_bin_type=True),  # bare int — invalid gateway frame
            pack(OP_READY, {"heartbeat_interval": 2000, "user": {}, "servers": []}),
        ])
        client._ws = ws  # type: ignore[assignment]

        result = await client._wait_for_ready(ws)  # type: ignore[arg-type]
        assert result["heartbeat_interval"] == 2000


# ---------------------------------------------------------------------------
# _identify()
# ---------------------------------------------------------------------------


class TestIdentify:
    async def test_sends_identify_opcode(self) -> None:
        client = GatewayClient("secret_token", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        await client._identify()

        ws.send.assert_called_once()
        sent_bytes: bytes = ws.send.call_args[0][0]
        decoded = msgpack.unpackb(sent_bytes, raw=False)
        assert decoded["op"] == OP_IDENTIFY
        assert decoded["d"]["token"] == "secret_token"
        assert "properties" in decoded["d"]


# ---------------------------------------------------------------------------
# _heartbeat_loop()
# ---------------------------------------------------------------------------


class TestHeartbeatLoop:
    async def test_raises_after_three_missed_acks(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]
        # Counter starts at 2; on the next iteration it sends, increments to 3, then raises.
        client._heartbeat_missed = 2

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ConnectionClosed, match="Heartbeat timeout"):
                await client._heartbeat_loop()

        # heartbeat_loop no longer closes ws directly — _run() context manager does that.
        ws.close.assert_not_called()
        # One heartbeat was sent before raising.
        assert ws.send.call_count == 1

    async def test_increments_missed_and_sends_heartbeat(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]
        client._heartbeat_missed = 0
        client._seq = 10

        call_count = 0

        async def fake_sleep(delay: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await client._heartbeat_loop()

        # One heartbeat should have been sent
        assert ws.send.call_count == 1
        expected = msgpack.packb({"op": OP_HEARTBEAT, "d": 10}, use_bin_type=True)
        ws.send.assert_called_with(expected)
        assert client._heartbeat_missed == 1


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestClose:
    async def test_sets_closed_flag(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        await client.close()

        assert client._closed
        ws.close.assert_called_once()

    async def test_cancels_pending_tasks(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]

        async def long_running() -> None:
            await asyncio.sleep(9999)

        client._heartbeat_task = asyncio.create_task(long_running())
        client._recv_task = asyncio.create_task(long_running())

        # close() now awaits the cancelled tasks internally via gather, so they
        # are fully cancelled before close() returns.
        await client.close()

        assert client._heartbeat_task.cancelled()
        assert client._recv_task.cancelled()

    async def test_no_error_when_no_tasks(self) -> None:
        client = GatewayClient("t", noop)
        ws = MockWS([])
        client._ws = ws  # type: ignore[assignment]
        # No tasks set — should not raise
        await client.close()


# ---------------------------------------------------------------------------
# _recv_loop()
# ---------------------------------------------------------------------------


class TestRecvLoop:
    async def test_non_dict_msgpack_frame_skipped(self) -> None:
        import msgpack as mp

        received: list[str] = []

        async def capture(event: str, data: Any, seq: int) -> None:
            received.append(event)

        client = GatewayClient("t", capture)
        # bare int frame followed by a valid dispatch
        ws = MockWS([
            mp.packb(99, use_bin_type=True),
            pack(OP_DISPATCH, {"content": "hi"}, t="MESSAGE_CREATE", s=1),
        ])
        client._ws = ws  # type: ignore[assignment]

        await client._recv_loop(ws)  # type: ignore[arg-type]

        # Only the valid dispatch should have reached the callback.
        assert received == ["MESSAGE_CREATE"]

    async def test_non_binary_frame_skipped(self) -> None:
        received: list[str] = []

        async def capture(event: str, data: Any, seq: int) -> None:
            received.append(event)

        client = GatewayClient("t", capture)
        ws = MockWS([
            "stray text frame",
            pack(OP_DISPATCH, {"content": "hi"}, t="SERVER_CREATE", s=2),
        ])
        client._ws = ws  # type: ignore[assignment]

        await client._recv_loop(ws)  # type: ignore[arg-type]

        assert received == ["SERVER_CREATE"]
