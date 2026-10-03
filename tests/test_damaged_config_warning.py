"""Loading a shifted race-info file must say so instead of looking normal.

The format is positional, so a file whose fields moved down a line still parses: the
loader reads each value into the wrong name and the interface then presents them as
settings somebody chose. The only way to notice is an anchor field holding a value it
could never legitimately hold.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """MainWindow would otherwise load this machine's own fpg_info.txt."""
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


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
