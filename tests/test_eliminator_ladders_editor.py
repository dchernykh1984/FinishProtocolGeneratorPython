"""The ladders table: it is an editor for a file, so every edit has to reach it."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QSpinBox

from app.eliminator_ladders_editor import EliminatorLaddersEditor

_app = QApplication.instance() or QApplication(sys.argv)

_START = "\n".join(
    (
        "101#Rider A#Men#1#1#1990#Team#City##1#",
        "102#Rider B#Men#1#1#1990#Team#City##2#",
        "201#Rider C#Women#1#1#1990#Team#City##1#",
    )
)


def _editor(tmp_path: Path, ladders: str = "", start: str = _START):
    (tmp_path / "start.txt").write_text(start, encoding="utf-8")
    if ladders:
        (tmp_path / "ladders.txt").write_text(ladders, encoding="utf-8")
    editor = EliminatorLaddersEditor()
    editor.set_files(str(tmp_path / "ladders.txt"), str(tmp_path / "start.txt"))
    return editor


def _saved(tmp_path: Path) -> list[str]:
    return (tmp_path / "ladders.txt").read_text(encoding="utf-8").splitlines()


def _name(editor: EliminatorLaddersEditor, row: int) -> QLineEdit:
    widget = editor.table.cellWidget(row, 0)
    assert isinstance(widget, QLineEdit)
    return widget


def _size(editor: EliminatorLaddersEditor, row: int) -> QComboBox:
    widget = editor.table.cellWidget(row, 1)
    assert isinstance(widget, QComboBox)
    return widget


def _rounds(editor: EliminatorLaddersEditor, row: int) -> QSpinBox:
    widget = editor.table.cellWidget(row, 2)
    assert isinstance(widget, QSpinBox)
    return widget


class TestLoading:
    def test_a_missing_file_is_an_empty_table(self, tmp_path: Path) -> None:
        # The first finals of an event start from no file at all.
        editor = _editor(tmp_path)
        assert editor.table.rowCount() == 0
        assert editor.rows() == []

    def test_a_file_fills_the_table(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\nWomen#2#1#\n")
        assert editor.rows() == [("Men", "4", "2"), ("Women", "2", "1")]

    def test_a_blank_row_loads_blank(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men###\n")
        assert editor.rows() == [("Men", "", "")]

    def test_a_line_with_no_group_is_dropped(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "#4#2#\n")
        assert editor.rows() == []

    def test_an_unsupported_heat_size_loads_blank(self, tmp_path: Path) -> None:
        # Only 2 and 4 can be ridden, so an 8 is shown as not chosen yet rather
        # than offered back as though the app would honour it.
        editor = _editor(tmp_path, "Men#8#2#\n")
        assert editor.rows() == [("Men", "", "2")]

    def test_a_round_count_too_deep_is_clamped_not_blanked(
        self, tmp_path: Path
    ) -> None:
        # Blanking it would be saved back on the next keystroke and the referee's
        # figure would be gone, so the nearest legal depth is shown instead.
        editor = _editor(tmp_path, "Men#4#99#\n")
        assert editor.rows() == [("Men", "4", "5")]
        assert "rounds at most 5" in editor.status.text()

    def test_an_adjusted_row_names_its_group(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\nWomen#8#2#\n")
        assert "Women" in editor.status.text()
        assert "Men," not in editor.status.text()

    def test_a_round_count_that_is_not_a_number_loads_blank(
        self, tmp_path: Path
    ) -> None:
        editor = _editor(tmp_path, "Men#4#x#\n")
        assert editor.rows() == [("Men", "4", "")]

    def test_loading_does_not_write_the_file_back(self, tmp_path: Path) -> None:
        _editor(tmp_path, "Men#8#2#\n")
        # The 8 is not a ladder, but the referee's file is not rewritten behind them.
        assert _saved(tmp_path) == ["Men#8#2#"]


class TestEditing:
    def test_choosing_a_shape_saves_it(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men###\n")
        _size(editor, 0).setCurrentText("4")
        _rounds(editor, 0).setValue(2)
        assert _saved(tmp_path) == ["Men#4#2#"]

    def test_renaming_a_group_saves_it(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        _name(editor, 0).setText("Juniors")
        assert _saved(tmp_path) == ["Juniors#4#2#"]

    def test_removing_the_selected_row_saves_it(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\nWomen#2#1#\n")
        editor.table.setCurrentCell(0, 0)
        editor._remove()
        assert _saved(tmp_path) == ["Women#2#1#"]

    def test_removing_with_nothing_selected_does_nothing(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor.table.setCurrentCell(-1, -1)
        editor._remove()
        assert editor.rows() == [("Men", "4", "2")]

    def test_an_added_row_is_blank_until_it_is_named(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor._add()
        assert editor.rows() == [("Men", "4", "2"), ("", "", "")]
        # A row with no group is not a ladder, so the file keeps only the real one.
        _rounds(editor, 1).setValue(1)
        assert _saved(tmp_path) == ["Men#4#2#"]

    def test_with_no_file_configured_editing_is_harmless(self) -> None:
        editor = EliminatorLaddersEditor()
        editor._add()
        _name(editor, 0).setText("Men")
        assert editor.rows() == [("Men", "", "")]

    def test_a_file_that_cannot_be_written_is_reported(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor._ladder_file = str(tmp_path / "nowhere" / "ladders.txt")
        _name(editor, 0).setText("Juniors")
        assert "Cannot write" in editor.status.text()


class TestItRefusesToShredAnotherFile:
    """The table saves on every keystroke, so a wrong path is not a typo, it is loss."""

    def test_nothing_is_written_while_the_path_clashes(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor.conflict = lambda: "start protocol"
        _name(editor, 0).setText("Juniors")
        assert _saved(tmp_path) == ["Men#4#2#"]

    def test_the_clash_is_named(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor.conflict = lambda: "start protocol"
        _name(editor, 0).setText("Juniors")
        assert "also the start protocol" in editor.status.text()

    def test_it_is_said_on_load_before_anything_is_typed(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor.conflict = lambda: "group times"
        editor.reload()
        assert "also the group times" in editor.status.text()

    def test_adding_groups_is_refused_too(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor.conflict = lambda: "start protocol"
        editor.add_missing_groups()
        assert _saved(tmp_path) == ["Men#4#2#"]
        assert "also the start protocol" in editor.status.text()

    def test_a_clear_path_saves_as_usual(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        _name(editor, 0).setText("Juniors")
        assert _saved(tmp_path) == ["Juniors#4#2#"]
        assert editor.status.text() == ""


class TestGroupsFromTheStartProtocol:
    def test_every_group_is_offered_once(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path)
        editor.add_missing_groups()
        assert editor.rows() == [("Men", "", ""), ("Women", "", "")]

    def test_the_shape_is_left_for_the_referee(self, tmp_path: Path) -> None:
        # Guessing it would pick the format of somebody's championship in silence.
        editor = _editor(tmp_path)
        editor.add_missing_groups()
        assert _saved(tmp_path) == ["Men###", "Women###"]

    def test_a_group_that_already_has_a_row_is_left_alone(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\n")
        editor.add_missing_groups()
        assert editor.rows() == [("Men", "4", "2"), ("Women", "", "")]

    def test_nothing_to_add_says_so(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path, "Men#4#2#\nWomen#4#1#\n")
        editor.add_missing_groups()
        assert "already has a row" in editor.status.text()
        assert _saved(tmp_path) == ["Men#4#2#", "Women#4#1#"]

    def test_added_groups_are_counted_in_the_status(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path)
        editor.add_missing_groups()
        assert "Added 2 group(s)" in editor.status.text()

    def test_a_missing_start_protocol_is_reported(self, tmp_path: Path) -> None:
        editor = _editor(tmp_path)
        editor._start_file = str(tmp_path / "gone.txt")
        editor.add_missing_groups()
        assert "Cannot read the start protocol" in editor.status.text()

    def test_without_a_start_protocol_configured_it_does_nothing(self) -> None:
        editor = EliminatorLaddersEditor()
        editor.add_missing_groups()
        assert editor.rows() == []
