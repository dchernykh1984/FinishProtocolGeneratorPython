"""Auto-refresh checkbox must survive a save -> load of race info.

Regression for the bug where ticking "Auto-refresh protocol" did not persist: the spin
box is filled by _sync_ui_from_cfg with signals blocked, so cfg.auto_refresh_interval
stayed 0, and the save guard (enabled AND interval > 0) dropped the RefreshProtocol tag,
leaving the checkbox unchecked on the next launch.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


def test_toggle_on_persists_shown_interval_into_cfg() -> None:
    """Ticking the box copies the shown spin-box value into cfg."""
    win = MainWindow()
    try:
        win._on_refresh_toggled(False)  # neutralise any auto-loaded timer/state
        # Mimic the post-load divergence: cfg interval 0, but the spin box shows a value
        # because _sync_ui_from_cfg fills it with signals blocked.
        win._cfg.auto_refresh_interval = 0
        win._cfg.auto_refresh_enabled = False
        win._sync_ui_from_cfg()
        assert win._cfg.auto_refresh_interval == 0
        assert win._spin_refresh.value() > 0

        win._on_refresh_toggled(True)
        assert win._cfg.auto_refresh_enabled is True
        assert win._cfg.auto_refresh_interval == win._spin_refresh.value()
        assert win._cfg.auto_refresh_interval > 0
    finally:
        win.deleteLater()


def test_enabling_auto_refresh_survives_save_load() -> None:
    """Full round-trip: enable from an off state, save, reload -> checkbox stays on."""
    win = MainWindow()
    try:
        win._on_refresh_toggled(False)
        win._cfg.auto_refresh_enabled = False
        win._cfg.auto_refresh_interval = 0
        with tempfile.TemporaryDirectory() as td:
            off = str(Path(td) / "off.txt")
            win._save_race_info_to_path(off)
            # An off config carries no RefreshProtocol tag.
            assert "RefreshProtocol" not in Path(off).read_text(encoding="utf-8")

            # Loading it reproduces the divergence: cfg interval 0, spin box shows > 0.
            win._load_race_info_from_path(off)
            assert win._cfg.auto_refresh_interval == 0
            assert win._spin_refresh.value() > 0

            # User ticks the box and exits (save on close).
            win._on_refresh_toggled(True)
            on = str(Path(td) / "on.txt")
            win._save_race_info_to_path(on)
            assert "RefreshProtocol" in Path(on).read_text(encoding="utf-8")

            # Relaunch: load the saved config.
            win._load_race_info_from_path(on)
        assert win._cfg.auto_refresh_enabled is True
        assert win._chk_refresh.isChecked() is True
        assert win._cfg.auto_refresh_interval > 0
    finally:
        win.deleteLater()
