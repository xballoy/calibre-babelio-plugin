from __future__ import annotations

from pathlib import Path

from calibre_babelio.client import FetchResult
from calibre_babelio.parser import SearchHit
from calibre_babelio.search import search_books

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeClient:
    def __init__(self, search_page: str | bytes, bibliography_page: str | None = None) -> None:
        self._search_page = search_page
        self._bibliography_page = bibliography_page
        self.searches: list[str] = []
        self.bibliographies: list[str] = []

    def search(self, terms: str) -> FetchResult:
        self.searches.append(terms)
        page = self._search_page
        body = page if isinstance(page, bytes) else _load(page)
        return FetchResult(body, "https://www.babelio.com/recherche")

    def get_author_bibliography(self, path: str) -> FetchResult:
        self.bibliographies.append(path)
        assert self._bibliography_page is not None
        return FetchResult(_load(self._bibliography_page), f"https://www.babelio.com{path}")


def test_book_results_are_returned_without_extra_requests() -> None:
    client = FakeClient("search_by_isbn.html")

    hits = search_books(client, "9782226244338")

    assert hits == (
        SearchHit(
            "Chattam-Autre-Monde-tome-5--Oz/401283", "Autre-Monde, tome 5 : Oz", "Maxime Chattam"
        ),
    )
    assert client.searches == ["9782226244338"]
    assert client.bibliographies == []


def test_author_only_result_falls_back_to_the_first_bibliography_page() -> None:
    client = FakeClient("search_by_author.html", "author_bibliography_chattam.html")

    hits = search_books(client, "Maxime Chattam")

    assert client.bibliographies == ["/auteur/Maxime-Chattam/2038/bibliographie"]
    assert len(hits) == 20
    assert hits[0] == SearchHit("Chattam-Lme-du-mal/899191", "L'Âme du mal", "Maxime Chattam")


def test_empty_search_returns_nothing_without_extra_requests() -> None:
    client = FakeClient("search_no_results.html")

    assert search_books(client, "zxqwvbnmlkjhgfdsapoiuyt") == ()
    assert client.bibliographies == []


def test_book_results_win_over_an_author_card() -> None:
    page = (
        b'<section class="rs-section rs-author"><h2>Maxime Chattam</h2>'
        b'<a class="rs-more" href="/auteur/Maxime-Chattam/2038/bibliographie">Bibliographie</a>'
        b"</section>"
        b'<section class="rs-section"><div class="lv-item">'
        b'<p class="lv-title"><a href="/livres/Chattam-Oz/401283">Oz</a></p>'
        b'<p class="lv-author"><a href="/auteur/Maxime-Chattam/2038">Maxime Chattam</a></p>'
        b"</div></section>"
    )
    client = FakeClient(page)

    assert search_books(client, "Chattam") == (
        SearchHit("Chattam-Oz/401283", "Oz", "Maxime Chattam"),
    )
    assert client.bibliographies == []
