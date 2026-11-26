"""A run auto-refresh started reports its errors in the log alone.

The maintainer, 2026-11-26: a dialog's own event loop kept the timer firing, so every
tick stacked one more over it -- five in five seconds at a one-second interval before
the first mark. A run started by hand keeps its dialog.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox

from app.config import RACE_TYPE_NUMBER_OF_TRIES
from app.main_window import MainWindow, _FTPWorker

_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The title of every message box the window opens, instead of opening it."""
    shown: list[str] = []
    for kind in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(
            QMessageBox, kind, lambda _parent, title, *_a, **_k: shown.append(title)
        )
    return shown


@pytest.fixture
def window(tmp_path: Path, dialogs: list[str]) -> Iterator[MainWindow]:
    """A race before its first mark: no results.txt yet."""
    (tmp_path / "start.txt").write_text(
        "1#Ivanov Ivan#G#1#1#1990#T#C##0 00:00:00.000#\n", encoding="utf-8"
    )
    (tmp_path / "groups.txt").write_text("G#20711 10:0:0.000#\n", encoding="utf-8")
    win = MainWindow()
    cfg = win._cfg
    cfg.start_protocol_file = str(tmp_path / "start.txt")
    cfg.group_time_file = str(tmp_path / "groups.txt")
    cfg.finish_time_file = str(tmp_path / "results.txt")
    cfg.group_protocol_file = str(tmp_path / "grp.html")
    cfg.absolute_protocol_file = str(tmp_path / "abs.html")
    cfg.use_interface_logger = True
    cfg.use_file_logger = False
    try:
        yield win
    finally:
        if win._timer is not None:
            win._timer.stop()
        for worker in (win._worker, win._ftp_worker):
            if worker is not None:
                worker.wait()
        # Deliver what a run still has queued while the dialogs are patched, so it
        # cannot open a real one in a later test.
        _app.processEvents()
        win.deleteLater()


def _log(win: MainWindow) -> list[str]:
    return [win._log_list.item(i).text() for i in range(win._log_list.count())]


def _idle(win: MainWindow) -> bool:
    return win._worker is None or not win._worker.isRunning()


def _wait(done: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 10
    while not done() and time.monotonic() < deadline:
        _app.processEvents()
        time.sleep(0.005)


def _auto_refresh(win: MainWindow, done: Callable[[], bool]) -> int:
    """Auto-refresh through its own handler until three ticks have gone and ``done``
    holds; the number of ticks."""
    win._spin_refresh.setValue(1)
    win._on_refresh_toggled(True)
    assert win._timer is not None
    ticks: list[int] = []
    win._timer.timeout.connect(lambda: ticks.append(1))
    win._timer.start(20)  # the spin box goes down to a second; the test need not
    _wait(lambda: len(ticks) >= 3 and done())
    win._timer.stop()
    return len(ticks)


def _errors(win: MainWindow, text: str) -> list[str]:
    return [line for line in _log(win) if line.startswith("ERROR: ") and text in line]


def test_a_failing_run_of_auto_refresh_opens_no_dialog_and_logs_the_error(
    window: MainWindow, dialogs: list[str]
) -> None:
    ticks = _auto_refresh(
        window, lambda: _idle(window) and bool(_errors(window, "results.txt"))
    )

    assert ticks >= 3
    assert dialogs == []
    assert _errors(window, "results.txt")


def test_a_run_started_by_hand_after_auto_refresh_keeps_its_dialog(
    window: MainWindow, dialogs: list[str]
) -> None:
    _auto_refresh(
        window, lambda: _idle(window) and bool(_errors(window, "results.txt"))
    )
    assert window._worker is not None
    window._worker.wait()
    _app.processEvents()

    window._btn_generate.click()
    _wait(lambda: _idle(window) and bool(dialogs))

    assert dialogs == ["Error"]
    assert _errors(window, "results.txt")


def test_a_download_by_hand_after_auto_refresh_keeps_its_dialog(
    window: MainWindow, dialogs: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _auto_refresh(
        window, lambda: _idle(window) and bool(_errors(window, "results.txt"))
    )
    assert window._worker is not None
    window._worker.wait()
    _app.processEvents()
    window._cfg.ftp_path = "ftp://127.0.0.1:9/"  # never reached: run is replaced
    window._cfg.result_times_action = "Download"
    monkeypatch.setattr(_FTPWorker, "run", lambda self: self.error.emit("no server"))

    window._on_ftp_download()
    assert window._ftp_worker is not None
    window._ftp_worker.wait()
    _app.processEvents()

    assert _errors(window, "no server")
    assert dialogs == ["Error"]


@pytest.mark.parametrize("refusal", ["Invalid attempt rules", "FTP not configured"])
def test_a_run_auto_refresh_cannot_start_says_why_in_the_log_alone(
    window: MainWindow, dialogs: list[str], refusal: str
) -> None:
    if refusal == "FTP not configured":
        window._cfg.result_times_action = "Download"
        window._cfg.ftp_path = ""
    else:
        window._combo_race_type.setCurrentText(RACE_TYPE_NUMBER_OF_TRIES)
        window._attempt_rules_editor._add()
        values = window._attempt_rules_editor.table.cellWidget(0, 2)
        assert isinstance(values, QLineEdit)  # the rule's values: an invalid list
        values.setText("1,,2")

    _auto_refresh(window, lambda: len(_errors(window, refusal)) >= 3)

    assert dialogs == []
    assert len(_errors(window, refusal)) >= 3
    assert window._worker is None

    window._btn_generate.click()
    assert dialogs == [refusal]
