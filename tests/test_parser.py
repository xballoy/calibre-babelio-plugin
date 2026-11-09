from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from calibre_babelio.parser import (
    AuthorBibliography,
    BabelioBook,
    SearchHit,
    SearchPage,
    parse_author_bibliography,
    parse_book_page,
    parse_full_summary,
    parse_search_results,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _book(name: str) -> BabelioBook:
    book = parse_book_page(_load(name))
    assert book is not None
    return book


def test_book_identity_comes_from_structured_data() -> None:
    b = _book("book_chattam.html")
    assert b.babelio_id == "Chattam-Autre-Monde-tome-5--Oz/401283"
    assert b.title == "Autre-Monde, tome 5 : Oz"
    assert b.authors == ("Maxime Chattam",)


def test_scientific_editor_is_not_an_author() -> None:
    assert _book("book_montecristo_richtags.html").authors == ("Alexandre Dumas",)


def test_co_authors_are_all_kept_in_page_order() -> None:
    assert _book("book_asterix_multiauthor.html").authors == ("René Goscinny", "Albert Uderzo")


def test_accented_title_is_decoded() -> None:
    assert _book("book_herisson_noseries.html").title == "L'Élégance du hérisson"


def test_edition_details_come_from_structured_data() -> None:
    b = _book("book_chattam.html")
    assert b.isbn == "9782226244338"
    assert b.publisher == "Albin Michel"
    assert b.pubdate == date(2012, 11, 2)


def test_unknown_publication_date_leaves_pubdate_unset() -> None:
    b = _book("book_herisson_noseries.html")
    assert b.pubdate is None
    assert b.publisher == "Gallimard"


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("book_chattam.html", 8.44),
        ("book_herisson_noseries.html", 7.56),
        ("book_montecristo_richtags.html", 9.1),
    ],
)
def test_rating_is_rescaled_from_five_to_ten(fixture: str, expected: float) -> None:
    assert _book(fixture).rating == pytest.approx(expected)


def test_cover_and_truncated_summary_point_to_full_summary() -> None:
    b = _book("book_chattam.html")
    assert b.cover_url == "https://www.babelio.com/couv/CVT_CVT_Autre-Monde-Tome-5--Oz_6607.jpg"
    assert b.summary is not None
    assert b.summary.startswith("La guerre avec les Cyniks terminée")
    assert (b.summary_full_type, b.summary_full_id) == (1, 918135)


def test_series_and_volume_come_from_the_details_table() -> None:
    b = _book("book_chattam.html")
    assert b.series == "Autre-Monde"
    assert b.series_index == 5.0


def test_book_without_series_leaves_series_unset() -> None:
    b = _book("book_herisson_noseries.html")
    assert b.series is None
    assert b.series_index is None


def test_tags_are_the_structured_data_genres() -> None:
    assert _book("book_chattam.html").tags == ("science-fiction", "littérature française")
    assert _book("book_montecristo_richtags.html").tags == ("histoire",)


def _page(node: object, body: str = "") -> bytes:
    script = f'<script type="application/ld+json">{json.dumps(node)}</script>'
    return f"<html><head>{script}</head><body>{body}</body></html>".encode("iso-8859-1")


def _inline_book(node: dict[str, object], body: str = "") -> BabelioBook:
    book = parse_book_page(_page({"@type": "Book", "name": "T", **node}, body))
    assert book is not None
    return book


def _series_row(cell: str) -> str:
    return f'<table class="biblio-table"><tr><th>Série</th><td>{cell}</td></tr></table>'


def test_several_authors_keep_order_and_drop_duplicates() -> None:
    authors = [{"@type": "Person", "name": n} for n in ("René Goscinny", "Albert Uderzo")]
    book = _inline_book({"author": [*authors, authors[0]]})
    assert book.authors == ("René Goscinny", "Albert Uderzo")


def test_single_author_object_and_plain_name_are_accepted() -> None:
    assert _inline_book({"author": {"name": "Jean Roux"}}).authors == ("Jean Roux",)
    assert _inline_book({"author": "Jean Roux"}).authors == ("Jean Roux",)


def test_book_found_at_top_level_with_multiple_types() -> None:
    page = _page([{"@type": "WebPage"}, {"@type": ["Book", "Product"], "name": "Typed"}])
    book = parse_book_page(page)
    assert book is not None
    assert book.title == "Typed"


def test_malformed_structured_data_is_skipped() -> None:
    good = '<script type="application/ld+json">{"@type": "Book", "name": "Kept"}</script>'
    page = f'<script type="application/ld+json">{{not json</script>{good}'.encode()
    book = parse_book_page(page)
    assert book is not None
    assert book.title == "Kept"


def test_page_whose_structured_data_has_no_book_is_not_a_book() -> None:
    assert parse_book_page(_page({"@graph": [{"@type": "BreadcrumbList"}]})) is None
    assert parse_book_page(_page("just a string")) is None


def test_missing_optional_fields_are_unset() -> None:
    book = _inline_book({})
    assert book.babelio_id is None
    assert (book.isbn, book.publisher, book.pubdate, book.rating) == (None, None, None, None)
    assert (book.cover_url, book.summary, book.tags) == (None, None, ())
    assert (book.summary_full_type, book.summary_full_id) == (None, None)


def test_invalid_publication_date_is_unset() -> None:
    assert _inline_book({"datePublished": "-001-11-30"}).pubdate is None


