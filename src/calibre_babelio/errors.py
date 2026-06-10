"""Typed exceptions raised by the Babelio HTTP client.

These live in their own calibre-free module so the worker, plugin entry point, and config UI can
catch them without importing the HTTP/anti-bot machinery in ``client.py``.
"""

from __future__ import annotations

_TOKEN_EXPIRED_MESSAGE = (
    "Babelio jstsToken is missing or expired — copy a fresh one from your browser "
    "(DevTools → Application → Cookies → www.babelio.com → jstsToken) into plugin settings."
)


class BabelioBlocked(Exception):
    """Raised when Babelio returns HTTP 403 (how the JS challenge manifests for headless clients).

    Signals that the ``jstsToken`` cookie is missing, expired, or invalid. The message is meant to
    be surfaced verbatim to the user.
    """


class CircuitBreakerOpen(Exception):
    """Raised while the circuit breaker is open after repeated blocks.

    ``remaining`` is the approximate number of seconds until the breaker auto-recovers, so callers
    can tell the user when to retry.
    """

    def __init__(self, remaining: float) -> None:
        self.remaining = remaining
        hours = remaining / 3600.0
        super().__init__(
            f"Babelio access is temporarily blocked to avoid an IP ban; "
            f"try again in ~{hours:.1f} h."
        )
