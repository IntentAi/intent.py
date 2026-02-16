"""Type definitions for Gateway payloads."""

from typing import Any, TypedDict

from .server import ServerPayload
from .user import UserPayload


class GatewayPayload(TypedDict, total=False):
    """Base gateway message structure."""

    op: int
    d: Any
    t: str  # Event type (Dispatch only)
    s: int  # Sequence number (Dispatch only)


class IdentifyPayload(TypedDict, total=False):
    """Identify payload (op 2)."""

    token: str
    intents: int
    properties: dict[str, str]


class ReadyPayload(TypedDict):
    """Ready payload (op 3)."""

    user: UserPayload
    servers: list[ServerPayload]
    heartbeat_interval: int
