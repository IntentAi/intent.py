"""
intent.py - Python bot SDK for Intent

A discord.py-compatible bot framework for the Intent platform.
"""

__version__ = "0.1.0"

# Core exports
# from .client import Client
from .enums import ChannelType
from .errors import IntentError
from .utils import parse_snowflake

__all__ = [
    "__version__",
    "IntentError",
    "ChannelType",
    "parse_snowflake",
]
