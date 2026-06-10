from __future__ import annotations

import threading
from typing import TYPE_CHECKING, cast

from calibre_babelio import Babelio

if TYPE_CHECKING:
    from calibre_babelio.worker import Worker


class AbandonedWorker:
    """A still-running worker whose `result`/`error` are unsafe to read after abort."""

    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return True

    @property
    def result(self) -> object:
        raise AssertionError("result read while the worker may still be running")

    @property
    def error(self) -> object:
        raise AssertionError("error read while the worker may still be running")


def test_run_workers_abort_returns_without_reading_results() -> None:
    plugin = Babelio()
    abort = threading.Event()
    abort.set()
    workers = [AbandonedWorker(), AbandonedWorker()]

    message = plugin._run_workers(cast("list[Worker]", workers), abort)

    assert message is None
    assert all(worker.started for worker in workers)
