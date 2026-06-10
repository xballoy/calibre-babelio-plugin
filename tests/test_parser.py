from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from calibre_babelio.parser import (
    BabelioBook,
    SearchHit,
    Tag,
    TagCategory,
    _attr,
    _parse_authors,
    _parse_babelio_id,
    _parse_cover_url,
    _parse_pubdate,
    _parse_publisher,
    _parse_rating,
    _parse_summary,
    _parse_summary_full_args,
    _parse_tags,
    _parse_title,
    _soup,
    parse_book_page,
    parse_search_results,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _search(name: str) -> list[SearchHit]:
    return parse_search_results(_load(name))


def _book(name: str) -> BabelioBook:
    book = parse_book_page(_load(name))
    assert book is not None
    return book


def test_isbn_search_returns_single_exact_hit() -> None:
    assert _search("search_by_isbn.html") == [
        SearchHit(
            babelio_id="Chattam-Autre-Monde-tome-5--Oz/401283",
            title="Autre-Monde, tome 5 : Oz",
            author="Maxime Chattam",
        )
    ]


def test_title_search_returns_ten_hits_with_authors() -> None:
    hits = _search("search_by_title.html")
    assert len(hits) == 10
    assert all(h.author for h in hits)
    assert all(h.babelio_id for h in hits)
    assert hits[0] == SearchHit(
        babelio_id="Rowling-Harry-Potter-tome-1--Harry-Potter-a-lecole-des-s/18811",
        title="Harry Potter, tome 1 : Harry Potter à l'école des sorciers",
        author="J. K. Rowling",
    )


def test_combined_author_title_search_returns_multiple_hits() -> None:
    hits = _search("search_by_both.html")
    assert len(hits) == 10
    assert hits[0] == SearchHit(
        babelio_id="Pullman--la-croisee-des-mondes-tome-1--Les-royaumes-du-N/5533",
        title="À la croisée des mondes, tome 1 : Les royaumes du Nord",
        author="Philip Pullman",
    )


def test_author_search_uses_mosaic_layout() -> None:
    hits = _search("search_by_author.html")
    assert len(hits) == 5
    assert all(h.author is None for h in hits)
    assert hits[0] == SearchHit(
        babelio_id="Chattam-82-secondes/1893474",
        title="8,2 secondes",
        author=None,
    )


def test_no_results_page_yields_zero_hits() -> None:
    assert _search("search_no_results.html") == []


def test_book_with_series_extracts_all_fields() -> None:
    b = _book("book_chattam.html")
    assert b.babelio_id == "Chattam-Autre-Monde-tome-5--Oz/401283"
    assert b.title == "Autre-Monde, tome 5 : Oz"
    assert b.authors == ("Maxime Chattam",)
    assert b.series == "Autre-Monde"
    assert b.series_index == 5.0
    assert b.isbn == "9782226244338"
    assert b.publisher == "Albin Michel / Wiz"
    assert b.pubdate == date(2012, 11, 2)
    assert b.rating == pytest.approx(8.42)
    assert b.cover_url == "https://www.babelio.com/couv/CVT_CVT_Autre-Monde-Tome-5--Oz_6607.jpg"
    assert (b.summary_full_type, b.summary_full_id) == (1, 918135)
    assert b.summary is not None
    assert b.summary.startswith("La guerre avec les Cyniks")
    assert b.tags


def test_book_without_series_leaves_series_unset() -> None:
    b = _book("book_herisson_noseries.html")
    assert b.series is None
    assert b.series_index is None
    assert b.title == "L'élégance du hérisson"
    assert b.authors == ("Muriel Barbery",)
    assert b.isbn == "9782070391653"
    assert b.publisher == "Gallimard / Folio"


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("book_chattam.html", 8.42),  # 4,21 on /5
        ("book_herisson_noseries.html", 7.54),  # 3,77 on /5
        ("book_montecristo_richtags.html", 9.1),  # 4,55 on /5
    ],
)
def test_rating_uses_french_comma_and_rescales_to_ten(fixture: str, expected: float) -> None:
    assert _book(fixture).rating == pytest.approx(expected)


