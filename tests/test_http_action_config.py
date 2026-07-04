"""Save/load and legacy-migration tests for the per-protocol HTTP actions.

The two upload checkboxes were replaced by two action fields (Nothing/Upload/Delete).
Old configs stored the checkboxes as UploadHttpGroups/UploadHttpAbsolute booleans and
must still migrate to the new actions on load.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.config import (
    HTTP_ACTION_DELETE,
    HTTP_ACTION_NOTHING,
    HTTP_ACTION_UPLOAD,
    migrate_http_actions,
    normalize_http_action,
)
from app.main_window import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)


def test_normalize_http_action() -> None:
    # Known values pass through unchanged.
    assert normalize_http_action(HTTP_ACTION_NOTHING) == HTTP_ACTION_NOTHING
    assert normalize_http_action(HTTP_ACTION_UPLOAD) == HTTP_ACTION_UPLOAD
    assert normalize_http_action(HTTP_ACTION_DELETE) == HTTP_ACTION_DELETE
    # Anything unrecognised (typo, empty, garbage) collapses to the safe default.
    assert normalize_http_action("Uplaod") == HTTP_ACTION_NOTHING
    assert normalize_http_action("") == HTTP_ACTION_NOTHING
    assert normalize_http_action("delete") == HTTP_ACTION_NOTHING


def test_migrate_http_actions_pairs() -> None:
    # Legacy: neither checked -> nothing happened at all.
    assert migrate_http_actions(False, False) == (
        HTTP_ACTION_NOTHING,
        HTTP_ACTION_NOTHING,
    )
    # Legacy: one checked -> upload it, delete the other.
    assert migrate_http_actions(True, False) == (
        HTTP_ACTION_UPLOAD,
        HTTP_ACTION_DELETE,
    )
    assert migrate_http_actions(False, True) == (
        HTTP_ACTION_DELETE,
        HTTP_ACTION_UPLOAD,
    )
    # Legacy: both checked -> upload both.
    assert migrate_http_actions(True, True) == (
        HTTP_ACTION_UPLOAD,
        HTTP_ACTION_UPLOAD,
    )


def test_save_then_load_preserves_actions() -> None:
    win = MainWindow()
    try:
        win._cfg.http_groups_action = HTTP_ACTION_UPLOAD
        win._cfg.http_absolute_action = HTTP_ACTION_DELETE
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            win._cfg.http_groups_action = HTTP_ACTION_NOTHING
            win._cfg.http_absolute_action = HTTP_ACTION_NOTHING
            win._load_race_info_from_path(path)
        assert win._cfg.http_groups_action == HTTP_ACTION_UPLOAD
        assert win._cfg.http_absolute_action == HTTP_ACTION_DELETE
    finally:
        win.deleteLater()


def test_legacy_upload_flags_migrate_on_load() -> None:
    win = MainWindow()
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            # Deterministic pre-save values so the tag rewrite below matches.
            win._cfg.http_groups_action = HTTP_ACTION_NOTHING
            win._cfg.http_absolute_action = HTTP_ACTION_NOTHING
            win._save_race_info_to_path(str(path))
            # Rewrite the new action tags as the old boolean checkbox tags.
            text = path.read_text(encoding="utf-8")
            text = text.replace("HttpGroupsAction\nNothing", "UploadHttpGroups\n1")
            text = text.replace("HttpAbsoluteAction\nNothing", "UploadHttpAbsolute\n0")
            path.write_text(text, encoding="utf-8")
            win._cfg.http_groups_action = HTTP_ACTION_NOTHING
            win._cfg.http_absolute_action = HTTP_ACTION_NOTHING
            win._load_race_info_from_path(str(path))
        # UploadHttpGroups=1, UploadHttpAbsolute=0 -> upload group, delete absolute.
        assert win._cfg.http_groups_action == HTTP_ACTION_UPLOAD
        assert win._cfg.http_absolute_action == HTTP_ACTION_DELETE
    finally:
        win.deleteLater()


def test_unknown_action_normalized_to_nothing_on_load() -> None:
    win = MainWindow()
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            win._cfg.http_groups_action = HTTP_ACTION_UPLOAD
            win._cfg.http_absolute_action = HTTP_ACTION_UPLOAD
            win._save_race_info_to_path(str(path))
            # Corrupt the saved value with a typo, as a hand-edited file might have.
            text = path.read_text(encoding="utf-8")
            text = text.replace("HttpGroupsAction\nUpload", "HttpGroupsAction\nUplaod")
            path.write_text(text, encoding="utf-8")
            win._load_race_info_from_path(str(path))
        # Typo -> safe default; the valid neighbour still loads normally.
        assert win._cfg.http_groups_action == HTTP_ACTION_NOTHING
        assert win._cfg.http_absolute_action == HTTP_ACTION_UPLOAD
    finally:
        win.deleteLater()
