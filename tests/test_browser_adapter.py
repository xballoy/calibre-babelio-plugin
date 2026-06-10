from __future__ import annotations

from typing import Any

from calibre_babelio._browser import CalibreBrowserAdapter


class FakeResponse:
    def read(self) -> bytes:
        return b"body"


class FakeRequest:
    def __init__(self, url: str, data: bytes | None = None, headers: dict[str, str] | None = None):
        self.url = url
        self.data = data
        self.headers = headers


class FakeBrowser:
    def __init__(self) -> None:
        self.user_agent: str | None = None
        self.set_headers: list[tuple[str, str]] = []
        self.cookies: list[tuple[str, str, str, str]] = []
        self.opened: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def set_user_agent(self, newval: str) -> None:
        self.user_agent = newval

    def set_header(self, header: str, value: str) -> None:
        self.set_headers.append((header, value))

    def set_simple_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None:
        self.cookies.append((name, value, domain, path))

    def open(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.opened.append((args, kwargs))
        return FakeResponse()

    def geturl(self) -> str:
        return "https://final.example"


def _adapter() -> tuple[CalibreBrowserAdapter, FakeBrowser]:
    browser = FakeBrowser()
    return CalibreBrowserAdapter(browser, request_factory=FakeRequest), browser


def test_open_builds_request_with_headers_and_passes_timeout() -> None:
    adapter, browser = _adapter()
    headers = {"X-Requested-With": "XMLHttpRequest", "Referer": "https://ref"}

    response = adapter.open("https://x", b"data", 10.0, headers=headers)

    assert response.read() == b"body"
    (args, kwargs), = browser.opened
    request = args[0]
    assert isinstance(request, FakeRequest)
    assert request.url == "https://x"
    assert request.data == b"data"
    assert request.headers == headers
    assert kwargs == {"timeout": 10.0}


def test_open_without_headers_sends_empty_dict() -> None:
    adapter, browser = _adapter()

    adapter.open("https://x", None, 5.0)

    (args, _), = browser.opened
    request = args[0]
    assert isinstance(request, FakeRequest)
    assert request.headers == {}


def test_open_omits_timeout_when_none() -> None:
    adapter, browser = _adapter()

    adapter.open("https://x")

    (_, kwargs), = browser.opened
    assert kwargs == {}


def test_setup_methods_delegate_to_browser() -> None:
    adapter, browser = _adapter()

    adapter.set_user_agent("UA/1.0")
    adapter.set_header("Accept-Language", "fr-FR")
    adapter.set_simple_cookie("jstsToken", "tok", "www.babelio.com")

    assert browser.user_agent == "UA/1.0"
    assert browser.set_headers == [("Accept-Language", "fr-FR")]
    assert browser.cookies == [("jstsToken", "tok", "www.babelio.com", "/")]
    assert adapter.geturl() == "https://final.example"