@pytest.mark.parametrize(
    ("aggregate", "expected"),
    [
        ({"ratingValue": 4}, 8.0),
        ({"ratingValue": "3,5", "bestRating": "5"}, 7.0),
        ({"ratingValue": 9, "bestRating": 5}, 10.0),
        ({"ratingValue": 8, "bestRating": 10}, 8.0),
    ],
)
def test_rating_variants_are_rescaled(aggregate: dict[str, object], expected: float) -> None:
    assert _inline_book({"aggregateRating": aggregate}).rating == pytest.approx(expected)


@pytest.mark.parametrize(
    "aggregate", [{"ratingValue": "n/a"}, {"ratingValue": True}, {"bestRating": 5}, 4.2]
)
def test_unusable_rating_is_unset(aggregate: object) -> None:
    assert _inline_book({"aggregateRating": aggregate}).rating is None


def test_fractional_volume_is_parsed() -> None:
    book = _inline_book({}, _series_row('<a href="/serie/X/1">X</a> tome 0,5 sur 8'))
    assert (book.series, book.series_index) == ("X", 0.5)


def test_volume_falls_back_to_the_title() -> None:
    book = _inline_book({"name": "X, tome 3 : Y"}, _series_row('<a href="/serie/X/1">X</a>'))
    assert (book.series, book.series_index) == ("X", 3.0)


def test_series_without_volume_has_no_index() -> None:
    book = _inline_book({}, _series_row('<a href="/serie/X/1">X</a>'))
    assert (book.series, book.series_index) == ("X", None)


@pytest.mark.parametrize(
    "table",
    [
        _series_row("Hors série"),
        _series_row('<a href="/serie/X/1"> </a>'),
        '<table class="biblio-table"><tr><th>Série</th></tr></table>',
    ],
)
def test_unusable_series_row_leaves_series_unset(table: str) -> None:
    assert _inline_book({}, table).series is None


def test_full_summary_args_ignore_unrelated_handlers() -> None:
    body = (
        '<div class="hero-summary-wrap"><span onclick="track()">x</span>'
        "<button onclick=\"voir_plus_a('#d_bio',1,42);\">Voir plus</button></div>"
    )
    book = _inline_book({}, body)
    assert (book.summary_full_type, book.summary_full_id) == (1, 42)


def test_non_book_page_returns_none() -> None:
    assert parse_book_page(_load("book_not_found_redirects_home.html")) is None


def test_isbn_search_returns_the_single_exact_hit() -> None:
    page = parse_search_results(_load("search_by_isbn.html"))
    assert page.hits == (
        SearchHit(
            babelio_id="Chattam-Autre-Monde-tome-5--Oz/401283",
            title="Autre-Monde, tome 5 : Oz",
            author="Maxime Chattam",
        ),
    )
    assert page.bibliography is None


def test_title_search_lists_only_book_results_not_menu_links() -> None:
    page = parse_search_results(_load("search_by_title.html"))
    assert [hit.babelio_id for hit in page.hits] == [
        "Barbery-Llegance-du-herisson/2852",
        "lePetitLitterairefr-Fiche-de-lecture--Lelegance-du-herisson-de-Murie/500207",
        "Benoit-Sonic--Lelegance-dun-herisson-bleu/1051717",
    ]
    assert page.hits[0].author == "Muriel Barbery"


def test_title_and_author_search_ranks_the_book_first() -> None:
    page = parse_search_results(_load("search_by_both.html"))
    assert page.hits[0] == SearchHit(
        "Barbery-Llegance-du-herisson/2852", "L'Élégance du hérisson", "Muriel Barbery"
    )
    assert page.bibliography is None


def test_empty_search_has_no_hits_and_no_bibliography() -> None:
    assert parse_search_results(_load("search_no_results.html")) == SearchPage((), None)


def test_author_search_points_to_the_author_bibliography() -> None:
    page = parse_search_results(_load("search_by_author.html"))
    assert page.hits == ()
    assert page.bibliography == AuthorBibliography(
        path="/auteur/Maxime-Chattam/2038/bibliographie", author="Maxime Chattam"
    )


def test_bibliography_lists_the_author_books() -> None:
    hits = parse_author_bibliography(_load("author_bibliography_chattam.html"), "Maxime Chattam")
    assert len(hits) == 20
    assert hits[0] == SearchHit("Chattam-Lme-du-mal/899191", "L'Âme du mal", "Maxime Chattam")


def test_result_items_without_a_book_link_are_skipped() -> None:
    html = (
        b'<section class="rs-section">'
        b'<div class="lv-item"><p class="lv-title">No link</p></div>'
        b'<div class="lv-item"><p class="lv-title"><a href="/auteur/x/1">X</a></p></div>'
        b'<div class="lv-item"><p class="lv-title"><a href="/livres/S/9">Kept</a></p></div>'
        b"</section>"
    )
    assert parse_search_results(html).hits == (SearchHit("S/9", "Kept", None),)


def test_author_card_without_bibliography_link_is_ignored() -> None:
    html = b'<section class="rs-section rs-author"><h2>X</h2></section>'
    assert parse_search_results(html).bibliography is None


def test_full_summary_keeps_paragraph_breaks() -> None:
    text = parse_full_summary(_load("ajax_resume_voirplus.html"))
    assert text is not None
    lines = text.split("\n")
    assert len(lines) == 8
    assert lines[0].startswith("La guerre avec les Cyniks terminée")
    assert lines[-1] == "Le sort d'Autre-Monde est en jeu"


def test_full_summary_empty_fragment_is_none() -> None:
    assert parse_full_summary(b"") is None
    assert parse_full_summary(b"<br>   <br>") is None
