from __future__ import annotations

import threading
from typing import TYPE_CHECKING, cast

from calibre_babelio import Babelio
from calibre_babelio.errors import (
    BabelioBlocked,
    BabelioTokenMissing,
    CircuitBreakerOpen,
    circuit_open_message,
    cookie_expired_message,
    token_missing_message,
)

if TYPE_CHECKING:
    from calibre_babelio.worker import Worker


class StubWorker:
    def __init__(self, error: object = None, result: object = None) -> None:
        self.error = error
        self.result = result

    def start(self) -> None:
        pass

    def is_alive(self) -> bool:
        return False


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


def test_run_workers_token_missing_error_returns_token_missing_message() -> None:
    plugin = Babelio()
    abort = threading.Event()
    workers = [StubWorker(error=BabelioTokenMissing("no token configured"))]

    message = plugin._run_workers(cast("list[Worker]", workers), abort)

    assert message == token_missing_message()


def test_run_workers_rejected_token_error_returns_cookie_expired_message() -> None:
    plugin = Babelio()
    abort = threading.Event()
    workers = [StubWorker(error=BabelioBlocked("rejected"))]

    message = plugin._run_workers(cast("list[Worker]", workers), abort)

    assert message == cookie_expired_message()


def test_run_workers_circuit_breaker_error_returns_circuit_open_message() -> None:
    plugin = Babelio()
    abort = threading.Event()
    workers = [StubWorker(error=CircuitBreakerOpen(3600))]

    message = plugin._run_workers(cast("list[Worker]", workers), abort)

    assert message == circuit_open_message()
