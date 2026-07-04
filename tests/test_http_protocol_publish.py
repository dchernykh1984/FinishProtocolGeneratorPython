"""Tests for HTTP protocol publishing in _GenerateWorker._do_uploads.

Behaviour: each protocol has an independent action -- Nothing (leave the site alone),
Upload (publish it) or Delete (remove it from the site).
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.config import (
    HTTP_ACTION_DELETE,
    HTTP_ACTION_NOTHING,
    HTTP_ACTION_UPLOAD,
    RACE_TYPE_ELIMINATOR_FINALS,
    RaceConfig,
)
from app.main_window import _GenerateWorker

_app = QApplication.instance() or QApplication(sys.argv)


def _cfg(**kw) -> RaceConfig:
    cfg = RaceConfig()
    cfg.http_site_url = "https://s"
    cfg.http_upload_token = "tok"
    cfg.group_protocol_file = "g.html"
    cfg.absolute_protocol_file = "a.html"
    for key, value in kw.items():
        setattr(cfg, key, value)
    return cfg


def _run(cfg: RaceConfig) -> tuple[list[str], list[str]]:
    uploaded: list[str] = []
    deleted: list[str] = []

    def record_upload(*a, **k) -> int:
        uploaded.append(a[2])  # a[2] is protocol_type
        return 0

    def record_delete(*a, **k) -> int:
        deleted.append(a[2])
        return 0

    worker = _GenerateWorker(cfg)
    with (
        patch("app.main_window.http_upload_protocol", side_effect=record_upload),
        patch("app.main_window.http_delete_protocol", side_effect=record_delete),
    ):
        worker._do_uploads(cfg)
    return uploaded, deleted


def test_both_nothing_does_nothing() -> None:
    up, dl = _run(
        _cfg(
            http_groups_action=HTTP_ACTION_NOTHING,
            http_absolute_action=HTTP_ACTION_NOTHING,
        )
    )
    assert up == []
    assert dl == []


def test_default_config_does_nothing() -> None:
    # Nothing is the default action, so a fresh config touches neither protocol.
    up, dl = _run(_cfg())
    assert up == []
    assert dl == []


def test_group_upload_only() -> None:
    up, dl = _run(
        _cfg(
            http_groups_action=HTTP_ACTION_UPLOAD,
            http_absolute_action=HTTP_ACTION_NOTHING,
        )
    )
    assert up == ["group"]
    assert dl == []


def test_group_delete_only() -> None:
    up, dl = _run(
        _cfg(
            http_groups_action=HTTP_ACTION_DELETE,
            http_absolute_action=HTTP_ACTION_NOTHING,
        )
    )
    assert up == []
    assert dl == ["group"]


def test_absolute_upload_only() -> None:
    up, dl = _run(
        _cfg(
            http_groups_action=HTTP_ACTION_NOTHING,
            http_absolute_action=HTTP_ACTION_UPLOAD,
        )
    )
    assert up == ["absolute"]
    assert dl == []


def test_both_upload() -> None:
    up, dl = _run(
        _cfg(
            http_groups_action=HTTP_ACTION_UPLOAD,
            http_absolute_action=HTTP_ACTION_UPLOAD,
        )
    )
    assert sorted(up) == ["absolute", "group"]
    assert dl == []


def test_upload_group_delete_absolute() -> None:
    up, dl = _run(
        _cfg(
            http_groups_action=HTTP_ACTION_UPLOAD,
            http_absolute_action=HTTP_ACTION_DELETE,
        )
    )
    assert up == ["group"]
    assert dl == ["absolute"]


def test_eliminator_finals_absolute_upload_falls_back_to_delete() -> None:
    # In eliminator finals the absolute protocol is never uploaded; an Upload request
    # removes any stale copy from the site instead.
    up, dl = _run(
        _cfg(
            race_type=RACE_TYPE_ELIMINATOR_FINALS,
            http_groups_action=HTTP_ACTION_UPLOAD,
            http_absolute_action=HTTP_ACTION_UPLOAD,
        )
    )
    assert up == ["group"]
    assert dl == ["absolute"]


def test_no_site_url_does_nothing() -> None:
    up, dl = _run(_cfg(http_site_url="", http_groups_action=HTTP_ACTION_UPLOAD))
    assert up == []
    assert dl == []


def test_unknown_action_does_nothing_not_delete() -> None:
    # A corrupt/typo action value must not fall through to deleting the protocol.
    up, dl = _run(_cfg(http_groups_action="Uplaod", http_absolute_action="garbage"))
    assert up == []
    assert dl == []
