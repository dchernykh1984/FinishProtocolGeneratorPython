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


class TestItNeverOverwritesARaceFile:
    """The field asks for a start protocol, so naming this race's own is an easy slip.

    Writing there would replace a start list with a finishing order in the middle of
    an event, so the export is dropped for that run and the clash reported.
    """

    def _cfg(self, tmp_path: Path) -> RaceConfig:
        cfg = RaceConfig(write_seeding_protocol=True)
        cfg.start_protocol_file = str(tmp_path / "start.txt")
        cfg.group_time_file = str(tmp_path / "groups.txt")
        cfg.finish_time_file = str(tmp_path / "results.txt")
        cfg.group_protocol_file = str(tmp_path / "gr.html")
        cfg.absolute_protocol_file = str(tmp_path / "abs.html")
        cfg.template_file = str(tmp_path / "template.html")
        cfg.start_check_list_file = str(tmp_path / "check.txt")
        return cfg

    @pytest.mark.parametrize(
        ("attribute", "label"),
        [
            ("start_protocol_file", "start protocol"),
            ("group_time_file", "group times"),
            ("finish_time_file", "finish times"),
            ("start_check_list_file", "start check list"),
            ("group_protocol_file", "group protocol"),
            ("absolute_protocol_file", "absolute protocol"),
            ("template_file", "HTML styles template"),
        ],
    )
    def test_every_race_file_is_guarded(
        self, tmp_path: Path, attribute: str, label: str
    ) -> None:
        cfg = self._cfg(tmp_path)
        cfg.seeding_protocol_file = getattr(cfg, attribute)
        assert cfg.seeding_protocol_conflict(cfg.group_protocol_file) == label

    def test_a_file_of_its_own_is_fine(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        cfg.seeding_protocol_file = str(tmp_path / "finals" / "start.txt")
        assert cfg.seeding_protocol_conflict(cfg.group_protocol_file) == ""

    def test_the_default_place_is_fine(self, tmp_path: Path) -> None:
        cfg = self._cfg(tmp_path)
        assert cfg.seeding_protocol_conflict(cfg.group_protocol_file) == ""

    def test_the_absolute_path_a_file_picker_gives_back_is_caught(self) -> None:
        # The pickers hand back absolute paths while the shipped settings are
        # relative, so this is the pair a referee is most likely to produce.
        from app.paths import app_path

        cfg = RaceConfig(write_seeding_protocol=True)
        cfg.start_protocol_file = "data/start.txt"
        cfg.seeding_protocol_file = str(app_path("data/start.txt"))
        assert cfg.seeding_protocol_conflict("data/gr.html") == "start protocol"

    def test_a_path_that_doubles_back_is_caught(self) -> None:
        cfg = RaceConfig(write_seeding_protocol=True)
        cfg.start_protocol_file = "data/../data/start.txt"
        cfg.seeding_protocol_file = "data/start.txt"
        assert cfg.seeding_protocol_conflict("data/gr.html") == "start protocol"

    def test_the_same_file_written_two_ways_is_still_caught(
        self, tmp_path: Path
    ) -> None:
        cfg = self._cfg(tmp_path)
        cfg.seeding_protocol_file = f"  {tmp_path}/./start.txt  "
        assert (
            cfg.seeding_protocol_conflict(cfg.group_protocol_file) == "start protocol"
        )

    def test_nothing_is_guarded_while_the_export_is_off(self, tmp_path: Path) -> None:
        # The check only matters when something would be written.
        cfg = self._cfg(tmp_path)
        cfg.write_seeding_protocol = False
        cfg.seeding_protocol_file = cfg.start_protocol_file
        assert not cfg.generate_text_protocol_effective()


class TestTheRunKeepsTheStartList:
    def _race(self, tmp_path: Path) -> RaceConfig:
        (tmp_path / "start.txt").write_text(
            "\n".join(
                f"{100 + i}#Rider {i}#Men#1#1#1990#Team#City##0 00:00:00.000#"
                for i in range(1, 5)
            ),
            encoding="utf-8",
        )
        (tmp_path / "groups.txt").write_text("Men#0 10:00:00.000#\n", encoding="utf-8")
        (tmp_path / "results.txt").write_text(
            "\n".join(f"{100 + i}#0 10:0:{30 + i}.000#finish#" for i in range(1, 5)),
            encoding="utf-8",
        )
        cfg = RaceConfig(write_seeding_protocol=True)
        cfg.start_protocol_file = str(tmp_path / "start.txt")
        cfg.group_time_file = str(tmp_path / "groups.txt")
        cfg.finish_time_file = str(tmp_path / "results.txt")
        cfg.group_protocol_file = str(tmp_path / "gr.html")
        cfg.absolute_protocol_file = str(tmp_path / "abs.html")
        return cfg

    def _run(self, cfg: RaceConfig) -> list[str]:
        from app.main_window import _GenerateWorker

        worker = _GenerateWorker(cfg)
        messages: list[str] = []
        worker.log_message.connect(messages.append)
        worker.run()
        return messages

    def test_a_clash_leaves_the_start_protocol_untouched(self, tmp_path: Path) -> None:
        cfg = self._race(tmp_path)
        cfg.seeding_protocol_file = cfg.start_protocol_file
        before = Path(cfg.start_protocol_file).read_bytes()
        messages = self._run(cfg)
        assert Path(cfg.start_protocol_file).read_bytes() == before
        assert any("would overwrite the start protocol" in m for m in messages)

    def test_the_protocols_are_still_written(self, tmp_path: Path) -> None:
        cfg = self._race(tmp_path)
        cfg.seeding_protocol_file = cfg.start_protocol_file
        self._run(cfg)
        assert Path(cfg.group_protocol_file).exists()
        assert Path(cfg.absolute_protocol_file).exists()

    def test_a_sound_path_still_gets_its_file(self, tmp_path: Path) -> None:
        cfg = self._race(tmp_path)
        cfg.seeding_protocol_file = str(tmp_path / "finals_start.txt")
        messages = self._run(cfg)
        assert Path(cfg.seeding_protocol_file).exists()
        assert not any("would overwrite" in m for m in messages)


class TestTheExportNeverTakesTheRunDown:
    """It is an extra, written from inside the group protocol.

    A failure there used to raise straight out of the run, so the absolute protocol
    was never written and the operator saw a bare OSError.
    """

    def test_a_folder_that_does_not_exist_yet_is_made(self, tmp_path: Path) -> None:
        # Pointing at the finals folder before it exists is the ordinary case.
        race = TestTheRunKeepsTheStartList()
        cfg = race._race(tmp_path)
        cfg.seeding_protocol_file = str(tmp_path / "finals" / "data" / "start.txt")
        messages = race._run(cfg)
        assert Path(cfg.seeding_protocol_file).exists()
        assert not any("ERROR" in m for m in messages)

    def test_the_absolute_protocol_is_written_anyway(self, tmp_path: Path) -> None:
        race = TestTheRunKeepsTheStartList()
        cfg = race._race(tmp_path)
        blocker = tmp_path / "blocked"
        blocker.write_text("not a directory", encoding="utf-8")
        cfg.seeding_protocol_file = str(blocker / "start.txt")
        messages = race._run(cfg)
        assert Path(cfg.absolute_protocol_file).exists()
        assert any("cannot be written" in m for m in messages)
        assert not Path(cfg.seeding_protocol_file).exists()
