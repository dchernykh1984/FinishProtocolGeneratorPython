"""Pack threshold is editable only for absolute stats and survives old/new configs."""

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QSpinBox

from app.file_io import KEY_VALUE_HEADER
from app.main_window import MainWindow


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)
    win = MainWindow()
    yield win
    win.deleteLater()
    app.processEvents()


def test_threshold_follows_absolute_toggle_and_updates_config(window):
    spin = window.findChild(QSpinBox, "pack_gap_seconds")
    absolute = window.findChild(QCheckBox, "send_absolute_statistics")
    group = window.findChild(QCheckBox, "send_group_statistics")
    assert spin.value() == 10
    assert not spin.isEnabled()
    group.setChecked(True)
    assert not spin.isEnabled()
    absolute.setChecked(True)
    assert spin.isEnabled()
    spin.setValue(15)
    assert window._cfg.pack_gap_seconds == 15
    layout = spin.parentWidget().layout()
    # Both controls are on the HTTP page, in consecutive rows.
    pack_row_index = next(
        i
        for i in range(layout.count())
        if layout.itemAt(i).layout() is not None
        and layout.itemAt(i).layout().indexOf(spin) >= 0
    )
    assert pack_row_index == layout.indexOf(absolute) + 1


def test_roundtrip_and_legacy_default(window, tmp_path):
    path = tmp_path / "race.txt"
    window._cfg.pack_gap_seconds = 25
    window._save_race_info_to_path(str(path))
    saved = path.read_text(encoding="utf-8")
    window._cfg.pack_gap_seconds = 3
    window._load_race_info_from_path(str(path))
    assert window._cfg.pack_gap_seconds == 25
    assert window.findChild(QSpinBox, "pack_gap_seconds").value() == 25
    path.write_text(saved.replace("PackGapSeconds\n25\n", ""), encoding="utf-8")
    window._load_race_info_from_path(str(path))
    assert window._cfg.pack_gap_seconds == 10


@pytest.mark.parametrize(
    "value, expected",
    [("7", 7), ("0", 0), ("-5", 10), ("bad", 10), ("99999999999", 10)],
)
def test_key_value_threshold_is_validated(window, tmp_path, value, expected):
    path = tmp_path / "race.txt"
    path.write_text(f"{KEY_VALUE_HEADER}\nPackGapSeconds={value}\n", encoding="utf-8")
    window._load_race_info_from_path(str(path))
    assert window._cfg.pack_gap_seconds == expected
