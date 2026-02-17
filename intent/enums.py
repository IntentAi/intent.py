"""Enumerations for Intent types."""

from enum import IntEnum


class ChannelType(IntEnum):
    """Channel type enumeration."""

    TEXT = 0
    VOICE = 1
    CATEGORY = 2
