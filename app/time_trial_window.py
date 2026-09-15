"""The time-trial start board: a separate window for the start line.

It shows the wall clock, the countdown to the next start, the bib about to go and,
much smaller in the bottom corners, the rider who just went (right) and the one going
after next (left), each under its own name.

The widget is deliberately thin. Which riders belong on the board and where every run
of text sits come from :mod:`app.time_trial`, so the only thing done here is scaling
that layout to the window and painting it.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from app.time_trial import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    StartEntry,
    board_items,
    board_transform,
    now_seconds,
    select_view,
)

# Fast enough that the countdown never looks stuck on a second, cheap enough to leave
# running: a repaint only walks a handful of text runs.
_TICK_MS = 100

_BACKGROUND = QColor(16, 16, 16)
_FOREGROUND = QColor(245, 245, 245)

_ALIGNMENT = {
    ALIGN_LEFT: Qt.AlignmentFlag.AlignLeft,
    ALIGN_CENTER: Qt.AlignmentFlag.AlignHCenter,
}


class TimeTrialWindow(QWidget):
    """Start board for a time trial, updated from the generator's start schedule."""

    def __init__(
        self,
        parent: QWidget | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(parent)
        # A parent would keep this inside the main window; it has to be its own window.
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("Time Trial")
        self.resize(int(DESIGN_WIDTH), int(DESIGN_HEIGHT))
        self.setMinimumSize(320, 192)
        self._entries: list[StartEntry] = []
        self._clock = clock if clock is not None else now_seconds
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self.update)

    def set_entries(self, entries: list[StartEntry]) -> None:
        """Replace the start schedule, as a fresh generation produces it."""
        self._entries = list(entries)
        self.update()

    def showEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802
        # Nothing on a hidden board is visible, so stop repainting it.
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), _BACKGROUND)
            # Qt never paints a zero-area widget, so scale is always positive here;
            # board_transform still defines the degenerate case for its own callers.
            scale, offset_x, offset_y = board_transform(self.width(), self.height())
            painter.setPen(_FOREGROUND)
            view = select_view(self._entries, self._clock())
            for item in board_items(view):
                font = QFont(self.font())
                font.setPointSizeF(max(1.0, item.font_size * scale))
                font.setBold(True)
                painter.setFont(font)
                rect = QRectF(
                    offset_x + item.x * scale,
                    offset_y + item.y * scale,
                    item.width * scale,
                    item.height * scale,
                )
                alignment = _ALIGNMENT.get(item.align, Qt.AlignmentFlag.AlignRight)
                # The boxes position the text; they must not crop it. Without
                # TextDontClip a descender that reaches past its box is sliced off,
                # which on a start board looks like a rendering fault.
                painter.drawText(
                    rect,
                    int(
                        alignment
                        | Qt.AlignmentFlag.AlignVCenter
                        | Qt.TextFlag.TextDontClip
                    ),
                    item.text,
                )
        finally:
            painter.end()
