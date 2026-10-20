"""Small ordered-rule editor; JSON is a storage format, not a user input field."""

from __future__ import annotations

import json
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

from app.attempt_rules import parse_attempt_rules


class AttemptRulesEditor(QWidget):
    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "First rule: result. Further rules: tie-breaks. Best times are summed; "
                "sort controls their order. Empty list: legacy Additional info rules."
            )
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Label", "Attempts", "Attempt numbers", "Sort"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setMinimumHeight(130)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        for title, handler in (
            ("Add rule", self._add),
            ("Remove rule", self._remove),
            ("Move up", lambda: self._move(-1)),
            ("Move down", lambda: self._move(1)),
        ):
            button = QPushButton(title)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)

    def set_rules_json(self, value: str) -> None:
        try:
            rules = parse_attempt_rules(value)
        except ValueError as exc:
            self._set_data([])
            self.error.setText(str(exc))
            return
        self._set_data(
            [
                {
                    "label": r.label,
                    "attempts": r.attempts,
                    "attempt_numbers": list(r.attempt_numbers),
                    "sort": r.sort,
                }
                for r in rules
            ]
        )
        self.error.clear()

    def _set_data(self, data: list[dict]) -> None:
        self.table.setRowCount(0)
        for item in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            label = QLineEdit(item["label"])
            count = QSpinBox()
            count.setRange(1, 2147483647)
            count.setValue(item["attempts"])
            numbers = item["attempt_numbers"]
            numbers_edit = QLineEdit(
                ",".join(map(str, numbers)) if isinstance(numbers, list) else numbers
            )
            direction = QComboBox()
            direction.addItems(["asc", "desc"])
            direction.setCurrentText(item["sort"])
            for column, widget in enumerate((label, count, numbers_edit, direction)):
                self.table.setCellWidget(row, column, widget)
            label.textChanged.connect(self._changed)
            count.valueChanged.connect(self._changed)
            numbers_edit.textChanged.connect(self._changed)
            direction.currentTextChanged.connect(self._changed)

    def _data(self) -> list[dict]:
        data = []
        for row in range(self.table.rowCount()):
            label = cast(QLineEdit, self.table.cellWidget(row, 0)).text()
            count = cast(QSpinBox, self.table.cellWidget(row, 1)).value()
            text = cast(QLineEdit, self.table.cellWidget(row, 2)).text()
            try:
                numbers: list[int] | str = [int(n.strip()) for n in text.split(",")]
            except ValueError:
                numbers = text
            direction = cast(QComboBox, self.table.cellWidget(row, 3)).currentText()
            data.append(
                {
                    "label": label,
                    "attempts": count,
                    "attempt_numbers": numbers,
                    "sort": direction,
                }
            )
        return data

    def _changed(self) -> None:
        value = json.dumps(self._data(), ensure_ascii=True, separators=(",", ":"))
        try:
            parse_attempt_rules(value)
        except ValueError as exc:
            self.error.setText(str(exc))
        else:
            self.error.clear()
        self.changed.emit(value)

    def _add(self) -> None:
        data = self._data()
        data.append(
            {
                "label": "Result" if not data else "Tie-break",
                "attempts": 1,
                "attempt_numbers": [1],
                "sort": "asc",
            }
        )
        self._set_data(data)
        self.table.setCurrentCell(len(data) - 1, 0)
        self._changed()

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._changed()

    def _move(self, delta: int) -> None:
        row = self.table.currentRow()
        data = self._data()
        target = row + delta
        if row < 0 or not 0 <= target < len(data):
            return
        data[row], data[target] = data[target], data[row]
        self._set_data(data)
        self.table.setCurrentCell(target, 0)
        self._changed()
