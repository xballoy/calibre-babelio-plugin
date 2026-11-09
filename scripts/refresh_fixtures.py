from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]

import conftest  # noqa: E402, F401

from calibre_babelio.client import (  # noqa: E402
    _DEFAULT_USER_AGENT,
    BabelioClient,
    FetchResult,
)
from calibre_babelio.errors import BabelioBlocked, CircuitBreakerOpen  # noqa: E402
from live_browser import UrllibBrowser  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable

_CHATTAM_BOOK = "Chattam-Autre-Monde-tome-5--Oz/401283"
_VOIR_PLUS = re.compile(rb"voir_plus_a\(\s*'[^']*'\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_AUTHOR_SEARCH = "Maxime Chattam"
_BIBLIOGRAPHY_LINK = re.compile(rb'href="(/auteur/[^"]+/bibliographie)"')


@dataclass(frozen=True, slots=True)
class Fixture:
    name: str
    fetch: Callable[[BabelioClient, dict[str, FetchResult]], FetchResult]
    expect_final_url: Callable[[str], bool] = lambda url: True


def _search(terms: str) -> Callable[[BabelioClient, dict[str, FetchResult]], FetchResult]:
    return lambda client, _: client.search(terms)


def _book(babelio_id: str) -> Callable[[BabelioClient, dict[str, FetchResult]], FetchResult]:
    return lambda client, _: client.get_book_page(babelio_id)


def _full_summary(client: BabelioClient, fetched: dict[str, FetchResult]) -> FetchResult:
    book = fetched.get("book_chattam.html") or client.get_book_page(_CHATTAM_BOOK)
    match = _VOIR_PLUS.search(book.body)
    if match is None:
        raise RuntimeError("no voir_plus_a(...) call on the Chattam book page")
    return client.get_full_summary(int(match.group(1)), int(match.group(2)), book.final_url)


def _author_bibliography(client: BabelioClient, fetched: dict[str, FetchResult]) -> FetchResult:
    search = fetched.get("search_by_author.html") or client.search(_AUTHOR_SEARCH)
    match = _BIBLIOGRAPHY_LINK.search(search.body)
    if match is None:
        raise RuntimeError("no bibliography link on the author search page")
    return client.get_author_bibliography(match.group(1).decode("ascii"))


FIXTURE_SPECS: tuple[Fixture, ...] = (
    Fixture("search_by_isbn.html", _search("9782226244338")),
    Fixture("search_by_title.html", _search("L'élégance du hérisson")),
    Fixture("search_by_both.html", _search("Barbery élégance hérisson")),
    Fixture("search_by_author.html", _search(_AUTHOR_SEARCH)),
    Fixture("search_no_results.html", _search("zxqwvbnmlkjhgfdsapoiuyt")),
    Fixture(
        "author_bibliography_chattam.html",
        _author_bibliography,
        lambda url: url.endswith("/bibliographie"),
    ),
    Fixture(
        "book_chattam.html",
        _book(_CHATTAM_BOOK),
        lambda url: url.endswith(f"/livres/{_CHATTAM_BOOK}"),
    ),
    Fixture(
        "book_herisson_noseries.html",
        _book("Barbery-Lelegance-du-herisson/2852"),
        lambda url: "/livres/" in url and url.endswith("/2852"),
    ),
    Fixture(
        "book_montecristo_richtags.html",
        _book("Dumas-Le-Comte-de-Monte-Cristo/1424592"),
        lambda url: "/livres/" in url and url.endswith("/1424592"),
    ),
    Fixture(
        "book_asterix_multiauthor.html",
        _book("Goscinny-Asterix-tome-1--Asterix-le-gaulois/17540"),
        lambda url: "/livres/" in url and url.endswith("/17540"),
    ),
    Fixture(
        "book_not_found_redirects_home.html",
        _book("Inexistant-Livre-inexistant/999999999"),
        lambda url: "/livres/" not in url,
    ),
    Fixture("ajax_resume_voirplus.html", _full_summary),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-download the Babelio HTML fixtures used by the parser and worker tests."
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("BABELIO_COOKIE"),
        help="jstsToken cookie value (defaults to $BABELIO_COOKIE)",
    )
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("BABELIO_UA") or _DEFAULT_USER_AGENT,
        help="User-Agent to send (defaults to $BABELIO_UA, then the bundled Chrome UA)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=FIXTURES,
        help=f"directory to write fixtures into (default: {FIXTURES.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="NAME",
        choices=[spec.name for spec in FIXTURE_SPECS],
        help="refresh only these fixtures",
    )
    args = parser.parse_args()
    if not args.token:
        parser.error("a token is required: pass --token or set BABELIO_COOKIE")
    return args


def main() -> int:
    args = _parse_args()
    specs = [spec for spec in FIXTURE_SPECS if not args.only or spec.name in args.only]
    args.out.mkdir(parents=True, exist_ok=True)
    client = BabelioClient(
        UrllibBrowser(),
        args.token,
        args.user_agent,
        lockfile_path=args.out / ".refresh_circuit_breaker.lock",
        block_threshold=1,
    )

    fetched: dict[str, FetchResult] = {}
    failures: list[str] = []
    for spec in specs:
        try:
            result = spec.fetch(client, fetched)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{spec.name}: {type(exc).__name__}: {exc}")
            print(f"FAIL {spec.name}: {exc}", file=sys.stderr)
            if isinstance(exc, BabelioBlocked | CircuitBreakerOpen):
                break
            continue
        if not spec.expect_final_url(result.final_url):
            failures.append(f"{spec.name}: unexpected final URL {result.final_url}")
            print(f"FAIL {spec.name}: unexpected final URL {result.final_url}", file=sys.stderr)
            continue
        fetched[spec.name] = result
        print(f"ok   {spec.name:<36} {len(result.body):>8} bytes  {result.final_url}")

    (args.out / ".refresh_circuit_breaker.lock").unlink(missing_ok=True)

    if failures:
        print(f"\n{len(failures)} fixture(s) failed; nothing was written.", file=sys.stderr)
        return 1

    for name, result in fetched.items():
        (args.out / name).write_bytes(result.body)
    print(f"\nWrote {len(fetched)} fixture(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
