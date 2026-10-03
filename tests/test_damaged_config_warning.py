"""Handling a race-info file whose fields no longer line up.

The format is positional, so a file whose fields moved down a line still parses: the
loader reads each value into the wrong name and the interface then presents them as
settings somebody chose. The only way to notice is an anchor field holding a value it
could never legitimately hold. Two things follow from noticing: say so on load, and do
not quietly write the misread values back over the only copy of the real ones.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from app import main_window as main_window_module
from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """MainWindow would otherwise load this machine's own fpg_info.txt."""
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


class _Questions:
    """Stands in for QMessageBox.question, answering by dialog title."""

    def __init__(self) -> None:
        self.titles: list[str] = []
        self.replies: dict[str, QMessageBox.StandardButton] = {}

    def __call__(
        self, _parent: object, title: str, _text: str, *args: object
    ) -> QMessageBox.StandardButton:
        self.titles.append(title)
        # Yes by default, so the exit confirmation does not block a close test.
        return self.replies.get(title, QMessageBox.StandardButton.Yes)


@pytest.fixture
def questions(monkeypatch: pytest.MonkeyPatch) -> _Questions:
    shown = _Questions()
    monkeypatch.setattr(QMessageBox, "question", shown)
    return shown


@pytest.fixture
def warnings(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Collect the modal errors instead of showing them."""
    shown: list[tuple[str, str]] = []

    def _record(_parent: object, title: str, text: str, *args: object) -> None:
        shown.append((title, text))

    monkeypatch.setattr(QMessageBox, "critical", _record)
    return shown


def _write_config(win: MainWindow, directory: str, shift: bool) -> str:
    """Save the current config, optionally shifting every field down one line."""
    path = Path(directory) / "fpg_info.txt"
    win._save_race_info_to_path(str(path))
    if shift:
        lines = path.read_text(encoding="utf-8").split("\n")
        # Exactly what a value with a trailing line break used to produce.
        path.write_text("\n".join([*lines[:1], "", *lines[1:]]), encoding="utf-8")
    return str(path)


class TestDamagedConfigWarning:
    def test_a_shifted_file_raises_an_error(
        self, warnings: list[tuple[str, str]]
    ) -> None:
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=True)
                win._load_race_info_from_path(path)
            assert len(warnings) == 1
            title, text = warnings[0]
            assert title == "Race info file damaged"
            # Name the file, the anchor that failed and the likely cause.
            assert path in text
            assert "race type" in text
            assert "line break" in text
        finally:
            win.deleteLater()

    def test_a_consistent_file_raises_nothing(
        self, warnings: list[tuple[str, str]]
    ) -> None:
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=False)
                win._load_race_info_from_path(path)
            assert warnings == []
        finally:
            win.deleteLater()

    def test_the_key_value_format_is_not_checked(
        self, warnings: list[tuple[str, str]]
    ) -> None:
        """It is tagged, so it cannot shift and has no anchors to check."""
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "kv.txt"
                path.write_text(
                    "# FPG Race Info\nRaceName=Race\nEnd\n", encoding="utf-8"
                )
                win._load_race_info_from_path(str(path))
            assert warnings == []
        finally:
            win.deleteLater()


_DAMAGED_TITLE = "Damaged race info file"


class TestSavingOverADamagedFile:
    """A save must not take the only copy of the real settings with it."""

    def test_a_first_run_saves_without_asking(self, questions: _Questions) -> None:
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "fpg_info.txt"
                win._save_race_info_to_path(str(path))
                assert path.exists()
            assert questions.titles == []
        finally:
            win.deleteLater()

    def test_a_sound_file_is_overwritten_without_asking(
        self, questions: _Questions
    ) -> None:
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=False)
                win._save_race_info_to_path(path)
            assert questions.titles == []
        finally:
            win.deleteLater()

    def test_an_empty_file_is_overwritten_without_asking(
        self, questions: _Questions
    ) -> None:
        """An empty or half-written file has no anchor, so it is not damaged."""
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "fpg_info.txt"
                path.write_text("", encoding="utf-8")
                win._save_race_info_to_path(str(path))
                assert path.read_text(encoding="utf-8") != ""
            assert questions.titles == []
        finally:
            win.deleteLater()

    def test_declining_leaves_a_damaged_file_byte_identical(
        self, questions: _Questions
    ) -> None:
        questions.replies[_DAMAGED_TITLE] = QMessageBox.StandardButton.No
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=True)
                before = Path(path).read_bytes()
                win._save_race_info_to_path(path)
                assert Path(path).read_bytes() == before
            assert questions.titles == [_DAMAGED_TITLE]
        finally:
            win.deleteLater()

    def test_accepting_overwrites_it(self, questions: _Questions) -> None:
        questions.replies[_DAMAGED_TITLE] = QMessageBox.StandardButton.Yes
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=True)
                before = Path(path).read_bytes()
                win._save_race_info_to_path(path)
                after = Path(path).read_bytes()
            assert after != before
            assert questions.titles == [_DAMAGED_TITLE]
        finally:
            win.deleteLater()

    def test_the_question_names_the_file_and_the_anchor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        asked: list[tuple[str, str]] = []

        def _question(
            _parent: object, title: str, text: str, *args: object
        ) -> QMessageBox.StandardButton:
            asked.append((title, text))
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "question", _question)
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=True)
                win._save_race_info_to_path(path)
            assert len(asked) == 1
            _title, text = asked[0]
            assert path in text
            assert "race type" in text
        finally:
            win.deleteLater()

    def test_exiting_does_not_overwrite_a_damaged_file(
        self, questions: _Questions, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The automatic save on exit goes through the same guard."""
        questions.replies[_DAMAGED_TITLE] = QMessageBox.StandardButton.No
        win = MainWindow()
        try:
            with tempfile.TemporaryDirectory() as td:
                path = _write_config(win, td, shift=True)
                # closeEvent saves to app_path("fpg_info.txt"), which is a tracked file
                # in this repository - point it at the temp copy instead.
                monkeypatch.setattr(
                    main_window_module,
                    "app_path",
                    lambda *parts: Path(td).joinpath(*parts),
                )
                before = Path(path).read_bytes()
                win.closeEvent(QCloseEvent())
                assert Path(path).read_bytes() == before
            # The exit confirmation, then the overwrite question.
            assert questions.titles == ["Exit", _DAMAGED_TITLE]
        finally:
            win.deleteLater()
