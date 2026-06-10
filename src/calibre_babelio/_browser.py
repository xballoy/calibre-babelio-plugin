"""Adapter bridging `client.BrowserProtocol` to Calibre's mechanize `Browser`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .client import _Response


class _MechanizeBrowser(Protocol):
    def set_user_agent(self, newval: str) -> None: ...
    def set_header(self, header: str, value: str) -> None: ...
    def set_simple_cookie(self, name: str, value: str, domain: str, path: str = ...) -> None: ...
    def open(
        self, url_or_request: object, data: bytes | None = ..., timeout: float = ...
    ) -> _Response: ...
    def geturl(self) -> str: ...


class CalibreBrowserAdapter:
    def __init__(
        self,
        browser: _MechanizeBrowser,
        request_factory: Callable[..., object] | None = None,
    ) -> None:
        self._browser = browser
        self._request_factory = request_factory

    def set_user_agent(self, newval: str) -> None:
        self._browser.set_user_agent(newval)

    def set_header(self, header: str, value: str) -> None:
        self._browser.set_header(header, value)

    def set_simple_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None:
        self._browser.set_simple_cookie(name, value, domain, path)

    def open(
        self,
        url: str,
        data: bytes | None = None,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> _Response:
        factory = self._request_factory
        if factory is None:
            from mechanize import Request

            factory = Request
        # mechanize's open() has no headers kwarg, so headers ride on a Request. The browser is
        # not thread-safe; BabelioClient serializes concurrent calls (see _SharedRequestState).
        request = factory(url, data=data, headers=dict(headers or {}))
        if timeout is None:
            return self._browser.open(request)
        return self._browser.open(request, timeout=timeout)

    def geturl(self) -> str:
        return self._browser.geturl()