def test_unknown_date_sentinel_leaves_pubdate_unset() -> None:
    assert _book("book_herisson_noseries.html").pubdate is None


def test_author_names_are_whitespace_collapsed() -> None:
    name = _book("book_chattam.html").authors[0]
    assert name == "Maxime Chattam"
    assert "  " not in name


@pytest.mark.parametrize(
    "fixture",
    ["book_chattam.html", "book_herisson_noseries.html", "book_montecristo_richtags.html"],
)
def test_isbn_is_bare_thirteen_digits(fixture: str) -> None:
    isbn = _book(fixture).isbn
    assert isbn is not None
    assert re.fullmatch(r"\d{13}", isbn) is not None


def test_editorial_role_authors_are_filtered_out() -> None:
    b = _book("book_montecristo_richtags.html")
    assert b.authors == ("Alexandre Dumas",)
    assert all("(" not in author for author in b.authors)


def test_tags_cover_all_four_categories() -> None:
    tags = _book("book_montecristo_richtags.html").tags
    assert {tag.category for tag in tags} == set(TagCategory)
    assert all(tag.relevance > 0 for tag in tags)


def test_tag_category_and_relevance_classification() -> None:
    by_name = {tag.name: tag for tag in _book("book_montecristo_richtags.html").tags}
    assert by_name["aventure"] == Tag("aventure", TagCategory.GENRE, 22)
    assert by_name["vengeance"].category is TagCategory.THEME
    assert by_name["19ème siècle"].category is TagCategory.PERIOD


def test_non_book_page_returns_none() -> None:
    # An unknown book URL 301-redirects to the homepage; it has neither a canonical /livres/
    # link nor an editions block, so it is not a book page.
    assert parse_book_page(_load("book_not_found_redirects_home.html")) is None


def test_rating_uses_aggregate_not_a_preceding_review_score() -> None:
    # A per-review ratingValue appears *before* the aggregate in document order; scoping to the
    # aggregateRating container must still pick the aggregate (3,00 → 6.0), not the review (5.0).
    html = (
        b'<div itemscope itemtype="http://schema.org/Rating">'
        b'<meta itemprop="ratingValue" content="5.0"/></div>'
        b'<div itemprop="aggregateRating"><span itemprop="ratingValue">3,00</span></div>'
    )
    assert _parse_rating(_soup(html)) == pytest.approx(6.0)


def test_rating_clamps_above_scale_to_ten() -> None:
    html = b'<div itemprop="aggregateRating"><span itemprop="ratingValue">7,0</span></div>'
    assert _parse_rating(_soup(html)) == 10.0


def test_rating_skips_empty_and_unparseable_nodes() -> None:
    html = (
        b'<div itemprop="aggregateRating">'
        b'<span itemprop="ratingValue"></span>'
        b'<span itemprop="ratingValue">n/a</span>'
        b'<span itemprop="ratingValue">4,0</span></div>'
    )
    assert _parse_rating(_soup(html)) == pytest.approx(8.0)


def test_rating_absent_aggregate_yields_none() -> None:
    assert _parse_rating(_soup(b"<html></html>")) is None


def test_non_trailing_parenthetical_author_is_kept_role_is_dropped() -> None:
    html = (
        b'<div class="livre_con">'
        b'<a href="/auteur/x/1">Anne (Marie) Dupont</a>'
        b'<a href="/auteur/y/2">Bob Martin (Traducteur)</a></div>'
    )
    assert _parse_authors(_soup(html)) == ("Anne (Marie) Dupont",)


def test_authors_deduplicate_preserving_order() -> None:
    html = (
        b'<div class="livre_con">'
        b'<a href="/auteur/x/1">Jean Roux</a>'
        b'<a href="/auteur/x/1">Jean Roux</a></div>'
    )
    assert _parse_authors(_soup(html)) == ("Jean Roux",)


def test_authors_without_container_is_empty() -> None:
    assert _parse_authors(_soup(b"<html></html>")) == ()


def test_attr_joins_multivalued_attribute() -> None:
    node = _soup(b'<a class="a b c"></a>').select_one("a")
    assert node is not None
    assert _attr(node, "class") == "a b c"


