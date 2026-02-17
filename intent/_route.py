"""Route class for HTTP requests."""

import re
from typing import Literal

HTTPMethod = Literal["GET", "POST", "PATCH", "DELETE", "PUT"]


class Route:
    """Represents an API route with rate limit bucket tracking."""

    def __init__(self, method: HTTPMethod, path: str) -> None:
        self.method = method
        self.path = path
        self.bucket_key = self._generate_bucket_key()

    def _generate_bucket_key(self) -> str:
        """
        Generate bucket key for rate limiting.

        Major parameters (server_id, channel_id, webhook_id) create separate buckets.
        Minor parameters (message_id, user_id) are normalized to share buckets.
        """
        # Only normalize minor parameters - keep major params (server_id, channel_id) intact
        normalized = re.sub(r"/messages/\d+", "/messages/:id", self.path)
        return f"{self.method}:{normalized}"

    def url(self, base: str) -> str:
        """Build full URL with base."""
        return f"{base}{self.path}"
