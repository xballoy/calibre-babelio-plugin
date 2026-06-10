from __future__ import annotations

import pytest

from calibre_babelio.query import build_search_query


def _query(
    title: str | None = None,
    authors: list[str] | None = None,
    isbn: str | None = None,
) -> str | None:
    return build_search_query(title=title, authors=authors, isbn=isbn)


def test_herisson_example_surfaces_target_at_rank_zero() -> None:
    # this deburred form returns the target at rank 0.
    assert _query(title="L'élégance du hérisson", authors=["Barbery"]) == (
        "elegance herisson barbery"
    )


def test_full_author_name_keeps_first_name() -> None:
    assert _query(title="L'élégance du hérisson", authors=["Muriel Barbery"]) == (
        "elegance herisson muriel barbery"
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
    assert _query(title="Oz", isbn="9782226244330") == "oz"


def test_misplaced_x_in_isbn10_is_invalid() -> None:
    assert _query(title="Oz", isbn="12345X789X") == "oz"


def test_invalid_isbn_with_no_title_or_author_is_none() -> None:
    assert _query(isbn="0000000001") is None


def test_diacritics_are_removed() -> None:
    assert _query(title="à côté de l'âtre") == "cote atre"


def test_two_letter_real_word_is_kept() -> None:
    assert _query(title="Autre-Monde, tome 5 : Oz") == "autre monde tome oz"


def test_stopwords_are_dropped_anywhere_not_just_leading() -> None:
    assert _query(title="Le Comte de Monte Cristo") == "comte monte cristo"


def test_multiple_authors_are_joined() -> None:
    assert _query(title="Boule de suif", authors=["Guy de Maupassant", "Émile Zola"]) == (
        "boule suif guy maupassant emile zola"
    )


def test_empty_author_strings_are_ignored() -> None:
    assert _query(title="Oz", authors=["", "Chattam"]) == "oz chattam"


def test_author_only_query() -> None:
    assert _query(authors=["Maxime Chattam"]) == "maxime chattam"


def test_all_stopword_title_falls_back_to_deburred_tokens() -> None:
    assert _query(title="Le La Les") == "le la les"


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
