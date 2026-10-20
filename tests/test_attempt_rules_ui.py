"""Rule editing and config persistence through the real main-window workflow."""

import json

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.attempt_rules import AttemptRule, parse_attempt_rules, rules_json
from app.config import RACE_TYPE_MASS_SPLITTED, RACE_TYPE_NUMBER_OF_TRIES
from app.file_io import KEY_VALUE_HEADER, load_config_file
from app.main_window import MainWindow


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)
    win = MainWindow()
    yield win
    win.deleteLater()
    app.processEvents()


def test_editor_visibility_editing_and_priority(window):
    editor = window._attempt_rules_editor
    assert editor.isHidden()
    window._combo_race_type.setCurrentText(RACE_TYPE_NUMBER_OF_TRIES)
    assert not editor.isHidden()
    editor._add()
    editor._add()
    editor.table.cellWidget(1, 0).setText("Qualification")
    editor.table.cellWidget(1, 3).setCurrentText("desc")
    assert parse_attempt_rules(window._cfg.attempt_rules_json)[1].sort == "desc"
    editor._move(-1)
    rules = parse_attempt_rules(window._cfg.attempt_rules_json)
    assert rules[0].label == "Qualification"
    editor._remove()
    assert len(parse_attempt_rules(window._cfg.attempt_rules_json)) == 1
    window._combo_race_type.setCurrentText(RACE_TYPE_MASS_SPLITTED)
    assert editor.isHidden()


@pytest.mark.parametrize("config_format", ["positional", "key_value"])
def test_rule_roundtrip_is_one_line_and_does_not_shift_other_fields(
    window, tmp_path, config_format
):
    rules = (AttemptRule("Result\nwith a label", 1, (2, 3), "asc"),)
    text = rules_json(rules)
    path = tmp_path / "race.txt"
    if config_format == "key_value":
        path.write_text(
            f"{KEY_VALUE_HEADER}\nRaceType={RACE_TYPE_NUMBER_OF_TRIES}\n"
            f"AttemptRules={text}\nHttpStageLabel=Final\n",
            encoding="utf-8",
        )
    else:
        window._cfg.attempt_rules_json = text
        window._cfg.race_type = RACE_TYPE_NUMBER_OF_TRIES
        window._cfg.http_stage_label = "Final"
        window._save_race_info_to_path(str(path))
        assert load_config_file(str(path))["attempt_rules_json"] == text
    window._load_race_info_from_path(str(path))
    assert parse_attempt_rules(window._cfg.attempt_rules_json) == rules
    assert window._cfg.http_stage_label == "Final"
    assert window._attempt_rules_editor.table.cellWidget(0, 0).text() == rules[0].label
    window._save_race_info_to_path(str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[lines.index("AttemptRules") + 1] == text


def test_loading_legacy_config_resets_previous_rules(window, tmp_path):
    window._attempt_rules_editor._add()
    path = tmp_path / "legacy.txt"
    path.write_text(f"{KEY_VALUE_HEADER}\nRaceType=Mass/Splitted\n", encoding="utf-8")
    window._load_race_info_from_path(str(path))
    assert window._cfg.attempt_rules_json == "[]"
    assert window._attempt_rules_editor.table.rowCount() == 0


def test_invalid_edit_blocks_generation_and_save_without_using_stale_rules(
    window, tmp_path, monkeypatch
):
    messages = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: messages.append(args))
    monkeypatch.setattr(
        window, "_start_generate_worker", lambda: pytest.fail("started")
    )
    window._combo_race_type.setCurrentText(RACE_TYPE_NUMBER_OF_TRIES)
    editor = window._attempt_rules_editor
    editor._add()
    editor.table.cellWidget(0, 2).setText("1,,2")
    assert editor.error.text()
    assert json.loads(window._cfg.attempt_rules_json)[0]["attempt_numbers"] == "1,,2"
    window._on_generate()
    path = tmp_path / "race.txt"
    path.write_text("preserve", encoding="utf-8")
    window._save_race_info_to_path(str(path))
    assert len(messages) == 2
    assert path.read_text(encoding="utf-8") == "preserve"


def test_invalid_loaded_rules_stay_visible_as_an_error(window, tmp_path):
    path = tmp_path / "race.txt"
    path.write_text(f"{KEY_VALUE_HEADER}\nAttemptRules=[\n", encoding="utf-8")
    window._load_race_info_from_path(str(path))
    assert window._cfg.attempt_rules_json == "["
    assert window._attempt_rules_editor.error.text()
