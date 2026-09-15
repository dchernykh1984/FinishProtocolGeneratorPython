"""The start board is wired to the button and refreshed by every generation."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.config import RaceConfig
from app.main_window import MainWindow, _GenerateWorker
from app.time_trial import StartEntry, now_seconds
from app.time_trial_window import TimeTrialWindow

_app = QApplication.instance() or QApplication(sys.argv)

BASE = now_seconds(datetime(2026, 9, 15, 10, 0, 0))
_DAY = 20711  # 2026-09-15 in days since the epoch, the scale the timing files use


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep MainWindow from reading whatever fpg_info.txt is on this machine."""
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


@pytest.fixture
def window():
    win = MainWindow()
    try:
        yield win
    finally:
        win.deleteLater()


def _race_files(tmp_path: Path) -> RaceConfig:
    """A tiny race: one group at 10:00, three riders a minute apart."""
    (tmp_path / "start.txt").write_text(
        "1#Ivanov Ivan#G#1#1#1990#T#C##0 00:00:00.000#\n"
        "2#Petrov Petr#G#1#1#1990#T#C##0 00:01:00.000#\n"
        "3#Sidorov Sidor#G#1#1#1990#T#C##0 00:02:00.000#\n",
        encoding="utf-8",
    )
    (tmp_path / "groups.txt").write_text(f"G#{_DAY} 10:0:0.000#\n", encoding="utf-8")
    (tmp_path / "results.txt").write_text("", encoding="utf-8")
    cfg = RaceConfig()
    cfg.start_protocol_file = str(tmp_path / "start.txt")
    cfg.group_time_file = str(tmp_path / "groups.txt")
    cfg.finish_time_file = str(tmp_path / "results.txt")
    cfg.group_protocol_file = str(tmp_path / "grp.html")
    cfg.absolute_protocol_file = str(tmp_path / "abs.html")
    cfg.use_interface_logger = False
    cfg.use_file_logger = False
    return cfg


class TestButton:
    def test_the_main_tab_offers_the_button(self, window) -> None:
        assert window._btn_time_trial.text() == "Open Time Trial Window"

    def test_pressing_it_opens_the_board(self, window) -> None:
        window._btn_time_trial.click()
        assert isinstance(window._time_trial_window, TimeTrialWindow)
        assert window._time_trial_window.isVisible()

    def test_pressing_it_again_reuses_the_same_board(self, window) -> None:
        window._btn_time_trial.click()
        first = window._time_trial_window
        window._btn_time_trial.click()
        assert window._time_trial_window is first

    def test_a_board_opened_later_still_shows_the_last_schedule(self, window) -> None:
        entries = [StartEntry("1", "Ivanov Ivan", BASE)]
        window._on_time_trial_ready(entries)
        window._btn_time_trial.click()
        assert window._time_trial_window._entries == entries

    def test_the_board_closes_with_the_application(self, window) -> None:
        window._btn_time_trial.click()
        # Parented to the main window, so it is not left behind as an orphan window.
        assert window._time_trial_window.parent() is window


class TestRefreshOnGeneration:
    def test_a_generation_publishes_the_start_schedule(self, tmp_path) -> None:
        cfg = _race_files(tmp_path)
        received: list[list[StartEntry]] = []
        worker = _GenerateWorker(cfg)
        worker.time_trial_ready.connect(received.append)
        worker.run()

        assert len(received) == 1
        entries = received[0]
        assert [e.competitor_id for e in entries] == ["1", "2", "3"]
        assert [e.start_time - BASE for e in entries] == [0.0, 60.0, 120.0]
        assert entries[0].name == "Ivanov Ivan"

    def test_the_schedule_reaches_an_open_board(self, window, tmp_path) -> None:
        window._btn_time_trial.click()
        cfg = _race_files(tmp_path)
        worker = _GenerateWorker(cfg)
        worker.time_trial_ready.connect(window._on_time_trial_ready)
        worker.run()

        assert len(window._time_trial_window._entries) == 3

    def test_regenerating_replaces_the_previous_schedule(
        self, window, tmp_path
    ) -> None:
        window._on_time_trial_ready([StartEntry("99", "Stale Rider", BASE)])
        cfg = _race_files(tmp_path)
        worker = _GenerateWorker(cfg)
        worker.time_trial_ready.connect(window._on_time_trial_ready)
        worker.run()

        bibs = [e.competitor_id for e in window._time_trial_entries]
        assert "99" not in bibs
        assert bibs == ["1", "2", "3"]

    def test_the_schedule_is_published_before_any_later_step_can_fail(
        self, tmp_path
    ) -> None:
        # Writing the protocol into a directory that does not exist fails the run; the
        # board still has to refresh, because its two input files were already read.
        cfg = _race_files(tmp_path)
        cfg.group_protocol_file = str(tmp_path / "missing" / "grp.html")
        received: list[list[StartEntry]] = []
        errors: list[str] = []
        worker = _GenerateWorker(cfg)
        worker.time_trial_ready.connect(received.append)
        worker.error.connect(errors.append)
        worker.run()

        assert errors
        assert len(received) == 1
