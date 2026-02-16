"""Connection state and cache management."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient


class ConnectionState:
    """
    Central state manager for the client.

    Placeholder - will be fully implemented in issue #5.
    """

    http: HTTPClient

    def __init__(self, http: HTTPClient) -> None:
        self.http = http
