"""Tests for HTTP protocol publishing in _GenerateWorker._do_uploads.

New behaviour: with at least one HTTP checkbox on, the checked protocol(s) are uploaded
and the unchecked one is deleted from the site; with neither checked, nothing happens.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.config import RACE_TYPE_ELIMINATOR_FINALS, RaceConfig
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


def test_neither_checkbox_does_nothing() -> None:
    up, dl = _run(_cfg(upload_http_groups=False, upload_http_absolute=False))
    assert up == []
    assert dl == []


def test_only_group_uploads_group_and_deletes_absolute() -> None:
    up, dl = _run(_cfg(upload_http_groups=True, upload_http_absolute=False))
    assert up == ["group"]
    assert dl == ["absolute"]


def test_only_absolute_uploads_absolute_and_deletes_group() -> None:
    up, dl = _run(_cfg(upload_http_groups=False, upload_http_absolute=True))
    assert up == ["absolute"]
    assert dl == ["group"]


def test_both_upload_both_and_delete_none() -> None:
    up, dl = _run(_cfg(upload_http_groups=True, upload_http_absolute=True))
    assert sorted(up) == ["absolute", "group"]
    assert dl == []


def test_eliminator_finals_deletes_absolute_even_if_checked() -> None:
    # In eliminator finals the absolute protocol is never uploaded, so it is removed.
    up, dl = _run(
        _cfg(
            race_type=RACE_TYPE_ELIMINATOR_FINALS,
            upload_http_groups=True,
            upload_http_absolute=True,
        )
    )
    assert up == ["group"]
    assert dl == ["absolute"]


def test_no_site_url_does_nothing() -> None:
    up, dl = _run(_cfg(http_site_url="", upload_http_groups=True))
    assert up == []
    assert dl == []
