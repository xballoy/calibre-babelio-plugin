"""Pure parsing of Babelio HTML into typed domain objects."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from bs4.element import Tag as BsTag

_ENCODING = "iso-8859-1"

_TOME = re.compile(r"tome\s+(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_SERIES_LABEL = "Série"
_VOIR_PLUS = re.compile(r"voir_plus_a\(\s*'[^']*'\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_WHITESPACE = re.compile(r"\s+")

_RATING_SOURCE_MAX = 5.0
_RATING_TARGET_MAX = 10.0


@dataclass(frozen=True, slots=True)
class SearchHit:
    babelio_id: str
    title: str
    author: str | None


@dataclass(frozen=True, slots=True)
class AuthorBibliography:
    path: str
    author: str


@dataclass(frozen=True, slots=True)
class SearchPage:
    hits: tuple[SearchHit, ...]
    bibliography: AuthorBibliography | None


@dataclass(frozen=True, slots=True)
class BabelioBook:
    babelio_id: str | None
    title: str
    authors: tuple[str, ...]
    isbn: str | None
    publisher: str | None
    pubdate: date | None
    rating: float | None
    series: str | None
    series_index: float | None
    cover_url: str | None
    summary: str | None
    summary_full_type: int | None
    summary_full_id: int | None
    tags: tuple[str, ...]


def parse_search_results(html: bytes) -> SearchPage:
    soup = _soup(html)
    hits = _hits(soup.select(".rs-section .lv-item"), ".lv-title a", ".lv-author a")
    return SearchPage(hits=hits, bibliography=_author_bibliography(soup))


def parse_author_bibliography(html: bytes, author: str) -> tuple[SearchHit, ...]:
    soup = _soup(html)
    hits = _hits(soup.select(".author-biblio-grid .book-card"), ".book-card-title a", None)
    return tuple(SearchHit(hit.babelio_id, hit.title, author) for hit in hits)


def parse_book_page(html: bytes) -> BabelioBook | None:
    soup = _soup(html)
    node = _book_node(soup)
    if node is None:
        return None
    title = _text(node.get("name"))
    summary_type, summary_id = _summary_full_args(soup)
    series, series_index = _series(soup, title)

    return BabelioBook(
        babelio_id=_id_from_livres_href(_text(node.get("url"))),
        title=title,
        authors=_names(node.get("author")),
        isbn=_text(node.get("isbn")) or None,
        publisher=next(iter(_names(node.get("publisher"))), None),
        pubdate=_iso_date(node.get("datePublished")),
        rating=_rating(node.get("aggregateRating")),
        series=series,
        series_index=series_index,
        cover_url=_text(node.get("image")) or None,
        summary=_text(node.get("description")) or None,
        summary_full_type=summary_type,
        summary_full_id=summary_id,
        tags=_names(node.get("genre")),
    )


def parse_full_summary(html: bytes) -> str | None:
    """Parse the AJAX summary fragment, converting `<br>` to newlines; `None` if empty."""
    soup = _soup(html)
    for br in soup.find_all("br"):
        br.replace_with("\n")
    lines = [collapsed for raw in soup.get_text().split("\n") if (collapsed := _collapse(raw))]
    return "\n".join(lines) or None


def _book_node(soup: BeautifulSoup) -> dict[str, object] | None:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.get_text())
        except ValueError:
            continue
        for node in _jsonld_nodes(data):
            if _is_book(node):
                return node
    return None


def _jsonld_nodes(data: object) -> list[dict[str, object]]:
    if isinstance(data, list):
        return [node for item in data for node in _jsonld_nodes(item)]
    if not isinstance(data, dict):
        return []
    graph = data.get("@graph")
    if isinstance(graph, list):
        return _jsonld_nodes(graph)
    return [data]


def _is_book(node: dict[str, object]) -> bool:
    kind = node.get("@type")
    return kind == "Book" or (isinstance(kind, list) and "Book" in kind)


def _text(value: object) -> str:
    return _collapse(value) if isinstance(value, str) else ""


def _names(value: object) -> tuple[str, ...]:
    entries = value if isinstance(value, list) else [value]
    names: list[str] = []
    for entry in entries:
        name = _text(entry.get("name")) if isinstance(entry, dict) else _text(entry)
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        return None


def _rating(value: object) -> float | None:
    if not isinstance(value, dict):
        return None
    score = _number(value.get("ratingValue"))
    if score is None:
        return None
    best = _number(value.get("bestRating")) or _RATING_SOURCE_MAX
    return max(0.0, min(_RATING_TARGET_MAX, score * _RATING_TARGET_MAX / best))


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(_text(value).replace(",", "."))
    except ValueError:
        return None


def _biblio_cell(soup: BeautifulSoup, label: str) -> BsTag | None:
    for row in soup.select("table.biblio-table tr"):
        header = row.find(["th", "td"])
        cells = row.find_all("td")
        if header is not None and cells and _collapse(header.get_text(" ")) == label:
            cell: BsTag = cells[-1]
            return cell
    return None


def _series(soup: BeautifulSoup, title: str) -> tuple[str | None, float | None]:
    cell = _biblio_cell(soup, _SERIES_LABEL)
    link = cell.select_one('a[href^="/serie/"]') if cell is not None else None
    if cell is None or link is None:
        return None, None
    name = _collapse(link.get_text(" "))
    match = _TOME.search(cell.get_text(" ")) or _TOME.search(title)
    index = float(match.group(1).replace(",", ".")) if match else None
    return name or None, index


def _summary_full_args(soup: BeautifulSoup) -> tuple[int | None, int | None]:
    for tag in soup.select(".hero-summary-wrap [onclick]"):
        match = _VOIR_PLUS.search(_attr(tag, "onclick") or "")
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def _soup(html: bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser", from_encoding=_ENCODING)


def _collapse(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _attr(node: BsTag, name: str) -> str | None:
    value = node.get(name)
    return value if isinstance(value, str) else None


def _id_from_livres_href(href: str) -> str | None:
    if "/livres/" not in href:
        return None
    return href.split("/livres/", 1)[1].split("?", 1)[0].rstrip("/")


def _hits(
    items: list[BsTag], title_selector: str, author_selector: str | None
) -> tuple[SearchHit, ...]:
    hits: list[SearchHit] = []
    for item in items:
        link = item.select_one(title_selector)
        babelio_id = _id_from_livres_href(_attr(link, "href") or "") if link is not None else None
        if link is None or not babelio_id:
            continue
        author_node = item.select_one(author_selector) if author_selector else None
        author = _collapse(author_node.get_text(" ")) if author_node is not None else ""
        hits.append(SearchHit(babelio_id, _collapse(link.get_text(" ")), author or None))
    return tuple(hits)


def _author_bibliography(soup: BeautifulSoup) -> AuthorBibliography | None:
    card = soup.select_one(".rs-section.rs-author")
    link = card.select_one('a.rs-more[href*="/bibliographie"]') if card is not None else None
    heading = card.select_one("h2") if card is not None else None
    path = _attr(link, "href") if link is not None else None
    if not path or heading is None:
        return None
    return AuthorBibliography(path=path, author=_collapse(heading.get_text(" ")))
