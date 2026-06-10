from __future__ import annotations

import threading
import time
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from calibre_babelio.client import (
    _SHARED_REQUEST_STATE,
    BabelioClient,
    ConnectionResult,
    ConnectionStatus,
    _full_resolution_url,
    _SharedRequestState,
)
from calibre_babelio.errors import BabelioBlocked, CircuitBreakerOpen

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

_COVER_URL = "https://www.babelio.com/couv/CVT_CVT_Autre-Monde-Tome-5--Oz_6607.jpg"


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body


class FakeBrowser:
    def __init__(
        self, body: bytes = b"", *, final_url: str = "", error: Exception | None = None
    ) -> None:
        self._body = body
        self._final_url = final_url
        self._error = error
        self.user_agent: str | None = None
        self.headers: dict[str, str] = {}
        self.cookies: list[tuple[str, str, str]] = []
        self.opened: list[str] = []

    def set_user_agent(self, newval: str) -> None:
        self.user_agent = newval

    def set_header(self, header: str, value: str) -> None:
        self.headers[header] = value

    def set_simple_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None:
        self.cookies.append((name, value, domain))

    def open(
        self,
        url: str,
        data: bytes | None = None,
        timeout: float = 30.0,
        headers: Mapping[str, str] | None = None,
    ) -> FakeResponse:
        self.opened.append(url)
        if self._error is not None:
            raise self._error
        return FakeResponse(self._body)

    def geturl(self) -> str:
        return self._final_url


def _client(browser: FakeBrowser, **kwargs: object) -> BabelioClient:
    kwargs.setdefault("_shared", _SharedRequestState())
    return BabelioClient(browser, "token", "UA/1.0", min_interval=0.0, **kwargs)  # type: ignore[arg-type]


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example", code, "blocked", {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://m.media-amazon.com/I/51abc._SX318_BO1,204,203,200_.jpg",
         "https://m.media-amazon.com/I/51abc.jpg"),
        ("https://m.media-amazon.com/I/51abc._SY475_.jpg",
         "https://m.media-amazon.com/I/51abc.jpg"),
        (_COVER_URL, _COVER_URL),
        ("https://www.babelio.com/couv/plain.jpg", "https://www.babelio.com/couv/plain.jpg"),
    ],
)
def test_full_resolution_url(url: str, expected: str) -> None:
    assert _full_resolution_url(url) == expected


def test_fetch_image_returns_body_and_sets_auth_headers() -> None:
    browser = FakeBrowser(b"\x89PNG-bytes", final_url=_COVER_URL)
    client = _client(browser)

    data = client.fetch_image(_COVER_URL, timeout=5.0)

    assert data == b"\x89PNG-bytes"
    assert browser.opened == [_COVER_URL]
    assert browser.user_agent == "UA/1.0"
    assert ("jstsToken", "token", "www.babelio.com") in browser.cookies


def test_fetch_image_strips_amazon_size_suffix() -> None:
    browser = FakeBrowser(b"img")
    client = _client(browser)

    client.fetch_image("https://m.media-amazon.com/I/51abc._SX318_.jpg")

    assert browser.opened == ["https://m.media-amazon.com/I/51abc.jpg"]


def test_fetch_image_403_raises_blocked() -> None:
    browser = FakeBrowser(error=_http_error(403))
    client = _client(browser)

    with pytest.raises(BabelioBlocked):
        client.fetch_image(_COVER_URL)


def test_fetch_image_non_403_http_error_propagates() -> None:
    browser = FakeBrowser(error=_http_error(500))
    client = _client(browser)

    with pytest.raises(urllib.error.HTTPError):
        client.fetch_image(_COVER_URL)


def test_fetch_image_open_circuit_blocks_request(tmp_path: Path) -> None:
    lockfile = tmp_path / "circuit.lock"
    lockfile.touch()
    browser = FakeBrowser(b"img")
    client = _client(
        browser,
        lockfile_path=lockfile,
        cooldown=3600.0,
        _now_wall=lambda: lockfile.stat().st_mtime + 60.0,
    )

    with pytest.raises(CircuitBreakerOpen):
        client.fetch_image(_COVER_URL)
    assert browser.opened == []


def test_get_full_summary_posts_to_ajax_endpoint() -> None:
    browser = FakeBrowser(b"<p>full r\xe9sum\xe9</p>", final_url="https://final")
    client = _client(browser)

    result = client.get_full_summary(1, 918135, "https://ref")

    assert result.body == b"<p>full r\xe9sum\xe9</p>"
    assert browser.opened == ["https://www.babelio.com/aj_voir_plus_a.php"]


def test_rate_limit_sleeps_when_requests_are_too_close(tmp_path: Path) -> None:
    sleeps: list[float] = []
    clock_values = iter([0.4, 1.0])
    client = BabelioClient(
        FakeBrowser(b"img"),
        "token",
        "UA/1.0",
        min_interval=1.0,
        lockfile_path=tmp_path / "circuit.lock",
        _clock=lambda: next(clock_values),
        _sleep=sleeps.append,
        _shared=_SharedRequestState(),
    )

    client.fetch_image(_COVER_URL)

    assert sleeps == [pytest.approx(0.6)]


