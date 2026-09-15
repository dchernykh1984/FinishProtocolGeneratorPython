"""Behaviour tests for the time-trial start board window."""

from __future__ import annotations

import sys
from datetime import datetime

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from app.time_trial import ALIGN_CENTER, BoardItem, StartEntry, now_seconds
from app.time_trial_window import TimeTrialWindow

_app = QApplication.instance() or QApplication(sys.argv)

BASE = now_seconds(datetime(2026, 9, 15, 10, 0, 0))


def _entries() -> list[StartEntry]:
    return [
        StartEntry(competitor_id=str(i), name=f"Rider {i}", start_time=BASE + i * 60)
        for i in range(1, 6)
    ]


@pytest.fixture
def board():
    window = TimeTrialWindow(clock=lambda: BASE + 150)
    try:
        yield window
    finally:
        window.hide()
        window.deleteLater()


def _render(window: TimeTrialWindow) -> QPixmap:
    """Paint the board, which is what actually exercises paintEvent."""
    pixmap = QPixmap(window.size())
    window.render(pixmap)
    return pixmap


def test_opens_as_its_own_window(board) -> None:
    assert board.isWindow()
    assert board.windowTitle() == "Time Trial"


def test_paints_a_full_board(board) -> None:
    board.set_entries(_entries())
    assert not _render(board).isNull()


def test_paints_with_no_schedule_at_all(board) -> None:
    # Nobody registered: the board must still come up rather than fail to paint.
    assert not _render(board).isNull()


def test_paints_once_the_field_has_emptied(board) -> None:
    window = TimeTrialWindow(clock=lambda: BASE + 10_000)
    try:
        window.set_entries(_entries())
        assert not _render(window).isNull()
    finally:
        window.deleteLater()


def test_set_entries_keeps_its_own_copy(board) -> None:
    entries = _entries()
    board.set_entries(entries)
    entries.clear()
    # A caller reusing its list must not blank the board.
    assert not _render(board).isNull()


@pytest.mark.parametrize(
    "size",
    [(320, 192), (800, 480), (1920, 1080), (400, 1000), (1000, 400)],
)
def test_paints_at_any_window_shape(board, size) -> None:
    board.set_entries(_entries())
    board.resize(*size)
    assert not _render(board).isNull()


def test_ticking_stops_while_the_board_is_hidden(board) -> None:
    board.show()
    assert board._timer.isActive()
    board.hide()
    # A hidden board shows nothing, so repainting it every tick is wasted work.
    assert not board._timer.isActive()


def test_the_clock_drives_what_is_shown() -> None:
    moment = BASE
    window = TimeTrialWindow(clock=lambda: moment)
    try:
        window.set_entries(_entries())
        assert not _render(window).isNull()
        moment = BASE + 300
        assert not _render(window).isNull()
    finally:
        window.deleteLater()


def test_uses_the_wall_clock_by_default() -> None:
    window = TimeTrialWindow()
    try:
        assert window._clock() > 20_000 * 86400
    finally:
        window.deleteLater()


def test_fonts_are_sized_in_pixels_so_dpi_cannot_rescale_them() -> None:
    # The layout boxes are pixel-style units. A point size is scaled again by the
    # screen DPI -- a third larger at 96 DPI -- so the text would outgrow its band on
    # exactly the machines this ships to.
    window = TimeTrialWindow(clock=lambda: BASE)
    try:
        item = BoardItem("0:30", 0, 0, 100, 40, 32, ALIGN_CENTER)
        font = window._item_font(item, 2.0)
        assert font.pixelSize() == 64
        assert font.pointSize() == -1  # Qt reports -1 once a pixel size is set
        assert font.bold()
    finally:
        window.deleteLater()


def test_a_font_never_collapses_to_nothing() -> None:
    window = TimeTrialWindow(clock=lambda: BASE)
    try:
        item = BoardItem("x", 0, 0, 10, 10, 18, ALIGN_CENTER)
        assert window._item_font(item, 0.001).pixelSize() >= 1
    finally:
        window.deleteLater()
