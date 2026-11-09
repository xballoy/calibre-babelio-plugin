from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .parser import SearchHit, parse_author_bibliography, parse_search_results

if TYPE_CHECKING:
    from .client import FetchResult


class SearchClientProtocol(Protocol):
    def search(self, terms: str) -> FetchResult: ...
    def get_author_bibliography(self, path: str) -> FetchResult: ...


def search_books(client: SearchClientProtocol, query: str) -> tuple[SearchHit, ...]:
    page = parse_search_results(client.search(query).body)
    if page.hits or page.bibliography is None:
        return page.hits
    bibliography = client.get_author_bibliography(page.bibliography.path)
    return parse_author_bibliography(bibliography.body, page.bibliography.author)
