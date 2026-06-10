from __future__ import annotations

from calibre_babelio.errors import circuit_open_message, cookie_expired_message


def test_cookie_expired_message_names_the_token_and_settings_path() -> None:
    message = cookie_expired_message()

    assert "jstsToken" in message
    assert "Configure" in message


def test_circuit_open_message_explains_the_block() -> None:
    assert "temporarily blocked" in circuit_open_message()
