"""Round-trip test: the four data-source selections survive save -> load of race info.

Regression for the bug where _save_race_info_to_path() wrote the four *Source tags but
load_config_file() did not parse them, so the positional fpg_info.txt format reset every
source back to "Use local data" on reload.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QCheckBox

from app.config import (
    START_LIST_SOURCE_LOCAL,
    START_LIST_SOURCE_SITE,
)
from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


def test_save_then_load_preserves_sources() -> None:
    """Full round-trip through the real MainWindow save/load methods."""
    win = MainWindow()
    try:
        win._cfg.start_list_source = START_LIST_SOURCE_SITE
        win._cfg.group_times_source = START_LIST_SOURCE_SITE
        win._cfg.finish_times_source = START_LIST_SOURCE_LOCAL
        win._cfg.remote_points_source = START_LIST_SOURCE_SITE
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            # Wipe the in-memory values, then reload from disk.
            win._cfg.start_list_source = START_LIST_SOURCE_LOCAL
            win._cfg.group_times_source = START_LIST_SOURCE_LOCAL
            win._cfg.finish_times_source = START_LIST_SOURCE_LOCAL
            win._cfg.remote_points_source = START_LIST_SOURCE_LOCAL
            win._load_race_info_from_path(path)
        assert win._cfg.start_list_source == START_LIST_SOURCE_SITE
        assert win._cfg.group_times_source == START_LIST_SOURCE_SITE
        assert win._cfg.finish_times_source == START_LIST_SOURCE_LOCAL
        assert win._cfg.remote_points_source == START_LIST_SOURCE_SITE
    finally:
        win.deleteLater()


def test_save_then_load_preserves_send_statistics_toggles() -> None:
    """The two live-stats toggles survive a full save -> load of race info."""
    win = MainWindow()
    try:
        win._cfg.send_group_statistics = True
        win._cfg.send_absolute_statistics = True
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            win._cfg.send_group_statistics = False
            win._cfg.send_absolute_statistics = False
            win._load_race_info_from_path(path)
        assert win._cfg.send_group_statistics is True
        assert win._cfg.send_absolute_statistics is True
    finally:
        win.deleteLater()


def test_disable_dns_survives_a_save_and_a_restart() -> None:
    win = MainWindow()
    try:
        box = win.findChild(QCheckBox, "disable_dns")
        assert box is not None
        assert box.text() == "Disable DNS (everyone counts as started)"
        box.setChecked(True)
        assert win._cfg.disable_dns is True
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            lines = Path(path).read_text(encoding="utf-8").splitlines()
            assert lines[-2:] == ["DisableDNS", "1"]
            box.setChecked(False)
            win._load_race_info_from_path(path)
            assert win._cfg.disable_dns is True
            assert box.isChecked()
            # A file written before the tag existed loads with it off.
            Path(path).write_text("\n".join(lines[:-2]) + "\n", encoding="utf-8")
            win._load_race_info_from_path(path)
            assert win._cfg.disable_dns is False
            assert not box.isChecked()
    finally:
        win.deleteLater()


def test_the_key_value_format_reads_disable_dns_like_its_siblings() -> None:
    win = MainWindow()
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            path.write_text("# FPG Race Info\nDisableDNS=1\n", encoding="utf-8")
            win._load_race_info_from_path(str(path))
        assert win._cfg.disable_dns is True
    finally:
        win.deleteLater()
