from Errors import TransientError


class RateLimitedError(TransientError):
    def __init__(self, message: str) -> None:
        self.message = message