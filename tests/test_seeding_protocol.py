"""The seeding export as a setting rather than a race type.

Eliminator Qualification only ever added this one file on top of an ordinary mass
start, so it became a checkbox. The tests that matter are about what happens to the
configs written while it was still a race type.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QMessageBox

from app.config import (
    ALL_RACE_TYPES,
    LEGACY_RACE_TYPE_QUALIFICATION,
    RACE_TYPE_CUSTOM_START,
    RACE_TYPE_ELIMINATOR_FINALS,
    RACE_TYPE_MASS_SPLITTED,
    RaceConfig,
)
from app.file_io import config_file_problems, load_config_file
from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _no_auto_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)


@pytest.fixture
def quiet(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Collect the modals instead of showing them."""
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda _p, title, _text, *a: shown.append(title)
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    return shown


class TestTheSetting:
    def test_the_race_type_is_gone_from_the_list(self) -> None:
        assert LEGACY_RACE_TYPE_QUALIFICATION not in ALL_RACE_TYPES

    def test_it_is_off_by_default(self) -> None:
        assert not RaceConfig().generate_text_protocol_effective()

    def test_ticking_it_turns_the_export_on(self) -> None:
        assert RaceConfig(
            write_seeding_protocol=True
        ).generate_text_protocol_effective()

    def test_it_composes_with_any_scoring(self) -> None:
        # The point of the move: a qualifier can be ridden in any mode.
        for race_type in ALL_RACE_TYPES:
            cfg = RaceConfig(race_type=race_type, write_seeding_protocol=True)
            expected = race_type != RACE_TYPE_ELIMINATOR_FINALS
            assert cfg.generate_text_protocol_effective() is expected, race_type

    def test_a_finals_round_has_no_places_to_seed_from(self) -> None:
        cfg = RaceConfig(
            race_type=RACE_TYPE_ELIMINATOR_FINALS, write_seeding_protocol=True
        )
        assert not cfg.generate_text_protocol_effective()


class TestWhereTheFileGoes:
    def test_an_empty_path_keeps_the_old_place(self) -> None:
        # Beside the group protocol, as the C++ generator wrote it.
        assert RaceConfig().seeding_protocol_path("data/gr.html") == "data/gr.html.txt"

    def test_a_path_is_used_as_given(self) -> None:
        cfg = RaceConfig(seeding_protocol_file="finals/data/start.txt")
        assert cfg.seeding_protocol_path("data/gr.html") == "finals/data/start.txt"


class TestMigratingAnOldConfig:
    """A config naming the retired race type must keep working."""

    def _positional(self, tmp_path: Path, race_type: str) -> str:
        win = MainWindow()
        try:
            path = str(tmp_path / "fpg_info.txt")
            win._save_race_info_to_path(path)
            lines = Path(path).read_text(encoding="utf-8").split("\n")
            lines[12] = race_type
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            return path
        finally:
            win.deleteLater()

    def test_the_retired_type_becomes_the_setting(
        self, tmp_path: Path, quiet: list[str]
    ) -> None:
        path = self._positional(tmp_path, LEGACY_RACE_TYPE_QUALIFICATION)
        win = MainWindow()
        try:
            win._load_race_info_from_path(path)
            assert win._cfg.race_type == RACE_TYPE_MASS_SPLITTED
            assert win._cfg.write_seeding_protocol
            assert win._cfg.generate_text_protocol_effective()
        finally:
            win.deleteLater()

    def test_it_is_not_reported_as_a_damaged_file(
        self, tmp_path: Path, quiet: list[str]
    ) -> None:
        # The anchor check knows the retired value: the file is old, not broken.
        path = self._positional(tmp_path, LEGACY_RACE_TYPE_QUALIFICATION)
        assert config_file_problems(load_config_file(path)) == []
        win = MainWindow()
        try:
            win._load_race_info_from_path(path)
        finally:
            win.deleteLater()
        assert quiet == []

    def test_a_genuinely_unknown_type_is_still_reported(self, tmp_path: Path) -> None:
        path = self._positional(tmp_path, "Something Else")
        assert config_file_problems(load_config_file(path))

    def test_the_key_value_format_is_migrated_too(
        self, tmp_path: Path, quiet: list[str]
    ) -> None:
        path = tmp_path / "kv.txt"
        path.write_text(
            "# FPG Race Info\n"
            f"RaceType={LEGACY_RACE_TYPE_QUALIFICATION}\n"
            "RaceName=Qualifier\n"
            "End\n",
            encoding="utf-8",
        )
        win = MainWindow()
        try:
            win._load_race_info_from_path(str(path))
            assert win._cfg.race_type == RACE_TYPE_MASS_SPLITTED
            assert win._cfg.write_seeding_protocol
        finally:
            win.deleteLater()

    def test_another_race_type_is_left_alone(
        self, tmp_path: Path, quiet: list[str]
    ) -> None:
        path = self._positional(tmp_path, RACE_TYPE_CUSTOM_START)
        win = MainWindow()
        try:
            win._load_race_info_from_path(path)
            assert win._cfg.race_type == RACE_TYPE_CUSTOM_START
            assert not win._cfg.write_seeding_protocol
        finally:
            win.deleteLater()


