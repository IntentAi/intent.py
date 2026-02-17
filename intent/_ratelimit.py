"""Rate limit bucket tracking."""

import asyncio
import time
from collections import deque
from collections.abc import Mapping


class RateLimitBucket:
    """Tracks rate limits for a specific route bucket."""

    def __init__(self) -> None:
        self.limit: int = 999999
        self.remaining: int = 999999
        self.reset: float = 0.0
        self.bucket: str | None = None
        self._queue: deque[asyncio.Future[None]] = deque()
        self._processing = False
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    async def acquire(self) -> None:
        """Wait for rate limit availability."""
        async with self._lock:
            now = time.time()

            # Reset if time passed
            if now >= self.reset and self.reset > 0:
                self.remaining = self.limit

            # Available slot
            if self.remaining > 0:
                self.remaining -= 1
                return

        # Out of requests - queue it
        future: asyncio.Future[None] = asyncio.Future()
        self._queue.append(future)
        self._process_queue()
        await future

    def update(self, headers: Mapping[str, str]) -> None:
        """Update rate limit info from response headers."""
        if limit := headers.get("x-ratelimit-limit"):
            self.limit = int(limit)
        if remaining := headers.get("x-ratelimit-remaining"):
            self.remaining = int(remaining)
        if reset := headers.get("x-ratelimit-reset"):
            self.reset = float(reset)
        if bucket := headers.get("x-ratelimit-bucket"):
            self.bucket = bucket

    def _process_queue(self) -> None:
        """Process queued requests when bucket resets."""
        if self._processing:
            return

        self._processing = True
        self._task = asyncio.create_task(self._process_queue_async())

    async def _process_queue_async(self) -> None:
        """Async queue processing."""
        try:
            while self._queue:
                now = time.time()

                if now < self.reset:
                    delay = self.reset - now
                    await asyncio.sleep(delay)

                async with self._lock:
                    self.remaining = self.limit

                    while self._queue and self.remaining > 0:
                        future = self._queue.popleft()
                        self.remaining -= 1
                        if not future.done():
                            future.set_result(None)
        finally:
            async with self._lock:
                self._processing = False
