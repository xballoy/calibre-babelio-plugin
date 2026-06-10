from __future__ import annotations

import threading
from datetime import UTC, date, datetime
from pathlib import Path
from queue import Queue

import pytest

from calibre_babelio.client import FetchResult
from calibre_babelio.errors import BabelioBlocked, CircuitBreakerOpen
from calibre_babelio.parser import SearchHit, TagCategory
from calibre_babelio.worker import (
    DateConverter,
    MetadataProtocol,
    Worker,
    WorkerConfig,
    WorkerContext,
)

FIXTURES = Path(__file__).parent / "fixtures"
_BOOK_URL = "https://www.babelio.com/livres/Chattam-Autre-Monde-tome-5--Oz/401283"
_CHATTAM_ID = "Chattam-Autre-Monde-tome-5--Oz/401283"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeMetadata:
    def __init__(self, title: str, authors: list[str] | None) -> None:
        self.title = title
        self.authors = authors if authors is not None else ["Unknown"]
        self.identifiers: dict[str, str] = {}
        self.source_relevance = 0
        self.languages: list[str] = []
        self.comments: str | None = None
        self.pubdate: datetime | None = None
        self.publisher: str | None = None
        self.rating: float | None = None
        self.series: str | None = None
        self.series_index: float | None = None
        self.tags: list[str] = []

    def set_identifier(self, typ: str, val: str) -> None:
        self.identifiers[typ] = val


class FakeClient:
    def __init__(
        self,
        page: bytes,
        *,
        final_url: str = _BOOK_URL,
        summary: bytes = b"",
        page_error: Exception | None = None,
        summary_error: Exception | None = None,
    ) -> None:
        self._page = page
        self._final_url = final_url
        self._summary = summary
        self._page_error = page_error
        self._summary_error = summary_error
        self.book_calls: list[str] = []
        self.summary_calls: list[tuple[int, int, str]] = []

    def get_book_page(self, babelio_id: str) -> FetchResult:
        self.book_calls.append(babelio_id)
        if self._page_error is not None:
            raise self._page_error
        return FetchResult(self._page, self._final_url)

    def get_full_summary(self, summary_type: int, obj_id: int, referer: str) -> FetchResult:
        self.summary_calls.append((summary_type, obj_id, referer))
        if self._summary_error is not None:
            raise self._summary_error
        return FetchResult(self._summary, self._final_url)


class FakePlugin:
    def __init__(self) -> None:
        self.cleaned: list[MetadataProtocol] = []
        self.cached_covers: list[tuple[str, str]] = []

    def clean_downloaded_metadata(self, mi: MetadataProtocol) -> None:
        self.cleaned.append(mi)

    def cache_identifier_to_cover_url(self, id_: str, url: str) -> None:
        self.cached_covers.append((id_, url))


class FakeLog:
    def __init__(self) -> None:
        self.records: list[tuple[str, tuple[object, ...]]] = []

    def info(self, *args: object) -> None:
        self.records.append(("info", args))

    def error(self, *args: object) -> None:
        self.records.append(("error", args))

    def exception(self, *args: object) -> None:
        self.records.append(("exception", args))


def _config(
    *,
    comments: bool = True,
    pubdate: bool = True,
    publisher: bool = True,
    rating: bool = True,
    series: bool = True,
    tags: bool = True,
    tag_relevance: dict[TagCategory, int] | None = None,
) -> WorkerConfig:
    return WorkerConfig(
        comments=comments,
        pubdate=pubdate,
        publisher=publisher,
        rating=rating,
        series=series,
        tags=tags,
        tag_relevance=(
            tag_relevance if tag_relevance is not None else dict.fromkeys(TagCategory, 12)
        ),
    )


def _context(
    client: FakeClient,
    *,
    config: WorkerConfig | None = None,
    abort: threading.Event | None = None,
    plugin: FakePlugin | None = None,
    date_to_datetime: DateConverter | None = None,
) -> tuple[WorkerContext, Queue[MetadataProtocol], FakePlugin]:
    queue: Queue[MetadataProtocol] = Queue()
    used_plugin = plugin if plugin is not None else FakePlugin()
    ctx = WorkerContext(
        client=client,
        plugin=used_plugin,
        result_queue=queue,
        abort=abort if abort is not None else threading.Event(),
        log=FakeLog(),
        metadata_factory=FakeMetadata,
        date_to_datetime=(
            date_to_datetime
            if date_to_datetime is not None
            else lambda d: datetime(d.year, d.month, d.day, tzinfo=UTC)
        ),
        config=config if config is not None else _config(),
    )
    return ctx, queue, used_plugin


