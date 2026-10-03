"""A line break inside a race-info value must never reach fpg_info.txt.

Regression for the corruption where an HTML snippet pasted into the Sponsor field
carried a trailing newline: the save wrote it raw, so that one field became two
physical lines and the positional loader read every following field one line late.
The damage then stuck, because the misread values were saved back in the same shape.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit

from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)

# Fields that take free text a user is likely to paste into.
_TEXT_FIELDS = ("sponsor", "race_name", "weather", "bottom_text", "track_conditions")


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """MainWindow would otherwise load this machine's own fpg_info.txt."""
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


def _saved_lines(win: MainWindow) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "fpg_info.txt")
        win._save_race_info_to_path(path)
        return Path(path).read_text(encoding="utf-8").split("\n")


class TestFieldsRejectLineBreaks:
    """The widgets drop a break where it enters."""

    def test_paste_with_a_trailing_newline_is_cleaned(self) -> None:
        win = MainWindow()
        try:
            edit = win.findChild(QLineEdit, "sponsor")
            assert edit is not None
            edit.setText("<div>logo</div>")
            # insert() is what QLineEdit.paste() uses, and Qt keeps the newline.
            edit.insert("\n")
            assert edit.text() == "<div>logo</div>"
            assert win._cfg.sponsor == "<div>logo</div>"
        finally:
            win.deleteLater()

    def test_multiline_paste_collapses_to_one_line(self) -> None:
        win = MainWindow()
        try:
            edit = win.findChild(QLineEdit, "race_name")
            assert edit is not None
            edit.insert("Race\nSecond line\n")
            assert "\n" not in edit.text()
            assert win._cfg.race_name == "Race Second line"
        finally:
            win.deleteLater()

    def test_sync_shows_what_will_be_saved(self) -> None:
        win = MainWindow()
        try:
            win._cfg.weather = "sunny\nand warm"
            win._sync_ui_from_cfg()
            edit = win.findChild(QLineEdit, "weather")
            assert edit is not None
            assert edit.text() == "sunny and warm"
        finally:
            win.deleteLater()


class TestSaveKeepsOneLinePerField:
    """And the save folds anything that reached the config another way."""

    def test_file_length_does_not_grow(self) -> None:
        win = MainWindow()
        try:
            win._cfg.sponsor = "<div>logo</div>"
            clean = _saved_lines(win)
            # Bypass the widgets entirely: the save is the backstop.
            win._cfg.sponsor = "<div>logo</div>\n"
            assert len(_saved_lines(win)) == len(clean)
        finally:
            win.deleteLater()

    def test_race_type_stays_on_the_thirteenth_line(self) -> None:
        win = MainWindow()
        try:
            win._cfg.sponsor = "<div>logo</div>\n"
            # The 13th line is the anchor the whole positional format hangs on; it is
            # what proved the live file had shifted.
            assert _saved_lines(win)[12] == win._cfg.race_type
        finally:
            win.deleteLater()

    @pytest.mark.parametrize("field", _TEXT_FIELDS)
    def test_round_trip_survives_a_break_in_any_text_field(self, field: str) -> None:
        win = MainWindow()
        try:
            win._cfg.race_name = "Race Name"
            win._cfg.race_date = "1 May 2026"
            win._cfg.race_place = "Somewhere"
            win._cfg.main_referee = "Referee"
            setattr(win._cfg, field, "first\nsecond")
            with tempfile.TemporaryDirectory() as td:
                path = str(Path(td) / "fpg_info.txt")
                win._save_race_info_to_path(path)
                other = MainWindow()
                try:
                    other._load_race_info_from_path(path)
                    assert getattr(other._cfg, field) == "first second"
                    # Nothing below the damaged field moved.
                    expected_name = (
                        "first second" if field == "race_name" else "Race Name"
                    )
                    assert other._cfg.race_name == expected_name
                    assert other._cfg.race_date == "1 May 2026"
                    assert other._cfg.race_place == "Somewhere"
                    assert other._cfg.main_referee == "Referee"
                    assert other._cfg.race_type == win._cfg.race_type
                    assert other._cfg.referee_label == win._cfg.referee_label
                finally:
                    other.deleteLater()
        finally:
            win.deleteLater()
