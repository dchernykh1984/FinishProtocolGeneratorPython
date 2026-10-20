"""Rule editing and config persistence through the real main-window workflow."""

import json

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from app.attempt_rules import AttemptRule, parse_attempt_rules, rules_json
from app.config import (
    ALL_RACE_TYPES,
    RACE_TYPE_MASS_SPLITTED,
    RACE_TYPE_NUMBER_OF_TRIES,
)
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
    path.write_text(
        f"{KEY_VALUE_HEADER}\nRaceType={RACE_TYPE_NUMBER_OF_TRIES}\nAttemptRules=[\n",
        encoding="utf-8",
    )
    window._load_race_info_from_path(str(path))
    assert window._cfg.attempt_rules_json == "["
    assert window._attempt_rules_editor.error.text()


def test_invalid_rules_keep_window_open_before_any_shutdown_side_effects(
    window, monkeypatch
):
    window._cfg.race_type = RACE_TYPE_NUMBER_OF_TRIES
    window._cfg.attempt_rules_json = "["
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )
    errors, calls = [], []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args))
    monkeypatch.setattr(window, "_stop_workers", lambda: calls.append("stopped"))
    monkeypatch.setattr(
        window, "_close_time_trial_window", lambda: calls.append("closed")
    )
    monkeypatch.setattr(
        window, "_save_race_info_to_path", lambda path: calls.append("saved")
    )
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert errors
    assert not calls


@pytest.mark.parametrize("config_format", ["positional", "key_value"])
@pytest.mark.parametrize(
    "race_type", [r for r in ALL_RACE_TYPES if r != RACE_TYPE_NUMBER_OF_TRIES]
)
def test_invalid_inactive_rules_do_not_block_save_or_exit(
    window, tmp_path, monkeypatch, config_format, race_type
):
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )
    path = tmp_path / "damaged.txt"
    if config_format == "positional":
        window._cfg.race_type = race_type
        window._save_race_info_to_path(str(path))
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "AttemptRules\n[]\n", "AttemptRules\n{broken\n"
            ),
            encoding="utf-8",
        )
    else:
        path.write_text(
            f"{KEY_VALUE_HEADER}\nRaceType={race_type}\nAttemptRules={{broken\n",
            encoding="utf-8",
        )
    window._load_race_info_from_path(str(path))
    saved = tmp_path / "saved.txt"
    window._save_race_info_to_path(str(saved))
    closed_saves = []
    monkeypatch.setattr(window, "_save_race_info_to_path", closed_saves.append)
    event = QCloseEvent()
    window.closeEvent(event)
    assert (saved.exists(), event.isAccepted(), len(errors)) == (True, True, 0)
    assert closed_saves
    assert window._cfg.attempt_rules_json == "[]"
    assert load_config_file(str(saved))["attempt_rules_json"] == "[]"
    assert not window._attempt_rules_editor.error.text()


def test_valid_inactive_rules_are_preserved_for_later_use(window, tmp_path):
    text = rules_json((AttemptRule("Result", 1, (2, 3), "asc"),))
    window._cfg.attempt_rules_json = text
    path = tmp_path / "race.txt"
    window._save_race_info_to_path(str(path))
    window._load_race_info_from_path(str(path))
    assert window._cfg.race_type == RACE_TYPE_MASS_SPLITTED
    assert window._cfg.attempt_rules_json == text
