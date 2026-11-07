"""Editor for the Eliminator Finals ladders: one row per group.

The ladder file is the single source of truth, so this widget reads and writes it
directly rather than keeping a copy in the config. The shape of a ladder is a
decision taken on the day -- six of eleven entered riders showed up, so a group that
was going to ride semi-finals now rides one final -- which is why it is set here
rather than carried over from the registration.

A row whose numbers are blank is kept and written out: the group then has no ladder,
the generation refuses, and the referee is told which group is waiting. Guessing a
shape would hand out medals for a format nobody chose.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.eliminator import HEAT_SIZES, start_list_groups
from app.eliminator_output import write_ladder_file
from app.file_io import read_start_protocol, read_text_lines
from app.models import get_field

#: Deepest ladder worth offering: five rounds already seats 64 qualifiers per group.
_MAX_ROUNDS = 5


class EliminatorLaddersEditor(QWidget):
    """Riders per heat and number of rounds, per group, saved to the ladder file."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._ladder_file = ""
        self._start_file = ""
        #: Why the ladder file could not be read, when it is there but unreadable.
        self._unreadable = ""
        #: Asks the race whether writing the ladder file would land on another of its
        #: files. While it answers with a setting's name, nothing is written: this
        #: table saves on every keystroke, so it would shred an input file.
        self.conflict: Callable[[], str] = lambda: ""
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "One ladder per group. Riders per heat and rounds decide the shape: "
                "4 and 2 is two semi-finals and a final for eight qualifiers, 4 and 1 "
                "one final for four. A blank row stops generation until it is filled."
            )
        )
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Group", "Riders per heat", "Rounds"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setMinimumHeight(130)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        for title, handler in (
            ("Add groups from the start protocol", self.add_missing_groups),
            ("Add group", self._add),
            ("Remove group", self._remove),
        ):
            button = QPushButton(title)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    # -- wiring ---------------------------------------------------------------

    def set_files(self, ladder_file: str, start_protocol_file: str) -> None:
        """Point the editor at the ladder file it owns and the start protocol it
        offers groups from, and show what the ladder file holds now."""
        self._ladder_file = ladder_file
        self._start_file = start_protocol_file
        self.reload()

    def reload(self) -> None:
        """Replace the table with what the ladder file says.

        A file that is not there yet is an empty table, not an error: the first finals
        of an event start from one, and the referee fills it in here. A file that is
        there but cannot be read is the opposite -- it holds ladders this table must
        not save an empty version over.
        """
        self._unreadable = ""
        lines: list[str] = []
        try:
            lines = read_text_lines(self._ladder_file) if self._ladder_file else []
        except FileNotFoundError:
            pass
        except OSError as exc:
            self._unreadable = f"Cannot read {self._ladder_file}: {exc}"
        rows: list[tuple[str, str, str]] = []
        for line in lines:
            group = get_field(line, 0).strip()
            if group:
                rows.append(
                    (group, get_field(line, 1).strip(), get_field(line, 2).strip())
                )
        self._set_rows(rows)
        # A value the table cannot show is a value the next keystroke would save
        # over, so say which group lost one instead of letting it vanish.
        adjusted = [
            row[0] for row, shown in zip(rows, self.rows(), strict=True) if row != shown
        ]
        self.status.setText(self._refusal() or _adjusted(adjusted))

    def _refusal(self) -> str:
        """Why this table will not save, or "" when it will."""
        if self._unreadable:
            return f"Not saved: {self._unreadable}"
        clash = self.conflict()
        if not clash:
            return ""
        return (
            f"Not saved: the ladder file is also the {clash} of this race. "
            "Point it at a file of its own."
        )

    def add_missing_groups(self) -> None:
        """Append every group of the start protocol that has no row yet.

        Only the name: the shape is the referee's call, and a default would be a
        silent guess at the format of somebody's championship.
        """
        if not self._start_file:
            return
        try:
            start_list = read_start_protocol(self._start_file, place_field=True)
        except OSError as exc:
            self.status.setText(f"Cannot read the start protocol: {exc}")
            return
        rows = self.rows()
        known = {group for group, _heat, _rounds in rows}
        added = [name for name in start_list_groups(start_list) if name not in known]
        if not added:
            self.status.setText("Every group of the start protocol already has a row.")
            return
        self._set_rows(rows + [(name, "", "") for name in added])
        self.status.setText(
            f"Added {len(added)} group(s); set riders per heat and rounds for each."
        )
        self._save()

    # -- table ----------------------------------------------------------------

    def rows(self) -> list[tuple[str, str, str]]:
        """The table as (group, riders per heat, rounds), the numbers as shown."""
        out: list[tuple[str, str, str]] = []
        for row in range(self.table.rowCount()):
            group = cast(QLineEdit, self.table.cellWidget(row, 0)).text()
            heat = cast(QComboBox, self.table.cellWidget(row, 1)).currentText()
            rounds = cast(QSpinBox, self.table.cellWidget(row, 2)).value()
            out.append((group, heat, "" if rounds == 0 else str(rounds)))
        return out

    def _set_rows(self, rows: list[tuple[str, str, str]]) -> None:
        self.table.setRowCount(0)
        for group, heat, rounds in rows:
            self._append(group, heat, rounds)

    def _append(self, group: str, heat: str, rounds: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name = QLineEdit(group)
        size = QComboBox()
        size.addItems(["", *(str(s) for s in HEAT_SIZES)])
        size.setCurrentText(heat if heat in {str(s) for s in HEAT_SIZES} else "")
        depth = QSpinBox()
        depth.setRange(0, _MAX_ROUNDS)
        # 0 is "not set yet", shown blank: a ladder of no rounds does not exist.
        depth.setSpecialValueText("")
        depth.setValue(_as_rounds(rounds))
        for column, widget in enumerate((name, size, depth)):
            self.table.setCellWidget(row, column, widget)
        # Connected only once the values are in, so filling the table from the file
        # cannot write that same file straight back.
        name.textChanged.connect(self._save)
        size.currentTextChanged.connect(self._save)
        depth.valueChanged.connect(self._save)

    def _add(self) -> None:
        self._append("", "", "")
        self.table.setCurrentCell(self.table.rowCount() - 1, 0)

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._save()

    def _save(self) -> None:
        """Write the table to the ladder file, which is where every reader looks."""
        if not self._ladder_file:
            return
        refusal = self._refusal()
        if refusal:
            self.status.setText(refusal)
            return
        try:
            write_ladder_file(self._ladder_file, self.rows())
        except OSError as exc:
            self.status.setText(f"Cannot write {self._ladder_file}: {exc}")
            return
        self.changed.emit()


def _adjusted(groups: list[str]) -> str:
    """Which groups the ladder file holds a value this table cannot show for."""
    if not groups:
        return ""
    return (
        f"Riders per heat must be {' or '.join(str(s) for s in HEAT_SIZES)} and "
        f"rounds at most {_MAX_ROUNDS}; check: {', '.join(groups)}."
    )


def _as_rounds(value: str) -> int:
    """What the spin box shows for a round count out of the ladder file.

    A number too deep for the box is clamped rather than blanked: blanking it would
    be saved back on the next keystroke, and the referee's figure would be gone.
    """
    try:
        rounds = int(value)
    except TypeError, ValueError:
        return 0
    return min(max(rounds, 0), _MAX_ROUNDS)
