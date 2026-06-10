"""Pure construction of the Babelio search term from book metadata."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

_NON_ISBN = re.compile(r"[^0-9Xx]")
_PUNCT = re.compile(r"[^a-z0-9]+")  # applied after deburr+lowercase, so the input is ASCII

_MIN_TOKEN_LEN = 2

# Leading articles and short French stop tokens; dropped wherever they appear (the validated
# hérisson example drops a mid-string "du", not just a leading article).
_STOPWORDS = frozenset(
    {"le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "au", "aux", "en"}
)


def build_search_query(
    *,
    title: str | None,
    authors: Sequence[str] | None,
    isbn: str | None,
) -> str | None:
    """Build the Babelio search term: a valid ISBN/EAN verbatim, else the deburred,
    article-stripped, lowercased title/authors. `None` when no usable input."""
    if isbn:
        normalized = _normalize_isbn(isbn)
        if normalized is not None:
            return normalized

    terms: list[str] = []
    if title:
        terms.append(title)
    if authors:
        terms.extend(author for author in authors if author)

    text = " ".join(terms).strip()
    if not text:
        return None
    return _deburr_terms(text) or None


def _normalize_isbn(raw: str) -> str | None:
    cleaned = _NON_ISBN.sub("", raw).upper()
    if len(cleaned) == 13 and cleaned.isdigit():
        if _isbn13_check_digit(cleaned[:12]) == cleaned[12]:
            return cleaned
        return None
    if len(cleaned) == 10 and _isbn10_checksum_ok(cleaned):
        core = "978" + cleaned[:9]  # Babelio's validated example was a 13-digit EAN
        return core + _isbn13_check_digit(core)
    return None


def _isbn13_check_digit(twelve: str) -> str:
    total = sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(twelve))
    return str((10 - total % 10) % 10)


def _isbn10_checksum_ok(ten: str) -> bool:
    total = 0
    for index, char in enumerate(ten):
        if char == "X":
            if index != 9:  # the check character "X" (value 10) is valid only in last position
                return False
            value = 10
        else:
            value = int(char)
        total += value * (10 - index)
    return total % 11 == 0


def _deburr_terms(text: str) -> str:
    cleaned = _PUNCT.sub(" ", _strip_accents(text).lower())
    tokens = cleaned.split()
    kept = [token for token in tokens if len(token) >= _MIN_TOKEN_LEN and token not in _STOPWORDS]
    # Never emit an empty query for non-empty input: if every token was dropped (e.g. a title made
    # entirely of articles), fall back to the deburred tokens unfiltered.
    return " ".join(kept) if kept else " ".join(tokens)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(char for char in nfkd if not unicodedata.combining(char))
