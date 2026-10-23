"""Sending a protocol to the site as HTML, as data, or both from one run."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from app import http_io
from app.config import (
    HTTP_ACTION_UPLOAD,
    PROTOCOL_FORMAT_BOTH,
    PROTOCOL_FORMAT_DATA,
    PROTOCOL_FORMAT_HTML,
    RaceConfig,
    normalize_protocol_format,
)
from app.main_window import MainWindow, _GenerateWorker

_app = QApplication.instance() or QApplication(sys.argv)
DOCUMENT = {"schema": 1, "sections": []}
# "Race" in Russian, built from code points: source files stay ASCII.
RACE = "".join(map(chr, (0x413, 0x43E, 0x43D, 0x43A, 0x430)))


def _response(body: bytes) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = 200
    resp.read.return_value = body
    return resp


def _upload(tmp_path, answer=b'{"id": 1, "file_hash": "h"}', **kwargs):
    html = tmp_path / "gr.html"
    html.write_text("<html><body>ok</body></html>", encoding="utf-8")
    sent = {}

    def fake_urlopen(req, timeout):
        sent["body"] = req.data
        return _response(answer)

    errors: list[str] = []
    warnings: list[str] = []
    with patch("app.http_io.urllib.request.urlopen", side_effect=fake_urlopen):
        code = http_io.upload_protocol(
            "https://site.test",
            "tok",
            "group",
            str(html),
            errors_out=errors,
            warnings_out=warnings,
            **kwargs,
        )
    return code, sent.get("body", b""), errors, warnings


def test_both_parts_go_in_one_request(tmp_path):
    code, body, errors, _ = _upload(tmp_path, document=DOCUMENT)
    assert code == 0 and errors == []
    assert b'name="html_file"; filename="gr.html"' in body
    assert b'name="document"; filename="protocol.json"' in body
    assert b"Content-Type: application/json" in body
    assert json.dumps(DOCUMENT).encode() in body


def test_html_alone_as_before(tmp_path):
    _, body, _, _ = _upload(tmp_path)
    assert b'name="html_file"' in body
    assert b'name="document"' not in body


def test_data_alone_sends_no_html(tmp_path):
    code, body, _, _ = _upload(tmp_path, document=DOCUMENT, send_html=False)
    assert code == 0
    assert b'name="html_file"' not in body
    assert b'name="document"' in body


def test_document_text_keeps_its_letters(tmp_path):
    document = {"schema": 1, "title": RACE, "sections": []}
    _, body, _, _ = _upload(tmp_path, document=document)
    assert RACE.encode() in body


def test_nothing_to_send_is_an_error(tmp_path):
    code, _, errors, _ = _upload(tmp_path, send_html=False)
    assert code == -1
    assert "Nothing to upload" in errors[0]


def test_refused_document_is_a_warning_not_an_error(tmp_path):
    answer = json.dumps(
        {"id": 1, "file_hash": "h", "shown": "html", "document_error": "schema 2"}
    ).encode()
    code, _, errors, warnings = _upload(tmp_path, answer=answer, document=DOCUMENT)
    assert code == 0 and errors == []
    assert "schema 2" in warnings[0]


def test_an_older_sites_answer_is_fine(tmp_path):
    code, _, errors, warnings = _upload(tmp_path, answer=b"OK", document=DOCUMENT)
    assert (code, errors, warnings) == (0, [], [])


def _cfg(fmt: str) -> RaceConfig:
    return RaceConfig(
        http_site_url="https://s",
        http_upload_token="tok",
        group_protocol_file="g.html",
        absolute_protocol_file="a.html",
        http_groups_action=HTTP_ACTION_UPLOAD,
        http_absolute_action=HTTP_ACTION_UPLOAD,
        http_protocol_format=fmt,
    )


def _publish(cfg: RaceConfig, documents) -> list[dict]:
    calls: list[dict] = []

    def record(*args, **kwargs) -> int:
        calls.append({"type": args[2], **kwargs})
        kwargs["warnings_out"].append("refused")
        return 0

    worker = _GenerateWorker(cfg)
    logged: list[str] = []
    worker.log_message.connect(logged.append)
    with patch("app.main_window.http_upload_protocol", side_effect=record):
        worker._do_uploads(cfg, [], documents)
    assert any("WARNING" in line and "refused" in line for line in logged)
    return calls


DOCS = {"group": {"g": 1}, "absolute": {"a": 1}}


def test_both_format_sends_html_and_data():
    calls = _publish(_cfg(PROTOCOL_FORMAT_BOTH), DOCS)
    assert [(c["type"], c["document"], c["send_html"]) for c in calls] == [
        ("group", {"g": 1}, True),
        ("absolute", {"a": 1}, True),
    ]


def test_html_format_sends_no_data():
    calls = _publish(_cfg(PROTOCOL_FORMAT_HTML), DOCS)
    assert all(c["document"] is None and c["send_html"] for c in calls)


def test_data_format_sends_no_html():
    calls = _publish(_cfg(PROTOCOL_FORMAT_DATA), DOCS)
    assert all(c["document"] and not c["send_html"] for c in calls)


def test_data_format_without_data_falls_back_to_html():
    calls = _publish(_cfg(PROTOCOL_FORMAT_DATA), {})
    assert all(c["document"] is None and c["send_html"] for c in calls)


def test_documents_are_built_only_when_they_are_sent():
    worker = _GenerateWorker(_cfg(PROTOCOL_FORMAT_HTML))
    assert worker._build_documents(_cfg(PROTOCOL_FORMAT_HTML), [], [], 0) == {}
    nothing = _cfg(PROTOCOL_FORMAT_BOTH)
    nothing.http_groups_action = nothing.http_absolute_action = "Nothing"
    assert worker._build_documents(nothing, [], [], 0) == {}
    built = worker._build_documents(_cfg(PROTOCOL_FORMAT_BOTH), [], [], 0)
    assert set(built) == {"group", "absolute"}


def test_a_failing_document_build_keeps_the_html_going():
    cfg = _cfg(PROTOCOL_FORMAT_BOTH)
    worker = _GenerateWorker(cfg)
    logged: list[str] = []
    worker.log_message.connect(logged.append)
    with patch(
        "app.main_window.build_group_document", side_effect=RuntimeError("boom")
    ):
        assert worker._build_documents(cfg, [], [], 0) == {}
    assert any("protocol data not built: boom" in line for line in logged)


@pytest.mark.parametrize("value", [PROTOCOL_FORMAT_HTML, PROTOCOL_FORMAT_DATA])
def test_format_and_language_survive_save_and_load(value):
    win = MainWindow()
    try:
        win._cfg.http_protocol_format = value
        win._cfg.protocol_language = "kk"
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            win._cfg.http_protocol_format = PROTOCOL_FORMAT_BOTH
            win._cfg.protocol_language = ""
            win._load_race_info_from_path(path)
        assert win._cfg.http_protocol_format == value
        assert win._cfg.protocol_language == "kk"
    finally:
        win.deleteLater()


def test_an_old_config_without_the_format_sends_both():
    assert RaceConfig().http_protocol_format == PROTOCOL_FORMAT_BOTH
    assert normalize_protocol_format("HTML+Data typo") == PROTOCOL_FORMAT_BOTH
