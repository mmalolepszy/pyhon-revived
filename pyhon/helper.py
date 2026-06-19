from yarl import URL

_SENSITIVE_QUERY_PARAMS = {"username", "password"}


def str_to_float(string: str | float) -> float:
    try:
        return int(string)
    except ValueError:
        return float(str(string).replace(",", "."))


def redact_url(url: URL) -> URL:
    """Mask credential-bearing query params before a URL is stored or logged."""
    if not url.query:
        return url
    redacted = {
        key: ("***" if key in _SENSITIVE_QUERY_PARAMS else value)
        for key, value in url.query.items()
    }
    return url.with_query(redacted)
