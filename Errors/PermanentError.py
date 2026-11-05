class PermanentError(Exception):
    """Retrying won't help: bad data, rejected by the downstream API."""