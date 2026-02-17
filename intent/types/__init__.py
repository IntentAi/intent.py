"""TypedDict payload definitions for type checking."""

from .channel import ChannelPayload
from .gateway import GatewayPayload, IdentifyPayload, ReadyPayload
from .message import MessagePayload
from .server import ServerPayload
from .user import UserPayload

__all__ = (
    "ChannelPayload",
    "GatewayPayload",
    "IdentifyPayload",
    "MessagePayload",
    "ReadyPayload",
    "ServerPayload",
    "UserPayload",
)
