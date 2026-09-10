class AIAnalysisError(Exception):
    """Base error for anything that goes wrong asking an AIProductAnalyzer
    to analyze one image. Never carries API keys or raw provider
    exceptions in its message -- callers may show `str(exc)` to a client
    without leaking internals.
    """


class AIServiceUnavailableError(AIAnalysisError):
    """The provider was unreachable/overloaded/timed out after retries were
    exhausted. Distinct from AIInvalidResponseError so callers can decide
    whether retrying the whole job later is worthwhile."""


class AIInvalidResponseError(AIAnalysisError):
    """The provider responded, but its output was not valid JSON, did not
    match the expected schema, or otherwise cannot be trusted (e.g. an
    out-of-range bounding box)."""
