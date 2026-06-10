"""Live integration tests against real Babelio: opt-in, gated on `BABELIO_COOKIE`.

Skipped unless `BABELIO_COOKIE` is set (a fresh `jstsToken`; `BABELIO_UA` optionally
overrides the User-Agent). Run explicitly with::

    BABELIO_COOKIE=<fresh token> uv run pytest tests/test_integration.py --no-cov

`--no-cov` because the coverage gate (`fail_under = 100`) measures only the pure
`parser`/`query` modules, which this network-driven test does not fully exercise.
"""

from __future__ import annotations

import http.client
import os
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import pytest

from calibre_babelio.client import _DEFAULT_USER_AGENT, BabelioClient, ConnectionStatus
from calibre_babelio.errors import _TOKEN_EXPIRED_MESSAGE, BabelioBlocked, CircuitBreakerOpen
from calibre_babelio.parser import parse_book_page, parse_search_results
from calibre_babelio.query import build_search_query

_COOKIE = os.environ.get("BABELIO_COOKIE")

pytestmark = pytest.mark.skipif(
    not _COOKIE,
    reason="set BABELIO_COOKIE (a fresh jstsToken) to run the live Babelio integration tests",
)

# Known book whose metadata is stable enough to assert on (mirrors the __main__ self-test).
_CHATTAM_ID = "Chattam-Autre-Monde-tome-5--Oz/401283"


class _UrllibBrowser:
    """Stdlib `BrowserProtocol` adapter standing in for Calibre's `self.browser`."""

    def __init__(self) -> None:
        self._headers: dict[str, str] = {}
        self._cookies: dict[str, str] = {}
        self._final_url = ""

    def set_user_agent(self, newval: str) -> None:
        self._headers["User-Agent"] = newval

    def set_header(self, header: str, value: str) -> None:
        self._headers[header] = value

    def set_simple_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None:
        self._cookies[name] = value

    def open(
        self,
        url: str,
        data: bytes | None = None,
        timeout: float = 30.0,
        headers: Mapping[str, str] | None = None,
    ) -> http.client.HTTPResponse:
        merged = dict(self._headers)
        if self._cookies:
            merged["Cookie"] = "; ".join(f"{name}={value}" for name, value in self._cookies.items())
        if headers:
            merged.update(headers)
        request = urllib.request.Request(url, data=data, headers=merged)
        response = urllib.request.urlopen(request, timeout=timeout)
        if not isinstance(response, http.client.HTTPResponse):  # pragma: no cover - https only
            raise TypeError("expected an HTTP response from Babelio")
        final = getattr(response, "url", None)
        self._final_url = final if isinstance(final, str) else url
        return response

    def geturl(self) -> str:
        return self._final_url


def _client(cookie: str, *, min_interval: float = 1.2, **kwargs: object) -> BabelioClient:
    user_agent = os.environ.get("BABELIO_UA") or _DEFAULT_USER_AGENT
    return BabelioClient(
        _UrllibBrowser(), cookie, user_agent, min_interval=min_interval, **kwargs  # type: ignore[arg-type]
    )


def _live_client() -> BabelioClient:
    return _client(os.environ["BABELIO_COOKIE"])


def test_identify_known_babelio_id() -> None:
    book = parse_book_page(_live_client().get_book_page(_CHATTAM_ID).body)

    assert book is not None
    assert "autre-monde" in book.title.lower()
    assert "Maxime Chattam" in book.authors
    assert book.series is not None and "autre-monde" in book.series.lower()
    assert book.series_index == 5.0


def test_identify_by_isbn_search() -> None:
    client = _live_client()
    query = build_search_query(
        title="L'élégance du hérisson",
        authors=["Muriel Barbery"],
        isbn="9782070396733",
    )
    assert query == "9782070396733"  # a valid ISBN searches by exact EAN

    hits = parse_search_results(client.search(query).body)
    assert hits, "expected at least one search hit for the hérisson ISBN"

    book = parse_book_page(client.get_book_page(hits[0].babelio_id).body)
    assert book is not None
    assert "hérisson" in book.title.lower()
    assert "Muriel Barbery" in book.authors


def test_garbled_cookie_reports_token_expired() -> None:
    result = _client("garbled-invalid-jststoken").test_connection()

    assert result.status is ConnectionStatus.TOKEN_EXPIRED


def test_repeated_blocks_trip_circuit_breaker(tmp_path: Path) -> None:
    lockfile = tmp_path / "cb.lock"
    client = _client("garbled-invalid-jststoken", lockfile_path=lockfile, block_threshold=2)

    with pytest.raises(BabelioBlocked) as first_block:
        client.search("test")
    assert str(first_block.value) == _TOKEN_EXPIRED_MESSAGE

    with pytest.raises(BabelioBlocked):
        client.search("test")  # reaches the threshold and trips the breaker
    assert lockfile.exists()

    with pytest.raises(CircuitBreakerOpen):
        client.search("test")  # circuit open; refused before any network call
