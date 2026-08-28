"""Closing the window must stop background workers first.

Regression for the crash where exiting while a worker thread was still running (e.g. a
live-stats upload blocked in DNS getaddrinfo) let Qt destroy a running QThread, aborting
the process with "QThread: Destroyed while thread is still running".
"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


class _BlockingWorker(QThread):
    def run(self) -> None:
        self.msleep(300)


def test_closeevent_waits_for_running_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    win = MainWindow()
    try:
        worker = _BlockingWorker()
        worker.start()
        assert worker.isRunning()
        win._worker = worker  # type: ignore[assignment]

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        monkeypatch.setattr(win, "_save_race_info_to_path", lambda path: None)

        event = QCloseEvent()
        win.closeEvent(event)

        # The worker was waited on, not left running to be destroyed on teardown.
        assert not worker.isRunning()
        assert event.isAccepted()
    finally:
        win.deleteLater()


def test_stop_workers_terminates_when_wait_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win = MainWindow()
    try:
        calls = {"terminated": False, "waited": False}

        class _WedgedWorker:
            def isRunning(self) -> bool:  # noqa: N802  (mirrors QThread's API)
                return True

            def quit(self) -> None:
                pass

            def wait(self, *_a: int) -> bool:
                calls["waited"] = True
                return False  # never finishes within the timeout

            def terminate(self) -> None:
                calls["terminated"] = True

        win._worker = _WedgedWorker()  # type: ignore[assignment]
        win._ftp_worker = None

        win._stop_workers()

        assert calls["waited"]
        assert calls["terminated"]
    finally:
        win.deleteLater()
