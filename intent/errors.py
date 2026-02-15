"""Exception hierarchy for Intent errors."""


class IntentError(Exception):
    """Base exception for all Intent errors."""

    pass


class HTTPException(IntentError):
    """HTTP request failed."""

    def __init__(
        self,
        status: int,
        message: str,
        code: str | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.code = code
        super().__init__(f"HTTP {status}: {message}")


class RateLimited(HTTPException):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        retry_after: float,
        global_limit: bool = False,
        bucket: str | None = None,
    ) -> None:
        self.retry_after = retry_after
        self.global_limit = global_limit
        self.bucket = bucket
        msg = f"Rate limited. Retry after {retry_after}s"
        if global_limit:
            msg += " (global)"
        super().__init__(429, msg, "RATE_LIMIT_EXCEEDED")


class Forbidden(HTTPException):
    """Forbidden (403)."""

    def __init__(self, message: str) -> None:
        super().__init__(403, message, "FORBIDDEN")


class NotFound(HTTPException):
    """Not found (404)."""

    def __init__(self, message: str) -> None:
        super().__init__(404, message, "NOT_FOUND")


class Unauthorized(HTTPException):
    """Unauthorized (401)."""

    def __init__(self, message: str) -> None:
        super().__init__(401, message, "UNAUTHORIZED")


class ServerError(HTTPException):
    """Server error (5xx)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(status, message, "SERVER_ERROR")
