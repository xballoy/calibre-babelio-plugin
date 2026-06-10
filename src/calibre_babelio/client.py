"""HTTP client and anti-bot layer for Babelio."""

from __future__ import annotations

import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from .errors import _TOKEN_EXPIRED_MESSAGE, BabelioBlocked, CircuitBreakerOpen

_BASE_URL = "https://www.babelio.com"
_ACCEPT_LANGUAGE = "fr-FR,fr;q=0.9"
_COOKIE_NAME = "jstsToken"
_COOKIE_DOMAIN = "www.babelio.com"
_BODY_ENCODING = "iso-8859-1"

_DEFAULT_MIN_INTERVAL = 1.2
_DEFAULT_BLOCK_THRESHOLD = 3
_DEFAULT_COOLDOWN = 23 * 3600.0
_CIRCUIT_LOCKFILE_NAME = "calibre_babelio_circuit_breaker.lock"

_HTTP_FORBIDDEN = 403

# Amazon image URLs encode a size in a modifier between the id and extension, e.g.
# `...._SX318_BO1,204,203,200_.jpg`; dropping it yields the full-resolution original.
_AMAZON_SIZE_RE = re.compile(r"\._S[XY]\d+_.*?(\.[A-Za-z]+)$")


def _full_resolution_url(url: str) -> str:
    """Strip an Amazon image size modifier for full-res. No-op on Babelio `/couv/` URLs."""
    return _AMAZON_SIZE_RE.sub(r"\1", url)


class _Response(Protocol):
    def read(self) -> bytes: ...


class BrowserProtocol(Protocol):
    def set_user_agent(self, newval: str) -> None: ...
    def set_header(self, header: str, value: str) -> None: ...
    def set_simple_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None: ...
    def open(
        self,
        url: str,
        data: bytes | None = ...,
        timeout: float = ...,
        headers: Mapping[str, str] | None = ...,
    ) -> _Response: ...
    def geturl(self) -> str: ...


@dataclass(frozen=True, slots=True)
class FetchResult:
    body: bytes
    final_url: str


class ConnectionStatus(Enum):
    OK = "ok"
    TOKEN_EXPIRED = "token_expired"
    CIRCUIT_OPEN = "circuit_open"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    status: ConnectionStatus
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ConnectionStatus.OK


class BabelioClient:
    def __init__(
        self,
        browser: BrowserProtocol,
        cookie: str,
        user_agent: str,
        *,
        min_interval: float = _DEFAULT_MIN_INTERVAL,
        lockfile_path: Path | None = None,
        block_threshold: int = _DEFAULT_BLOCK_THRESHOLD,
        cooldown: float = _DEFAULT_COOLDOWN,
        _clock: Callable[[], float] = time.monotonic,
        _sleep: Callable[[float], None] = time.sleep,
        _now_wall: Callable[[], float] = time.time,
    ) -> None:
        self._browser = browser
        self._cookie = cookie
        self._user_agent = user_agent
        self._min_interval = min_interval
        self._lockfile_path = lockfile_path or (
            Path(tempfile.gettempdir()) / _CIRCUIT_LOCKFILE_NAME
        )
        self._block_threshold = block_threshold
        self._cooldown = cooldown
        self._clock = _clock
        self._sleep = _sleep
        self._now_wall = _now_wall
        self._last_request_at = 0.0
        self._consecutive_blocks = 0
        self._lock = threading.Lock()
        self._setup_browser()

    def _setup_browser(self) -> None:
        self._browser.set_user_agent(self._user_agent)
        self._browser.set_header("Accept-Language", _ACCEPT_LANGUAGE)
        # Host-only on www.babelio.com — not broadened to .babelio.com.
        self._browser.set_simple_cookie(_COOKIE_NAME, self._cookie, _COOKIE_DOMAIN)

    def get_book_page(self, babelio_id: str, *, timeout: float = 30.0) -> FetchResult:
        return self._fetch(f"{_BASE_URL}/livres/{babelio_id}", None, {}, timeout)

    def search(
        self,
        terms: str,
        *,
        timeout: float = 30.0,
        record_blocks: bool = True,
        check_circuit: bool = True,
    ) -> FetchResult:
        data = urllib.parse.urlencode({"Recherche": terms}, encoding=_BODY_ENCODING).encode(
            _BODY_ENCODING
        )
        return self._fetch(
            f"{_BASE_URL}/recherche",
            data,
            {},
            timeout,
            record_blocks=record_blocks,
            check_circuit=check_circuit,
        )

    def fetch_image(self, url: str, *, timeout: float = 30.0) -> bytes:
        # Goes through the configured browser (cookie + UA), so Babelio-hosted /couv/ covers
        # behind the wall download too; the host-only cookie isn't sent to external CDNs.
        return self._fetch(_full_resolution_url(url), None, {}, timeout).body

    def get_full_summary(
        self, summary_type: int, obj_id: int, referer: str, *, timeout: float = 30.0
    ) -> FetchResult:
        data = urllib.parse.urlencode(
            {"type": summary_type, "id_obj": obj_id}, encoding=_BODY_ENCODING
        ).encode(_BODY_ENCODING)
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": referer}
        return self._fetch(f"{_BASE_URL}/aj_voir_plus_a.php", data, headers, timeout)

    def test_connection(self, *, timeout: float = 10.0) -> ConnectionResult:
        try:
            self.search("test", timeout=timeout, record_blocks=False, check_circuit=False)
        except BabelioBlocked:
            return ConnectionResult(ConnectionStatus.TOKEN_EXPIRED)
        except CircuitBreakerOpen as exc:
            return ConnectionResult(ConnectionStatus.CIRCUIT_OPEN, str(exc))
        except Exception as exc:  # noqa: BLE001 — UI button must report any failure, never raise.
            return ConnectionResult(ConnectionStatus.ERROR, str(exc))
        return ConnectionResult(ConnectionStatus.OK)

    def _fetch(
        self,
        url: str,
        data: bytes | None,
        extra_headers: Mapping[str, str],
        timeout: float,
        *,
        record_blocks: bool = True,
        check_circuit: bool = True,
    ) -> FetchResult:
        if check_circuit:
            self._check_circuit()
        self._wait_rate_limit()
        try:
            response = self._browser.open(url, data, timeout, headers=extra_headers)
        except urllib.error.HTTPError as exc:
            if exc.code == _HTTP_FORBIDDEN:
                self._on_block(record_blocks)  # raises BabelioBlocked
            raise  # non-403 HTTPError surfaces unchanged
        body = response.read()
        self._on_success()
        return FetchResult(body, self._browser.geturl())

    def _wait_rate_limit(self) -> None:
        with self._lock:
            elapsed = self._clock() - self._last_request_at
            if elapsed < self._min_interval:
                self._sleep(self._min_interval - elapsed)
            self._last_request_at = self._clock()

    def _check_circuit(self) -> None:
        if not self._lockfile_path.exists():
            return
        age = self._now_wall() - self._lockfile_path.stat().st_mtime
        if age < self._cooldown:
            raise CircuitBreakerOpen(self._cooldown - age)
        self._lockfile_path.unlink(missing_ok=True)
        with self._lock:
            self._consecutive_blocks = 0

    def _on_success(self) -> None:
        with self._lock:
            self._consecutive_blocks = 0

    def _on_block(self, record_blocks: bool) -> None:
        if record_blocks:
            with self._lock:
                self._consecutive_blocks += 1
                if self._consecutive_blocks >= self._block_threshold:
                    self._lockfile_path.touch()
                    self._consecutive_blocks = 0
        raise BabelioBlocked(_TOKEN_EXPIRED_MESSAGE)
