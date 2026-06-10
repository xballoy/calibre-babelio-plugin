from __future__ import annotations

import pytest

from calibre_babelio.query import build_search_query


def _query(
    title: str | None = None,
    authors: list[str] | None = None,
    isbn: str | None = None,
) -> str | None:
    return build_search_query(title=title, authors=authors, isbn=isbn)


def test_herisson_example_is_sent_near_verbatim() -> None:
    assert _query(title="L'élégance du hérisson", authors=["Barbery"]) == (
        "L'élégance du hérisson Barbery"
    )


def test_full_author_name_keeps_first_name() -> None:
    assert _query(title="L'élégance du hérisson", authors=["Muriel Barbery"]) == (
        "L'élégance du hérisson Muriel Barbery"
    )


@pytest.mark.parametrize(
    ("isbn", "expected"),
    [
        ("9782226244338", "9782226244338"),     # valid ISBN-13 passed through unchanged
        ("2226244336", "9782226244338"),         # valid ISBN-10 → 978-prefixed EAN-13
        ("123456789X", "9781234567897"),         # ISBN-10 with "X" check digit
        ("978-2-226-24433-8", "9782226244338"),  # hyphen separators stripped
        ("1-234-56789-x", "9781234567897"),      # separators + lowercase "x"
    ],
)
def test_valid_isbn_is_normalized_to_ean13(isbn: str, expected: str) -> None:
    assert _query(isbn=isbn) == expected


def test_valid_isbn_takes_precedence_over_title() -> None:
    assert _query(title="ignored", isbn="9782226244338") == "9782226244338"


def test_invalid_isbn_checksum_falls_through_to_title() -> None:
    assert _query(title="Oz", isbn="9782226244330") == "Oz"


def test_misplaced_x_in_isbn10_is_invalid() -> None:
    assert _query(title="Oz", isbn="12345X789X") == "Oz"


def test_invalid_isbn_with_no_title_or_author_is_none() -> None:
    assert _query(isbn="0000000001") is None


def test_diacritics_are_kept() -> None:
    assert _query(title="à côté de l'âtre") == "à côté de l'âtre"


def test_punctuation_is_kept() -> None:
    assert _query(title="Autre-Monde, tome 5 : Oz") == "Autre-Monde, tome 5 : Oz"


def test_stopwords_are_kept() -> None:
    assert _query(title="Le Comte de Monte Cristo") == "Le Comte de Monte Cristo"


def test_apostrophe_is_kept() -> None:
    # stripping it splits "t'arrache" into "t arrache", which Babelio won't match to "tarrache"
    assert _query(title="Et la vie t'arrache à moi", authors=["Hendrickx Virginie"]) == (
        "Et la vie t'arrache à moi Hendrickx Virginie"
    )


def test_leading_article_is_kept() -> None:
    # dropping the article lets a fuzzy mismatch outrank the target on Babelio
    assert _query(title="La colocataire", authors=["Sarah Bailey"]) == "La colocataire Sarah Bailey"


def test_typographic_apostrophe_is_mapped_to_ascii() -> None:
    assert _query(title="L’élégance") == "L'élégance"


def test_typographic_dashes_and_ellipsis_are_mapped_to_ascii() -> None:
    assert _query(title="A–B—C…") == "A-B-C..."


def test_non_latin1_characters_are_dropped() -> None:
    assert _query(title="Café ☕ 你好", authors=["Zola"]) == "Café Zola"


def test_multiple_authors_are_joined() -> None:
    assert _query(title="Boule de suif", authors=["Guy de Maupassant", "Émile Zola"]) == (
        "Boule de suif Guy de Maupassant Émile Zola"
    )


def test_empty_author_strings_are_ignored() -> None:
    assert _query(title="Oz", authors=["", "Chattam"]) == "Oz Chattam"


def test_author_only_query() -> None:
    assert _query(authors=["Maxime Chattam"]) == "Maxime Chattam"


def test_title_reduced_to_only_non_latin1_returns_none() -> None:
    assert _query(title="你好世界") is None


@pytest.mark.parametrize(
    ("title", "authors", "isbn"),
    [
        (None, None, None),
        ("", [], ""),
        ("   ", None, None),
    ],
)
def test_no_usable_input_returns_none(
    title: str | None, authors: list[str] | None, isbn: str | None
) -> None:
    assert build_search_query(title=title, authors=authors, isbn=isbn) is None


def test_punctuation_only_title_returns_none() -> None:
    assert _query(title="!!! ---") is None