def _run(target: SearchHit | str, ctx: WorkerContext, relevance: int = 0) -> Worker:
    worker = Worker(target, relevance, ctx)
    worker.run()
    return worker


def test_full_mapping_from_book_page() -> None:
    client = FakeClient(_load("book_chattam.html"), summary=_load("ajax_resume_voirplus.html"))
    ctx, queue, plugin = _context(client)

    worker = _run(_CHATTAM_ID, ctx, relevance=3)

    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    assert worker.result is mi
    assert worker.error is None
    assert mi.title == "Autre-Monde, tome 5 : Oz"
    assert mi.authors == ["Maxime Chattam"]
    assert mi.identifiers == {"babelio_id": _CHATTAM_ID, "isbn": "9782226244338"}
    assert mi.source_relevance == 3
    assert mi.languages == ["fra"]
    assert mi.series == "Autre-Monde"
    assert mi.series_index == 5.0
    assert mi.publisher == "Albin Michel / Wiz"
    assert mi.pubdate == datetime(2012, 11, 2, tzinfo=UTC)
    assert mi.rating == pytest.approx(8.42)
    assert "aventure" in mi.tags
    assert plugin.cached_covers == [
        (_CHATTAM_ID, "https://www.babelio.com/couv/CVT_CVT_Autre-Monde-Tome-5--Oz_6607.jpg")
    ]
    assert plugin.cleaned == [mi]


def test_disabled_toggles_leave_fields_unset() -> None:
    client = FakeClient(_load("book_chattam.html"), summary=_load("ajax_resume_voirplus.html"))
    ctx, queue, plugin = _context(
        client,
        config=_config(
            comments=False,
            pubdate=False,
            publisher=False,
            rating=False,
            series=False,
            tags=False,
        ),
    )

    _run(_CHATTAM_ID, ctx)

    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    assert mi.comments is None
    assert mi.pubdate is None
    assert mi.publisher is None
    assert mi.rating is None
    assert mi.series is None
    assert mi.series_index is None
    assert mi.tags == []
    # Identifiers, relevance, languages and cover caching are not toggle-gated.
    assert mi.identifiers == {"babelio_id": _CHATTAM_ID, "isbn": "9782226244338"}
    assert mi.languages == ["fra"]
    assert len(plugin.cached_covers) == 1
    # The truncated résumé toggle being off means no AJAX follow-up.
    assert client.summary_calls == []


def test_abort_before_run_queues_nothing() -> None:
    client = FakeClient(_load("book_chattam.html"))
    abort = threading.Event()
    abort.set()
    ctx, queue, _ = _context(client, abort=abort)

    worker = _run(_CHATTAM_ID, ctx)

    assert worker.result is None
    assert queue.empty()
    assert client.book_calls == []


def test_truncated_resume_fetches_full_text() -> None:
    client = FakeClient(_load("book_chattam.html"), summary=_load("ajax_resume_voirplus.html"))
    ctx, queue, _ = _context(client)

    _run(_CHATTAM_ID, ctx)

    assert client.summary_calls == [(1, 918135, _BOOK_URL)]
    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    assert mi.comments is not None
    assert mi.comments.startswith("La guerre avec les Cyniks terminée")
    assert "\n" in mi.comments


def test_non_truncated_resume_skips_ajax() -> None:
    # All saved book fixtures are truncated, so build a minimal complete-résumé page.
    page = (
        b'<link rel="canonical" href="https://www.babelio.com/livres/Slug/9">'
        b'<div class="livre_resume">A short complete summary.</div>'
    )
    client = FakeClient(page)
    ctx, queue, _ = _context(client)

    _run("Slug/9", ctx)

    assert client.summary_calls == []
    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    assert mi.comments == "A short complete summary."
    assert mi.series is None


