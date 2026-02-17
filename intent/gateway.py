"""WebSocket gateway client with MessagePack protocol."""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from collections.abc import Awaitable, Callable
from typing import Any, cast

import msgpack  # type: ignore[import-untyped]
from websockets.asyncio.client import ClientConnection, connect

from .errors import ConnectionClosed, GatewayError
from .types.gateway import GatewayPayload

__all__ = ("GatewayClient",)

log = logging.getLogger(__name__)

# Reconnect backoff steps in seconds; capped at the last value
_BACKOFF_STEPS = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
_JITTER = 0.25  # ±25% of base delay

# Opcodes used in Phase 1
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_READY = 3
OP_HEARTBEAT_ACK = 11


class GatewayClient:
    """WebSocket client for the Intent gateway.

    Handles the full connection lifecycle: identify, ready, heartbeat, and event
    dispatch. Reconnects automatically on failure using exponential backoff.

    Args:
        token: Bot or user token for Identify.
        dispatch: Async callback invoked for every Dispatch event:
                  ``await dispatch(event_name, data, seq)``.
        url: Gateway WebSocket URL.
    """

    def __init__(
        self,
        token: str,
        dispatch: Callable[[str, Any, int], Awaitable[None]],
        *,
        url: str = "wss://gateway.intent.chat/",
    ) -> None:
        self.token = token
        self._dispatch = dispatch
        self._url = url

        self._ws: ClientConnection | None = None
        self._closed = False
        self._heartbeat_interval = 41.25  # overwritten by Ready payload
        self._heartbeat_missed = 0
        self._seq: int | None = None  # last received sequence number

        self._heartbeat_task: asyncio.Task[None] | None = None
        self._recv_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Connect to the gateway and reconnect on failure.

        Runs until ``close()`` is called. Reconnection uses exponential backoff
        with jitter to avoid thundering herd on server restarts.
        """
        attempt = 0
        while not self._closed:
            try:
                await self._run()
            except Exception as exc:
                if self._closed:
                    return
                log.warning("Gateway disconnected: %r", exc)

            if self._closed:
                return

            delay = self._backoff_delay(attempt)
            log.info("Reconnecting in %.2fs (attempt %d)", delay, attempt + 1)
            await asyncio.sleep(delay)
            attempt += 1

    async def close(self) -> None:
        """Shut down the connection and stop reconnecting."""
        self._closed = True

        # Cancel tasks and wait for them to finish before closing the socket.
        # Without this, a concurrent send() in a task races against ws.close().
        tasks = [t for t in (self._heartbeat_task, self._recv_task) if t and not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if self._ws is not None:
            await self._ws.close()

    async def send(self, op: int, d: Any = None) -> None:
        """Pack and transmit a gateway payload.

        Raises:
            GatewayError: If called when not connected.
        """
        if self._ws is None:
            raise GatewayError("Not connected")
        payload: dict[str, Any] = {"op": op, "d": d}
        await self._ws.send(msgpack.packb(payload, use_bin_type=True))

    # ------------------------------------------------------------------
    # Internal connection lifecycle
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Run one connection attempt from open to close."""
        async with connect(self._url) as ws:
            self._ws = ws
            self._heartbeat_missed = 0
            self._seq = None  # fresh sequence for this connection
            try:
                await self._identify()

                # Block here until the server sends Ready (op 3).
                ready_d = await self._wait_for_ready(ws)
                interval_ms = int(ready_d.get("heartbeat_interval", 41250))
                self._heartbeat_interval = interval_ms / 1000.0
                log.info("Ready (heartbeat every %.2fs)", self._heartbeat_interval)

                # Fire READY as a pseudo-event so state can populate caches.
                await self._dispatch("READY", ready_d, 0)

                # Run heartbeat and receive concurrently; stop both when either fails.
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self._recv_task = asyncio.create_task(self._recv_loop(ws))

                done, pending = await asyncio.wait(
                    {self._heartbeat_task, self._recv_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass

                # Re-raise the first exception; log any secondary one.
                first_exc: BaseException | None = None
                for task in done:
                    if not task.cancelled():
                        exc = task.exception()
                        if exc is not None:
                            if first_exc is None:
                                first_exc = exc
                            else:
                                log.debug("Secondary task exception (suppressed): %r", exc)
                if first_exc is not None:
                    raise first_exc
            finally:
                # Clear ws ref so send() fails fast during reconnect window.
                self._ws = None

    async def _wait_for_ready(self, ws: ClientConnection) -> dict[str, Any]:
        """Consume messages until Ready (op 3) arrives.

        Raises:
            GatewayError: If the connection closes before Ready, or if the
                          server sends a payload that indicates auth failure.
        """
        async for raw in ws:
            if not isinstance(raw, bytes):
                continue

            raw_payload = msgpack.unpackb(raw, raw=False)
            if not isinstance(raw_payload, dict):
                log.warning("Non-dict msgpack frame before Ready (type=%s), ignoring",
                            type(raw_payload).__name__)
                continue

            payload = cast(GatewayPayload, raw_payload)
            op = payload.get("op", -1)

            if op == OP_READY:
                d = payload.get("d")
                return d if isinstance(d, dict) else {}

            # Any other opcode before Ready is unexpected — log at warning so
            # auth failures (e.g. future op 8 Invalid Session) surface clearly.
            log.warning("Unexpected op %d before Ready, ignoring", op)

        raise GatewayError("Connection closed before Ready received")

    async def _identify(self) -> None:
        """Send the Identify payload (op 2)."""
        await self.send(
            OP_IDENTIFY,
            {
                "token": self.token,
                "properties": {"os": sys.platform, "browser": "intent.py", "device": "bot"},
            },
        )
        log.debug("Sent Identify")

    async def _heartbeat_loop(self) -> None:
        """Send heartbeats on the server-specified interval.

        Tracks missed ACKs; 3 consecutive missed ACKs = dead connection.
        Counter increments on send, resets to 0 when an ACK arrives.
        Raises ConnectionClosed rather than closing the socket directly —
        the _run() context manager handles the actual WS close on exit.
        """
        while True:
            await asyncio.sleep(self._heartbeat_interval)

            await self.send(OP_HEARTBEAT, self._seq)
            self._heartbeat_missed += 1
            log.debug("Heartbeat sent (outstanding=%d)", self._heartbeat_missed)

            if self._heartbeat_missed >= 3:
                log.warning("3 missed heartbeat ACKs — dropping connection")
                raise ConnectionClosed(None, "Heartbeat timeout")

    async def _recv_loop(self, ws: ClientConnection) -> None:
        """Receive and handle all incoming gateway frames."""
        async for raw in ws:
            if not isinstance(raw, bytes):
                log.debug("Non-binary frame received, ignoring")
                continue

            raw_payload = msgpack.unpackb(raw, raw=False)
            if not isinstance(raw_payload, dict):
                log.warning("Non-dict msgpack frame (type=%s), ignoring",
                            type(raw_payload).__name__)
                continue

            payload = cast(GatewayPayload, raw_payload)
            await self._handle(payload)

    async def _handle(self, payload: GatewayPayload) -> None:
        """Route an incoming payload by opcode."""
        op = payload.get("op", -1)

        if op == OP_DISPATCH:
            event: str | None = payload.get("t")
            if not event:
                log.warning("Received Dispatch with missing event name, skipping")
                return
            seq: int = payload.get("s") or 0
            self._seq = seq
            try:
                await self._dispatch(event, payload.get("d"), seq)
            except Exception:
                log.exception("Unhandled exception in dispatch callback for %s", event)

        elif op == OP_HEARTBEAT_ACK:
            self._heartbeat_missed = 0
            log.debug("Heartbeat ACK")

        elif op == OP_HEARTBEAT:
            # Server requesting an immediate heartbeat (rare but valid).
            await self.send(OP_HEARTBEAT, self._seq)

        else:
            log.debug("Unhandled opcode %d", op)

    def _backoff_delay(self, attempt: int) -> float:
        """Return a jittered backoff delay for the given attempt number."""
        base = _BACKOFF_STEPS[min(attempt, len(_BACKOFF_STEPS) - 1)]
        jitter = base * _JITTER
        return base + random.uniform(-jitter, jitter)
