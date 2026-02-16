"""HTTP client for Intent REST API."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, cast

import aiohttp

from ._ratelimit import RateLimitBucket
from ._route import Route
from .errors import Forbidden, HTTPException, NotFound, RateLimited, ServerError, Unauthorized

__all__ = ("HTTPClient",)

log = logging.getLogger(__name__)


class HTTPClient:
    """Async HTTP client with rate limiting for Intent REST API."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.intent.chat/v1",
        *,
        max_retries: int = 5,
    ) -> None:
        self.token = token
        self.base_url = base_url
        self.max_retries = max_retries

        self._session: aiohttp.ClientSession | None = None
        self._buckets: dict[str, RateLimitBucket] = {}
        self._global_lock = asyncio.Lock()
        self._global_over: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_bucket(self, route: Route) -> RateLimitBucket:
        """Get or create rate limit bucket for route."""
        key = route.bucket_key
        if key not in self._buckets:
            self._buckets[key] = RateLimitBucket()
        return self._buckets[key]

    async def request(
        self,
        route: Route,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Make HTTP request with rate limiting and retry logic.

        Handles:
        - Per-route rate limiting via buckets
        - Global rate limit gate
        - 429 retry using Retry-After header
        - 5xx exponential backoff (max 5 retries)
        """
        bucket = self._get_bucket(route)
        session = await self._get_session()

        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        for attempt in range(self.max_retries):
            # Wait for global rate limit
            async with self._global_lock:
                if self._global_over > 0:
                    delay = self._global_over - asyncio.get_event_loop().time()
                    if delay > 0:
                        log.warning(f"Global rate limit - waiting {delay:.2f}s")
                        await asyncio.sleep(delay)
                    self._global_over = 0.0

            # Wait for per-route bucket
            await bucket.acquire()

            try:
                url = route.url(self.base_url)
                async with session.request(
                    route.method, url, json=json, params=params, headers=headers
                ) as resp:
                    # Update bucket from headers
                    bucket.update(dict(resp.headers))

                    # Success responses
                    if 200 <= resp.status < 300:
                        if resp.status == 204:
                            return None
                        return await resp.json()

                    # Rate limited
                    if resp.status == 429:
                        data = await resp.json()
                        retry_after = data.get("retry_after", 1.0)
                        is_global = data.get("global", False)

                        if is_global:
                            async with self._global_lock:
                                self._global_over = (
                                    asyncio.get_event_loop().time() + retry_after
                                )
                            log.warning(f"Global rate limit hit - retry after {retry_after}s")
                        else:
                            log.warning(
                                f"Route {route.bucket_key} rate limited - retry after {retry_after}s"
                            )

                        # Last attempt - raise instead of retry
                        if attempt == self.max_retries - 1:
                            raise RateLimited(
                                retry_after, global_limit=is_global, bucket=bucket.bucket
                            )

                        await asyncio.sleep(retry_after)
                        continue

                    # Client errors
                    text = await resp.text()
                    if resp.status == 401:
                        raise Unauthorized(text)
                    if resp.status == 403:
                        raise Forbidden(text)
                    if resp.status == 404:
                        raise NotFound(text)

                    # Server errors - retry with backoff
                    if 500 <= resp.status < 600:
                        if attempt == self.max_retries - 1:
                            raise ServerError(resp.status, text)

                        # Exponential backoff with jitter
                        delay = (2**attempt) + random.uniform(0, 1)
                        log.warning(
                            f"Server error {resp.status} - retry {attempt + 1}/{self.max_retries} after {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Other errors
                    raise HTTPException(resp.status, text)

            except aiohttp.ClientError as e:
                # Network errors - retry with backoff
                if attempt == self.max_retries - 1:
                    raise HTTPException(0, f"Network error: {e}")

                delay = (2**attempt) + random.uniform(0, 1)
                log.warning(f"Network error - retry {attempt + 1}/{self.max_retries} after {delay:.2f}s")
                await asyncio.sleep(delay)
                continue

        raise HTTPException(0, "Max retries exceeded")

    # ==================== Servers ====================

    async def get_servers(self) -> list[dict[str, Any]]:
        """Get all servers the current user is in."""
        return cast(list[dict[str, Any]], await self.request(Route("GET", "/servers")))

    async def create_server(self, *, name: str, **kwargs: Any) -> dict[str, Any]:
        """Create a new server."""
        payload = {"name": name, **kwargs}
        return cast(dict[str, Any], await self.request(Route("POST", "/servers"), json=payload))

    async def get_server(self, server_id: str) -> dict[str, Any]:
        """Get a server by ID."""
        return cast(dict[str, Any], await self.request(Route("GET", f"/servers/{server_id}")))

    async def edit_server(self, server_id: str, **kwargs: Any) -> dict[str, Any]:
        """Edit a server."""
        return cast(
            dict[str, Any], await self.request(Route("PATCH", f"/servers/{server_id}"), json=kwargs)
        )

    async def delete_server(self, server_id: str) -> None:
        """Delete a server."""
        await self.request(Route("DELETE", f"/servers/{server_id}"))

    # ==================== Channels ====================

    async def get_channels(self, server_id: str) -> list[dict[str, Any]]:
        """Get all channels in a server."""
        return cast(
            list[dict[str, Any]], await self.request(Route("GET", f"/servers/{server_id}/channels"))
        )

    async def create_channel(
        self, server_id: str, *, name: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Create a channel in a server."""
        payload = {"name": name, **kwargs}
        return cast(
            dict[str, Any],
            await self.request(Route("POST", f"/servers/{server_id}/channels"), json=payload),
        )

    async def get_channel(self, channel_id: str) -> dict[str, Any]:
        """Get a channel by ID."""
        return cast(dict[str, Any], await self.request(Route("GET", f"/channels/{channel_id}")))

    async def edit_channel(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        """Edit a channel."""
        return cast(
            dict[str, Any],
            await self.request(Route("PATCH", f"/channels/{channel_id}"), json=kwargs),
        )

    async def delete_channel(self, channel_id: str) -> None:
        """Delete a channel."""
        await self.request(Route("DELETE", f"/channels/{channel_id}"))

    # ==================== Messages ====================

    async def get_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get messages from a channel."""
        params: dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        return cast(
            list[dict[str, Any]],
            await self.request(Route("GET", f"/channels/{channel_id}/messages"), params=params),
        )

    async def get_message(self, channel_id: str, message_id: str) -> dict[str, Any]:
        """Get a single message."""
        return cast(
            dict[str, Any],
            await self.request(Route("GET", f"/channels/{channel_id}/messages/{message_id}")),
        )

    async def send_message(self, channel_id: str, *, content: str, **kwargs: Any) -> dict[str, Any]:
        """Send a message to a channel."""
        payload = {"content": content, **kwargs}
        return cast(
            dict[str, Any],
            await self.request(Route("POST", f"/channels/{channel_id}/messages"), json=payload),
        )

    async def edit_message(
        self, channel_id: str, message_id: str, *, content: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Edit a message."""
        payload = {"content": content, **kwargs}
        return cast(
            dict[str, Any],
            await self.request(
                Route("PATCH", f"/channels/{channel_id}/messages/{message_id}"), json=payload
            ),
        )

    async def delete_message(self, channel_id: str, message_id: str) -> None:
        """Delete a message."""
        await self.request(Route("DELETE", f"/channels/{channel_id}/messages/{message_id}"))
