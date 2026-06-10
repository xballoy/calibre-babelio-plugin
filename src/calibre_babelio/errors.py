"""Typed exceptions raised by the Babelio HTTP client."""

from __future__ import annotations

_TOKEN_EXPIRED_MESSAGE = (
    "Babelio jstsToken is missing or expired: copy a fresh one from your browser "
    "(DevTools → Application → Cookies → www.babelio.com → jstsToken) into plugin settings."
)


class BabelioBlocked(Exception):
    """Raised on HTTP 403: a missing, expired, or invalid `jstsToken`."""


class CircuitBreakerOpen(Exception):
    """Raised while the breaker is open; `remaining` is seconds until auto-recovery."""

    def __init__(self, remaining: float) -> None:
        self.remaining = remaining
        hours = remaining / 3600.0
        super().__init__(
            f"Babelio access is temporarily blocked to avoid an IP ban; "
            f"try again in ~{hours:.1f} h."
        )
