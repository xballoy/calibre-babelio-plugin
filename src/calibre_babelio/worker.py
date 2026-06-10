"""Per-book fetch worker: bridges the HTTP client and parser into a Calibre `Metadata`."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol

from .errors import BabelioBlocked, CircuitBreakerOpen
from .parser import (
    BabelioBook,
    SearchHit,
    TagCategory,
    parse_book_page,
    parse_full_summary,
)

if TYPE_CHECKING:
    from queue import Queue

    from .client import FetchResult

_LANGUAGE = "fra"  # Babelio metadata is French; we don't do per-book language detection.


class MetadataProtocol(Protocol):
    """The subset of Calibre's `Metadata` the worker reads or writes."""

    title: str
    authors: list[str]
    source_relevance: int
    languages: list[str]
    comments: str | None
    pubdate: datetime | None
    publisher: str | None
    rating: float | None
    series: str | None
    series_index: float | None
    tags: list[str]

    @property
    def identifiers(self) -> Mapping[str, str]: ...

    def set_identifier(self, typ: str, val: str) -> None: ...


MetadataFactory = Callable[[str, list[str] | None], MetadataProtocol]
DateConverter = Callable[[date], datetime]


class ClientProtocol(Protocol):
    def get_book_page(self, babelio_id: str) -> FetchResult: ...
    def get_full_summary(self, summary_type: int, obj_id: int, referer: str) -> FetchResult: ...


class SourceProtocol(Protocol):
    def clean_downloaded_metadata(self, mi: MetadataProtocol) -> None: ...
    def cache_identifier_to_cover_url(self, id_: str, url: str) -> None: ...


class LogProtocol(Protocol):
    def info(self, *args: object) -> None: ...
    def error(self, *args: object) -> None: ...
    def exception(self, *args: object) -> None: ...


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    """Per-field toggles driving which metadata fields the worker populates."""

    comments: bool
    pubdate: bool
    publisher: bool
    rating: bool
    series: bool
    tags: bool
    # Minimum tag relevance to keep, per category (genre / thème / lieu / quand).
    tag_relevance: Mapping[TagCategory, int]


@dataclass(frozen=True, slots=True)
class WorkerContext:
    """Dependencies shared across all workers of a single `identify()` call."""

    client: ClientProtocol
    plugin: SourceProtocol
    result_queue: Queue[MetadataProtocol]
    abort: threading.Event
    log: LogProtocol
    metadata_factory: MetadataFactory
    # Renders the date on the correct day in the user's timezone; a bare midnight-UTC
    # datetime would display as the previous day west of UTC.
    date_to_datetime: DateConverter
    config: WorkerConfig


class Worker(threading.Thread):
    """Fetches and parses one book, builds its `Metadata`, and queues it.

    A caught anti-bot block is recorded on :attr:`error` so the orchestrator can surface the
    translated message; :attr:`result` exposes the queued object for tests.
    """

    def __init__(self, target: SearchHit | str, relevance: int, ctx: WorkerContext) -> None:
        # Daemon because an aborted identify() abandons its workers without joining them.
        super().__init__(daemon=True)
        self._target = target
        self._relevance = relevance
        self._ctx = ctx
        self.error: BabelioBlocked | CircuitBreakerOpen | None = None
        self.result: MetadataProtocol | None = None

    def run(self) -> None:
        ctx = self._ctx
        if ctx.abort.is_set():
            return

        babelio_id = self._target if isinstance(self._target, str) else self._target.babelio_id
        try:
            page = ctx.client.get_book_page(babelio_id)
        except (BabelioBlocked, CircuitBreakerOpen) as exc:
            self.error = exc
            ctx.log.error("Babelio blocked while fetching", babelio_id, exc)
            return
        except Exception:
            ctx.log.exception("Failed to fetch Babelio book", babelio_id)
            return

        try:
            book = parse_book_page(page.body)
            if book is None:
                ctx.log.info("Not a Babelio book page", babelio_id)
                return
            mi = self._build_metadata(book, babelio_id, page.final_url)
            ctx.plugin.clean_downloaded_metadata(mi)
            self.result = mi
            ctx.result_queue.put(mi)
        except Exception:
            ctx.log.exception("Failed to parse Babelio book", babelio_id)

    def _build_metadata(  # noqa: C901 - a flat per-field toggle mapping; splitting hurts cohesion.
        self, book: BabelioBook, babelio_id: str, referer: str
    ) -> MetadataProtocol:
        ctx = self._ctx
        config = ctx.config

        title = book.title or (self._target.title if isinstance(self._target, SearchHit) else "")
        mi = ctx.metadata_factory(title, list(book.authors) or None)

        mi.set_identifier("babelio_id", babelio_id)
        if book.isbn:
            mi.set_identifier("isbn", book.isbn)

        mi.source_relevance = self._relevance
        mi.languages = [_LANGUAGE]

        if book.cover_url:
            ctx.plugin.cache_identifier_to_cover_url(babelio_id, book.cover_url)

        if config.comments:
            comments = self._resolve_comments(book, referer)
            if comments:
                mi.comments = comments

        if config.pubdate and book.pubdate is not None:
            mi.pubdate = ctx.date_to_datetime(book.pubdate)

        if config.publisher and book.publisher:
            mi.publisher = book.publisher

        if config.rating and book.rating is not None:
            mi.rating = book.rating

        if config.series and book.series:
            mi.series = book.series
            mi.series_index = book.series_index if book.series_index is not None else 1.0

        if config.tags:
            tags = self._select_tags(book)
            if tags:
                mi.tags = tags

        return mi

    def _resolve_comments(self, book: BabelioBook, referer: str) -> str | None:
        ctx = self._ctx
        full_type, full_id = book.summary_full_type, book.summary_full_id
        if full_type is None or full_id is None or ctx.abort.is_set():
            return book.summary

        try:
            fragment = ctx.client.get_full_summary(full_type, full_id, referer)
            full = parse_full_summary(fragment.body)
        except Exception:
            ctx.log.exception("Failed to fetch full Babelio résumé", referer)
            return book.summary
        return full or book.summary

    def _select_tags(self, book: BabelioBook) -> list[str]:
        thresholds = self._ctx.config.tag_relevance
        names: list[str] = []
        seen: set[str] = set()
        for tag in book.tags:
            if tag.relevance < thresholds.get(tag.category, 0) or tag.name in seen:
                continue
            seen.add(tag.name)
            names.append(tag.name)
        return names
