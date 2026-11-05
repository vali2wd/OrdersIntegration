class AuthError(Exception):
    """"""

class PermanentError(Exception):
    """Retrying won't help: bad data, rejected by the downstream API."""

class TransientError(Exception):
    """Might work later: timeouts, 5xx, 429 after retries ran out."""

class RateLimitedError(TransientError):
    """429 from the WMS. Carries how long the server asked us to wait."""
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
