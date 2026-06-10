"""Pure parsing of Babelio HTML into typed domain objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from bs4.element import Tag as BsTag

_ENCODING = "iso-8859-1"

_ISBN13 = re.compile(r"(?<!\d)(\d{13})(?!\d)")
_DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_TOME = re.compile(r"tome\s+(\d+)", re.IGNORECASE)
_VOIR_PLUS = re.compile(r"voir_plus_a\(\s*'[^']*'\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_TAG_CATEGORY = re.compile(r"^tc_(\d+)$")
_TAG_RELEVANCE = re.compile(r"^tag_t(\d+)$")
# Editorial roles appear as a trailing parenthetical, e.g. "Claude Schopp (Éditeur scientifique)".
# Anchor to the end so a name with a legitimate mid-string parenthetical is not dropped.
_EDITORIAL_ROLE = re.compile(r"\([^)]*\)\s*$")
_WHITESPACE = re.compile(r"\s+")
_TITLE_SUFFIX = " - Babelio"

_RATING_SOURCE_MAX = 5.0  # Babelio rates out of 5
_RATING_TARGET_MAX = 10.0  # Calibre expects ratings on a 0–10 scale


class TagCategory(Enum):
    GENRE = "genre"
    THEME = "theme"
    PLACE = "place"
    PERIOD = "period"


_TAG_CATEGORY_BY_INDEX = {
    0: TagCategory.GENRE,
    1: TagCategory.THEME,
    2: TagCategory.PLACE,
    3: TagCategory.PERIOD,
}


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    category: TagCategory
    relevance: int


@dataclass(frozen=True, slots=True)
class SearchHit:
    babelio_id: str
    title: str
    author: str | None


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
    tags: tuple[Tag, ...]


def parse_search_results(html: bytes) -> list[SearchHit]:
    """Parse hits from the `.cr_meta` rows, falling back to the `ul.livres_mozaique` mosaic."""
    soup = _soup(html)

    metas = soup.select(".cr_meta")
    if metas:
        return [hit for meta in metas if (hit := _parse_cr_meta(meta)) is not None]

    return [
        hit
        for item in soup.select("ul.livres_mozaique li.item")
        if (hit := _parse_mosaic_item(item)) is not None
    ]


def parse_book_page(html: bytes) -> BabelioBook | None:
    """Parse a book page, or `None` when neither a canonical `/livres/` link nor an
    edition block is present (an unknown URL redirected to the homepage)."""
    soup = _soup(html)
    babelio_id = _parse_babelio_id(soup)
    refs = soup.select_one(".livre_refs.grey_light")
    if babelio_id is None and refs is None:
        return None
    refs_text = refs.get_text(" ", strip=True) if refs is not None else ""
    title = _parse_title(soup)
    summary_type, summary_id = _parse_summary_full_args(soup)

    return BabelioBook(
        babelio_id=babelio_id,
        title=title,
        authors=_parse_authors(soup),
        isbn=_parse_isbn(refs_text),
        publisher=_parse_publisher(refs),
        pubdate=_parse_pubdate(refs_text),
        rating=_parse_rating(soup),
        series=_parse_series(soup),
        series_index=_parse_series_index(title),
        cover_url=_parse_cover_url(soup),
        summary=_parse_summary(soup),
        summary_full_type=summary_type,
        summary_full_id=summary_id,
        tags=_parse_tags(soup),
    )


def parse_full_summary(html: bytes) -> str | None:
    """Parse the AJAX summary fragment, converting `<br>` to newlines; `None` if empty."""
    soup = _soup(html)
    for br in soup.find_all("br"):
        br.replace_with("\n")
    lines = [collapsed for raw in soup.get_text().split("\n") if (collapsed := _collapse(raw))]
    return "\n".join(lines) or None


def _soup(html: bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser", from_encoding=_ENCODING)


def _collapse(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _attr(node: BsTag, name: str) -> str | None:
    value = node.get(name)
    if isinstance(value, list):
        return " ".join(value)
    return value


def _id_from_livres_href(href: str) -> str | None:
    if "/livres/" not in href:
        return None
    return href.split("/livres/", 1)[1].split("?", 1)[0].rstrip("/")


def _parse_cr_meta(meta: BsTag) -> SearchHit | None:
    link = meta.select_one(".titre1 a") or meta.select_one("a.titre1")
    if link is None:
        return None
    href = _attr(link, "href")
    babelio_id = _id_from_livres_href(href) if href else None
    if not babelio_id:
        return None
    author_node = meta.select_one(".libelle")
    author = _collapse(author_node.get_text(" ", strip=True)) if author_node else None
    return SearchHit(
        babelio_id=babelio_id,
        title=_collapse(link.get_text(" ", strip=True)),
        author=author or None,
    )


def _parse_mosaic_item(item: BsTag) -> SearchHit | None:
    link = item.select_one('a[href^="/livres/"]')
    if link is None:
        return None
    href = _attr(link, "href")
    babelio_id = _id_from_livres_href(href) if href else None
    if not babelio_id:
        return None
    title_node = item.select_one(".titre_compact")
    title = title_node.get_text(" ", strip=True) if title_node else link.get_text(" ", strip=True)
    return SearchHit(babelio_id=babelio_id, title=_collapse(title), author=None)


def _parse_babelio_id(soup: BeautifulSoup) -> str | None:
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical is None:
        return None
    href = _attr(canonical, "href")
    return _id_from_livres_href(href) if href else None


def _parse_title(soup: BeautifulSoup) -> str:
    node = soup.select_one("head > title") or soup.select_one("title")
    raw = _collapse(node.get_text(" ", strip=True)) if node is not None else ""
    if raw.endswith(_TITLE_SUFFIX):
        # Form: "<title> - <author> - Babelio"; drop the trailing author and site suffix.
        return raw.rsplit(" - ", 2)[0]
    return raw


def _parse_authors(soup: BeautifulSoup) -> tuple[str, ...]:
    container = soup.select_one(".livre_con")
    if container is None:
        return ()
    authors: list[str] = []
    seen: set[str] = set()
    for link in container.select('a[href^="/auteur/"]'):
        name = _collapse(link.get_text(" ", strip=True))
        if not name or name in seen or _EDITORIAL_ROLE.search(name):
            continue
        seen.add(name)
        authors.append(name)
    return tuple(authors)


def _parse_isbn(refs_text: str) -> str | None:
    match = _ISBN13.search(refs_text)
    return match.group(1) if match else None


def _parse_publisher(refs: BsTag | None) -> str | None:
    if refs is None:
        return None
    names: list[str] = []
    seen: set[str] = set()
    for link in refs.select('a[href^="/editeur"]'):
        name = _collapse(link.get_text(" ", strip=True))
        if not name or name in seen or name.casefold() == "voir plus":
            continue
        seen.add(name)
        names.append(name)
    return " / ".join(names) if names else None


def _parse_pubdate(refs_text: str) -> date | None:
    match = _DATE.search(refs_text)
    if match is None:
        return None
    try:
        parsed = datetime.strptime(match.group(0), "%d/%m/%Y").date()
    except ValueError:
        return None
    return parsed if parsed.year > 0 else None


def _parse_rating(soup: BeautifulSoup) -> float | None:
    # Pages carry one aggregate ratingValue plus a per-review ratingValue meta node for every
    # displayed review; scope to the aggregateRating container so review scores can't be mistaken
    # for the book's rating regardless of document order.
    for node in soup.select('[itemprop="aggregateRating"] [itemprop="ratingValue"]'):
        text = node.get_text(strip=True)
        if not text:
            continue
        try:
            value = float(text.replace(",", ".")) * (_RATING_TARGET_MAX / _RATING_SOURCE_MAX)
        except ValueError:
            continue
        return max(0.0, min(_RATING_TARGET_MAX, value))
    return None


def _parse_series(soup: BeautifulSoup) -> str | None:
    link = soup.select_one('a[href^="/serie/"]')
    if link is None:
        return None
    name = _collapse(link.get_text(" ", strip=True))
    return name or None


def _parse_series_index(title: str) -> float | None:
    match = _TOME.search(title)
    return float(match.group(1)) if match else None


def _parse_cover_url(soup: BeautifulSoup) -> str | None:
    link = soup.select_one('link[rel="image_src"]')
    if link is None:
        return None
    return _attr(link, "href")


def _parse_summary(soup: BeautifulSoup) -> str | None:
    node = soup.select_one(".livre_resume")
    if node is None:
        return None
    text = _collapse(node.get_text(" ", strip=True))
    return text or None


def _parse_summary_full_args(soup: BeautifulSoup) -> tuple[int | None, int | None]:
    node = soup.select_one(".livre_resume")
    if node is None:
        return None, None
    for tag in [node, *node.select("[onclick]")]:
        onclick = _attr(tag, "onclick")
        if not onclick:
            continue
        match = _VOIR_PLUS.search(onclick)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def _parse_tags(soup: BeautifulSoup) -> tuple[Tag, ...]:
    tags: list[Tag] = []
    for link in soup.select(".tags a"):
        category: TagCategory | None = None
        relevance = 0
        for cls in link.get_attribute_list("class"):
            category_match = _TAG_CATEGORY.match(cls)
            if category_match is not None:
                category = _TAG_CATEGORY_BY_INDEX.get(int(category_match.group(1)))
                continue
            relevance_match = _TAG_RELEVANCE.match(cls)
            if relevance_match is not None:
                relevance = int(relevance_match.group(1))
        if category is None:
            continue
        name = _collapse(link.get_text(" ", strip=True))
        if name:
            tags.append(Tag(name=name, category=category, relevance=relevance))
    return tuple(tags)