def test_babelio_id_without_canonical_is_none() -> None:
    assert _parse_babelio_id(_soup(b"<html></html>")) is None


def test_babelio_id_ignores_non_livres_canonical() -> None:
    html = b'<link rel="canonical" href="https://www.babelio.com"/>'
    assert _parse_babelio_id(_soup(html)) is None


def test_title_without_site_suffix_returned_verbatim() -> None:
    assert _parse_title(_soup(b"<title>Just A Title</title>")) == "Just A Title"


def test_title_missing_is_empty() -> None:
    assert _parse_title(_soup(b"<html></html>")) == ""


def test_publisher_none_when_refs_missing() -> None:
    assert _parse_publisher(None) is None


def test_publisher_filters_voir_plus_and_dedupes() -> None:
    html = (
        b'<div class="livre_refs grey_light">'
        b'<a href="/editeur/Foo">Foo</a>'
        b'<a href="/editeur/Foo">Foo</a>'
        b'<a href="/editeur/x">Voir plus</a></div>'
    )
    refs = _soup(html).select_one(".livre_refs.grey_light")
    assert _parse_publisher(refs) == "Foo"


def test_pubdate_invalid_date_is_none() -> None:
    assert _parse_pubdate("Paru le 31/02/2012") is None


def test_pubdate_no_date_is_none() -> None:
    assert _parse_pubdate("no date here") is None


def test_cover_url_absent_is_none() -> None:
    assert _parse_cover_url(_soup(b"<html></html>")) is None


def test_summary_absent_is_none() -> None:
    assert _parse_summary(_soup(b"<html></html>")) is None


def test_summary_full_args_absent_is_none() -> None:
    assert _parse_summary_full_args(_soup(b"<html></html>")) == (None, None)


def test_summary_full_args_read_from_child_onclick() -> None:
    html = (
        b'<div class="livre_resume">'
        b'<span onclick="noise()">x</span>'
        b"<a onclick=\"javascript:voir_plus_a('#d', 2, 55)\">voir plus</a></div>"
    )
    assert _parse_summary_full_args(_soup(html)) == (2, 55)


def test_summary_full_args_without_voir_plus_is_none() -> None:
    html = b'<div class="livre_resume" onclick="other()">x</div>'
    assert _parse_summary_full_args(_soup(html)) == (None, None)


def test_cr_meta_without_link_is_skipped() -> None:
    assert parse_search_results(b'<div class="cr_meta"></div>') == []


def test_cr_meta_with_non_livres_href_is_skipped() -> None:
    html = b'<div class="cr_meta"><div class="titre1"><a href="/auteur/x/1">X</a></div></div>'
    assert parse_search_results(html) == []


def test_cr_meta_uses_anchor_titre1_fallback() -> None:
    html = b'<div class="cr_meta"><a class="titre1" href="/livres/Slug/9">Title</a></div>'
    assert parse_search_results(html) == [SearchHit("Slug/9", "Title", None)]


def test_mosaic_item_without_link_is_skipped() -> None:
    html = b'<ul class="livres_mozaique"><li class="item"></li></ul>'
    assert parse_search_results(html) == []


def test_mosaic_item_with_empty_livres_id_is_skipped() -> None:
    html = b'<ul class="livres_mozaique"><li class="item"><a href="/livres/">x</a></li></ul>'
    assert parse_search_results(html) == []


def test_mosaic_item_falls_back_to_link_text_for_title() -> None:
    html = (
        b'<ul class="livres_mozaique"><li class="item">'
        b'<a href="/livres/Slug/9">Fallback Title</a></li></ul>'
    )
    assert parse_search_results(html) == [SearchHit("Slug/9", "Fallback Title", None)]


def test_tags_skips_anchor_without_class() -> None:
    assert _parse_tags(_soup(b'<div class="tags"><a href="/x">no class</a></div>')) == ()


def test_tags_skips_uncategorized_and_empty_names() -> None:
    html = (
        b'<div class="tags">'
        b'<a class="tag_t5" href="/x">uncategorized</a>'
        b'<a class="tc_0 tag_t9" href="/x"></a></div>'
    )
    assert _parse_tags(_soup(html)) == ()
