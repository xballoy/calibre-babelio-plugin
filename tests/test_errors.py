from __future__ import annotations

from calibre_babelio.errors import (
    BabelioBlocked,
    BabelioTokenMissing,
    CircuitBreakerOpen,
    circuit_open_message,
    cookie_expired_message,
    message_for_error,
    token_missing_message,
)


def test_cookie_expired_message_names_the_token_and_settings_path() -> None:
    message = cookie_expired_message()

    assert "jstsToken" in message
    assert "Configure" in message


def test_token_missing_message_names_the_token_and_settings_path() -> None:
    message = token_missing_message()

    assert "jstsToken" in message
    assert "Configure" in message


def test_circuit_open_message_explains_the_block() -> None:
    assert "temporarily blocked" in circuit_open_message()


def test_message_for_error_maps_circuit_breaker_open() -> None:
    assert message_for_error(CircuitBreakerOpen(3600)) == circuit_open_message()


def test_message_for_error_maps_token_missing() -> None:
    assert message_for_error(BabelioTokenMissing("no token configured")) == token_missing_message()


def test_message_for_error_maps_other_babelio_blocked() -> None:
    assert message_for_error(BabelioBlocked("rejected")) == cookie_expired_message()