def test_non_book_page_queues_nothing() -> None:
    client = FakeClient(_load("book_not_found_redirects_home.html"))
    ctx, queue, _ = _context(client)

    worker = _run("Unknown/0", ctx)

    assert worker.result is None
    assert queue.empty()


def test_blocked_book_page_records_error() -> None:
    err = BabelioBlocked("expired")
    client = FakeClient(b"", page_error=err)
    ctx, queue, _ = _context(client)

    worker = _run(_CHATTAM_ID, ctx)

    assert worker.error is err
    assert queue.empty()


def test_circuit_breaker_records_error() -> None:
    err = CircuitBreakerOpen(3600.0)
    client = FakeClient(b"", page_error=err)
    ctx, queue, _ = _context(client)

    worker = _run(_CHATTAM_ID, ctx)

    assert worker.error is err
    assert queue.empty()


def test_unexpected_book_page_error_is_swallowed() -> None:
    client = FakeClient(b"", page_error=RuntimeError("boom"))
    ctx, queue, _ = _context(client)

    worker = _run(_CHATTAM_ID, ctx)

    assert worker.error is None
    assert worker.result is None
    assert queue.empty()


def test_ajax_failure_falls_back_to_truncated_summary() -> None:
    client = FakeClient(
        _load("book_chattam.html"), summary_error=BabelioBlocked("expired during ajax")
    )
    ctx, queue, _ = _context(client)

    worker = _run(_CHATTAM_ID, ctx)

    # The page already succeeded — the failed follow-up must not lose the result or set error.
    assert worker.error is None
    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    # Falls back to the truncated résumé, which still carries the "Voir plus" marker.
    assert mi.comments is not None and mi.comments.endswith("Voir plus")
    assert "\n" not in mi.comments


def test_search_hit_target_with_empty_title_falls_back_to_hit_title() -> None:
    # A book page with an edition block but no <title> parses to an empty title.
    client = FakeClient(b'<div class="livre_refs grey_light"></div>', final_url=_BOOK_URL)
    ctx, queue, _ = _context(client)
    hit = SearchHit(babelio_id=_CHATTAM_ID, title="Hit Title", author="Maxime Chattam")

    _run(hit, ctx)

    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    assert mi.title == "Hit Title"
    assert mi.identifiers["babelio_id"] == _CHATTAM_ID


def test_tag_threshold_drops_low_relevance_tags() -> None:
    client = FakeClient(_load("book_chattam.html"))
    # 'suspense' has relevance 14; raise the genre threshold above it.
    ctx, queue, _ = _context(
        client,
        config=_config(tag_relevance={**dict.fromkeys(TagCategory, 12), TagCategory.GENRE: 15}),
    )

    _run(_CHATTAM_ID, ctx)

    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    assert "suspense" not in mi.tags
    assert "fantastique" in mi.tags  # relevance 27, well above the threshold


def test_pubdate_uses_injected_date_converter() -> None:
    client = FakeClient(_load("book_chattam.html"), summary=_load("ajax_resume_voirplus.html"))
    seen: list[date] = []
    sentinel = datetime(1999, 1, 1, 9, 30, tzinfo=UTC)

    def converter(d: date) -> datetime:
        seen.append(d)
        return sentinel

    ctx, queue, _ = _context(client, date_to_datetime=converter)

    _run(_CHATTAM_ID, ctx)

    mi = queue.get_nowait()
    assert isinstance(mi, FakeMetadata)
    # The worker hands the parsed date to the converter verbatim; tz semantics are Calibre's job.
    assert seen == [date(2012, 11, 2)]
    assert mi.pubdate is sentinel


def test_metadata_build_failure_is_swallowed() -> None:
    class RaisingPlugin(FakePlugin):
        def clean_downloaded_metadata(self, mi: MetadataProtocol) -> None:
            raise RuntimeError("boom")

    client = FakeClient(_load("book_chattam.html"), summary=_load("ajax_resume_voirplus.html"))
    ctx, queue, _ = _context(client, plugin=RaisingPlugin())

    worker = _run(_CHATTAM_ID, ctx)

    # A throw while building/cleaning must not kill the worker or surface as a block error.
    assert worker.result is None
    assert worker.error is None
    assert queue.empty()
    assert isinstance(ctx.log, FakeLog)
    assert any(level == "exception" for level, _ in ctx.log.records)
