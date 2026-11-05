class TransientError(Exception):
    """Might work later: timeouts, 5xx, 429 after retries ran out."""