from __future__ import annotations

import http.client
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class UrllibBrowser:
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
        if not isinstance(response, http.client.HTTPResponse):
            raise TypeError("expected an HTTP response from Babelio")
        final = getattr(response, "url", None)
        self._final_url = final if isinstance(final, str) else url
        return response

    def geturl(self) -> str:
        return self._final_url
