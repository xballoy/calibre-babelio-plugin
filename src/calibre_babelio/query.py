"""Pure construction of the Babelio search term from book metadata."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_NON_ISBN = re.compile(r"[^0-9Xx]")

# Babelio folds case/accents/punctuation itself; we map these to ASCII only so apostrophes survive
# and the term stays encodable in client.py's ISO-8859-1 request body.
_TYPOGRAPHIC = str.maketrans(
    {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}
)


def build_search_query(
    *,
    title: str | None,
    authors: Sequence[str] | None,
    isbn: str | None,
) -> str | None:
    """Build the Babelio search term: a valid ISBN/EAN verbatim, else the near-verbatim
    title/authors. `None` when no usable input."""
    if isbn:
        normalized = _normalize_isbn(isbn)
        if normalized is not None:
            return normalized

    terms: list[str] = []
    if title:
        terms.append(title)
    if authors:
        terms.extend(author for author in authors if author)

    return _normalize_terms(" ".join(terms))


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


def _normalize_terms(text: str) -> str | None:
    mapped = text.translate(_TYPOGRAPHIC)
    latin1_safe = mapped.encode("iso-8859-1", "ignore").decode("iso-8859-1")
    normalized = " ".join(latin1_safe.split())
    return normalized if any(char.isalnum() for char in normalized) else None