def test_expired_circuit_lockfile_is_removed_and_request_proceeds(tmp_path: Path) -> None:
    lockfile = tmp_path / "circuit.lock"
    lockfile.touch()
    browser = FakeBrowser(b"img")
    client = _client(
        browser,
        lockfile_path=lockfile,
        cooldown=3600.0,
        _now_wall=lambda: lockfile.stat().st_mtime + 7200.0,
    )

    client.fetch_image(_COVER_URL)

    assert not lockfile.exists()
    assert browser.opened == [_COVER_URL]


def test_repeated_blocks_trip_the_circuit_breaker(tmp_path: Path) -> None:
    lockfile = tmp_path / "circuit.lock"
    browser = FakeBrowser(error=_http_error(403))
    client = _client(browser, lockfile_path=lockfile, block_threshold=2)

    for _ in range(2):
        with pytest.raises(BabelioBlocked):
            client.fetch_image(_COVER_URL)

    assert lockfile.exists()
    with pytest.raises(CircuitBreakerOpen):
        client.fetch_image(_COVER_URL)


def test_connection_ok() -> None:
    client = _client(FakeBrowser(b"<html></html>", final_url=f"{_COVER_URL}"))

    result = client.test_connection()

    assert result.status is ConnectionStatus.OK
    assert result.ok
    assert result.detail == ""


def test_connection_blocked_returns_token_expired() -> None:
    client = _client(FakeBrowser(error=_http_error(403)))

    result = client.test_connection()

    assert result.status is ConnectionStatus.TOKEN_EXPIRED
    assert not result.ok


def test_connection_unexpected_error_returns_error_status() -> None:
    client = _client(FakeBrowser(error=_http_error(500)))

    result = client.test_connection()

    assert result.status is ConnectionStatus.ERROR
    assert not result.ok
    assert result.detail  # raw exception text preserved for display


@pytest.mark.parametrize(
    ("status", "expected_ok"),
    [
        (ConnectionStatus.OK, True),
        (ConnectionStatus.TOKEN_EXPIRED, False),
        (ConnectionStatus.CIRCUIT_OPEN, False),
        (ConnectionStatus.ERROR, False),
    ],
)
def test_connection_result_ok_tracks_status(
    status: ConnectionStatus, expected_ok: bool
) -> None:
    assert ConnectionResult(status).ok is expected_ok


class RaceDetectingBrowser(FakeBrowser):
    """Test double that records whether any two `open()` calls overlap in time."""

    def __init__(self) -> None:
        super().__init__()
        self._counter_lock = threading.Lock()
        self._in_flight = 0
        self.concurrent_seen = False
        self._current_url = ""

    def open(
        self,
        url: str,
        data: bytes | None = None,
        timeout: float = 30.0,
        headers: Mapping[str, str] | None = None,
    ) -> FakeResponse:
        with self._counter_lock:
            self._in_flight += 1
            if self._in_flight > 1:
                self.concurrent_seen = True
        self.opened.append(url)
        self._current_url = url
        time.sleep(0.005)  # widen the window so an unsynchronized caller would interleave here
        with self._counter_lock:
            self._in_flight -= 1
        return FakeResponse(b"")

    def geturl(self) -> str:
        return self._current_url


def test_clients_share_request_state_by_default() -> None:
    first = BabelioClient(FakeBrowser(), "token", "UA/1.0")
    second = BabelioClient(FakeBrowser(), "token", "UA/1.0")

    assert first._shared is second._shared is _SHARED_REQUEST_STATE


class VanishingLockfile(Path):
    """Simulates the lockfile being unlinked by another thread mid-check."""

    def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
        raise FileNotFoundError(str(self))


def test_check_circuit_tolerates_lockfile_vanishing(tmp_path: Path) -> None:
    browser = FakeBrowser(b"img")
    client = _client(browser, lockfile_path=VanishingLockfile(tmp_path / "circuit.lock"))

    client.fetch_image(_COVER_URL)

    assert browser.opened == [_COVER_URL]


def test_concurrent_fetches_are_serialized() -> None:
    browser = RaceDetectingBrowser()
    client = _client(browser)
    ids = [f"Book-{n}/{n}" for n in range(8)]
    results: dict[str, str] = {}
    results_lock = threading.Lock()

    def fetch(babelio_id: str) -> None:
        result = client.get_book_page(babelio_id)
        with results_lock:
            results[babelio_id] = result.final_url

    threads = [threading.Thread(target=fetch, args=(i,)) for i in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not browser.concurrent_seen
    for babelio_id in ids:
        assert results[babelio_id].endswith(f"/livres/{babelio_id}")


def test_concurrent_fetches_across_clients_are_serialized() -> None:
    browser = RaceDetectingBrowser()
    shared = _SharedRequestState()
    clients = [_client(browser, _shared=shared) for _ in range(2)]
    ids = [f"Book-{n}/{n}" for n in range(8)]

    threads = [
        threading.Thread(target=clients[n % 2].get_book_page, args=(babelio_id,))
        for n, babelio_id in enumerate(ids)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not browser.concurrent_seen
    assert len(browser.opened) == len(ids)