class TestTheSettingsSurviveARoundTrip:
    @pytest.mark.parametrize("ticked", [True, False])
    def test_save_then_load(self, tmp_path: Path, ticked: bool) -> None:
        win = MainWindow()
        try:
            win._cfg.write_seeding_protocol = ticked
            win._cfg.seeding_protocol_file = "finals/start.txt" if ticked else ""
            path = str(tmp_path / "fpg_info.txt")
            win._save_race_info_to_path(path)
            other = MainWindow()
            try:
                other._load_race_info_from_path(path)
                assert other._cfg.write_seeding_protocol is ticked
                assert (
                    other._cfg.seeding_protocol_file == win._cfg.seeding_protocol_file
                )
            finally:
                other.deleteLater()
        finally:
            win.deleteLater()


class TestTheInterface:
    def test_the_row_is_there(self) -> None:
        win = MainWindow()
        try:
            assert win.findChild(QCheckBox, "write_seeding_protocol") is not None
            assert win.findChild(QLineEdit, "seeding_protocol_file") is not None
        finally:
            win.deleteLater()

    def test_the_path_follows_the_checkbox(self) -> None:
        win = MainWindow()
        try:
            checkbox = win.findChild(QCheckBox, "write_seeding_protocol")
            assert checkbox is not None
            assert not win._edit_seeding.isEnabled()
            checkbox.setChecked(True)
            assert win._cfg.write_seeding_protocol
            assert win._edit_seeding.isEnabled() and win._btn_seeding.isEnabled()
            checkbox.setChecked(False)
            assert not win._edit_seeding.isEnabled()
        finally:
            win.deleteLater()

    def test_it_hides_for_a_finals_round(self) -> None:
        win = MainWindow()
        try:
            win._combo_race_type.setCurrentText(RACE_TYPE_ELIMINATOR_FINALS)
            assert win._seeding_row.isHidden()
            win._combo_race_type.setCurrentText(RACE_TYPE_MASS_SPLITTED)
            assert not win._seeding_row.isHidden()
        finally:
            win.deleteLater()

    def test_loading_a_config_puts_the_row_in_step(self, tmp_path: Path) -> None:
        win = MainWindow()
        try:
            win._cfg.race_type = RACE_TYPE_ELIMINATOR_FINALS
            win._cfg.write_seeding_protocol = True
            path = str(tmp_path / "fpg_info.txt")
            win._save_race_info_to_path(path)
            other = MainWindow()
            try:
                other._load_race_info_from_path(path)
                assert other._seeding_row.isHidden()
                assert other._edit_seeding.isEnabled()
            finally:
                other.deleteLater()
        finally:
            win.deleteLater()


def test_the_export_runs_in_a_mode_it_never_could_before(tmp_path: Path) -> None:
    """Custom Start as the qualifier -- impossible while this was a race type."""
    from app.config import RaceConfig as Config
    from app.html_writer import write_group_protocol
    from app.models import GroupStartElement

    cfg = Config(
        race_type=RACE_TYPE_CUSTOM_START,
        write_seeding_protocol=True,
        seeding_protocol_file=str(tmp_path / "seeding.txt"),
    )
    with tempfile.TemporaryDirectory() as td:
        group_protocol = str(Path(td) / "gr.html")
        write_group_protocol(
            group_protocol, [], [GroupStartElement(group_id="Men", seconds=0.0)], cfg, 0
        )
    assert (tmp_path / "seeding.txt").exists()
    assert not Path(group_protocol + ".txt").exists()
