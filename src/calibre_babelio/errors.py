"""Typed exceptions and shared user-facing messages for the Babelio client."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:

    def _(text: str) -> str: ...
    def load_translations() -> None: ...


load_translations()

_TOKEN_EXPIRED_MESSAGE = (
    "Babelio jstsToken is missing or expired: copy a fresh one from your browser "
    "(DevTools → Application → Cookies → www.babelio.com → jstsToken) into plugin settings."
)


def cookie_expired_message() -> str:
    return _(
        "Babelio cookie is missing or expired: paste a fresh jstsToken in the plugin "
        "settings (Preferences → Metadata download → Babelio → Configure)."
    )


def circuit_open_message() -> str:
    return _("Babelio access is temporarily blocked to avoid an IP ban; try again later.")


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
