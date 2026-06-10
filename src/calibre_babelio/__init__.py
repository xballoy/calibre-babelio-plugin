"""Plugin entry point: the `Babelio(Source)` class Calibre loads."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from calibre.ebooks.metadata.sources.base import Source

if TYPE_CHECKING:
    from collections.abc import Mapping
    from queue import Queue
    from threading import Event

    from .config import ConfigWidget
    from .worker import LogProtocol, MetadataProtocol, Worker

    def _(text: str) -> str: ...
    def load_translations() -> None: ...


load_translations()


_BASE_URL = "https://www.babelio.com"
_BOOK_URL_RE = re.compile(r"babelio\.com/livres/(?P<id>[^?#]+?/\d+)")
_POLL_INTERVAL = 0.1


class Babelio(Source):  # type: ignore[misc]
    name = "Babelio"
    description = _("Downloads metadata and covers from Babelio (babelio.com)")
    author = "Xavier Balloy"
    version = (0, 1, 0)
    minimum_calibre_version = (6, 0, 0)

    capabilities = frozenset({"identify", "cover"})
    touched_fields = frozenset(
        {
            "title",
            "authors",
            "identifier:babelio_id",
            "identifier:isbn",
            "comments",
            "rating",
            "publisher",
            "pubdate",
            "series",
            "series_index",
            "tags",
            "languages",
        }
    )
    has_html_comments = True
    supports_gzip_transfer_encoding = True

    def is_customizable(self) -> bool:
        return True

    def config_widget(self) -> ConfigWidget:
        from .config import ConfigWidget

        return ConfigWidget()

    def save_settings(self, config_widget: ConfigWidget) -> None:
        config_widget.save_settings()

    def get_book_url(
        self, identifiers: Mapping[str, str]
    ) -> tuple[str, str, str] | None:
        babelio_id = identifiers.get("babelio_id")
        if babelio_id:
            return ("babelio_id", babelio_id, f"{_BASE_URL}/livres/{babelio_id}")
        return None

    def id_from_url(self, url: str) -> tuple[str, str] | None:
        match = _BOOK_URL_RE.search(url)
        if match:
            return ("babelio_id", match.group("id"))
        return None

    def get_cached_cover_url(self, identifiers: Mapping[str, str]) -> str | None:
        babelio_id = identifiers.get("babelio_id")
        if not babelio_id:
            return None
        url: str | None = self.cached_identifier_to_cover_url(babelio_id)
        return url

    def identify(
        self,
        log: LogProtocol,
        result_queue: Queue[MetadataProtocol],
        abort: Event,
        title: str | None = None,
        authors: list[str] | None = None,
        identifiers: Mapping[str, str] = {},
        timeout: int = 30,
    ) -> str | None:
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.utils.date import parse_only_date

        from ._browser import CalibreBrowserAdapter
        from .client import BabelioClient
        from .config import prefs, worker_config_from_prefs
        from .errors import (
            BabelioBlocked,
            CircuitBreakerOpen,
            circuit_open_message,
            cookie_expired_message,
        )
        from .parser import parse_search_results
        from .query import build_search_query
        from .worker import Worker, WorkerContext

        client = BabelioClient(
            CalibreBrowserAdapter(self.browser),
            prefs["jsts_token"],
            prefs["user_agent"],
            min_interval=prefs["min_interval"],
        )
        ctx = WorkerContext(
            client=client,
            plugin=self,
            result_queue=result_queue,
            abort=abort,
            log=log,
            metadata_factory=Metadata,
            date_to_datetime=lambda d: parse_only_date(
                d.isoformat(), assume_utc=False, as_utc=False
            ),
            config=worker_config_from_prefs(),
        )

        babelio_id = identifiers.get("babelio_id")
        if babelio_id:
            workers = [Worker(babelio_id, 0, ctx)]
        else:
            query = build_search_query(
                title=title, authors=authors, isbn=identifiers.get("isbn")
            )
            if not query:
                log.info("No usable title/author/ISBN to search Babelio")
                return None
            try:
                search = client.search(query)
            except BabelioBlocked:
                return cookie_expired_message()
            except CircuitBreakerOpen:
                return circuit_open_message()

            hits = parse_search_results(search.body)
            if not hits:
                log.info("No Babelio search results for", query)
                return None
            workers = [
                Worker(hit, relevance, ctx)
                for relevance, hit in enumerate(hits[: prefs["max_results"]])
            ]

        return self._run_workers(workers, abort)

    def _run_workers(self, workers: list[Worker], abort: Event) -> str | None:
        from .errors import CircuitBreakerOpen, circuit_open_message, cookie_expired_message

        for worker in workers:
            worker.start()
        while not abort.is_set() and any(worker.is_alive() for worker in workers):
            time.sleep(_POLL_INTERVAL)

        if abort.is_set():
            # Abandoned workers may still be writing `result`/`error`; don't read them.
            return None
        if any(worker.result is not None for worker in workers):
            return None
        if workers and all(worker.error is not None for worker in workers):
            if any(isinstance(worker.error, CircuitBreakerOpen) for worker in workers):
                return circuit_open_message()
            return cookie_expired_message()
        return None

    def download_cover(
        self,
        log: LogProtocol,
        result_queue: Queue[tuple[Babelio, bytes]],
        abort: Event,
        title: str | None = None,
        authors: list[str] | None = None,
        identifiers: Mapping[str, str] = {},
        timeout: int = 30,
        get_best_cover: bool = False,
    ) -> None:
        from ._browser import CalibreBrowserAdapter
        from .client import BabelioClient
        from .config import prefs
        from .errors import BabelioBlocked, CircuitBreakerOpen

        if not prefs["allow_covers"]:
            log.info("Cover download disabled in Babelio settings")
            return

        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            cached_url = self._cover_url_via_identify(
                log, abort, title=title, authors=authors,
                identifiers=identifiers, timeout=timeout,
            )
        if abort.is_set():
            return
        if cached_url is None:
            log.info("No Babelio cover found for", title)
            return

        client = BabelioClient(
            CalibreBrowserAdapter(self.browser),
            prefs["jsts_token"],
            prefs["user_agent"],
            min_interval=prefs["min_interval"],
        )
        log.info("Downloading Babelio cover from:", cached_url)
        try:
            cdata = client.fetch_image(cached_url, timeout=timeout)
        except (BabelioBlocked, CircuitBreakerOpen) as exc:
            log.error("Babelio blocked the cover download:", exc)
            return
        except Exception:
            log.exception("Failed to download Babelio cover from:", cached_url)
            return
        if cdata:
            result_queue.put((self, cdata))

    def _cover_url_via_identify(
        self,
        log: LogProtocol,
        abort: Event,
        *,
        title: str | None,
        authors: list[str] | None,
        identifiers: Mapping[str, str],
        timeout: int,
    ) -> str | None:
        from queue import Empty, Queue

        log.info("No cached Babelio cover; running identify first")
        rq: Queue[MetadataProtocol] = Queue()
        self.identify(
            log, rq, abort, title=title, authors=authors,
            identifiers=identifiers, timeout=timeout,
        )
        if abort.is_set():
            return None
        results = []
        while True:
            try:
                results.append(rq.get_nowait())
            except Empty:
                break
        results.sort(
            key=self.identify_results_keygen(
                title=title, authors=authors, identifiers=identifiers
            )
        )
        for mi in results:
            cached_url = self.get_cached_cover_url(mi.identifiers)
            if cached_url is not None:
                return cached_url
        return None


if __name__ == "__main__":
    from calibre.ebooks.metadata.sources.test import (
        authors_test,
        series_test,
        test_identify_plugin,
        title_test,
    )

    test_identify_plugin(
        Babelio.name,
        [
            (
                {"identifiers": {"babelio_id": "Chattam-Autre-Monde-tome-5--Oz/401283"}},
                [
                    title_test("Autre-Monde", exact=False),
                    authors_test(["Maxime Chattam"]),
                    series_test("Autre-Monde", 5),
                ],
            ),
            (
                {
                    "title": "L'élégance du hérisson",
                    "authors": ["Muriel Barbery"],
                    "identifiers": {"isbn": "9782070396733"},
                },
                [
                    title_test("hérisson", exact=False),
                    authors_test(["Muriel Barbery"]),
                ],
            ),
        ],
    )
