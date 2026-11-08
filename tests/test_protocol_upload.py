"""Sending a protocol to the site as HTML, as data, or both from one run."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
)

from app import http_io
from app.config import (
    HTTP_ACTION_UPLOAD,
    PROTOCOL_FORMAT_BOTH,
    PROTOCOL_FORMAT_DATA,
    PROTOCOL_FORMAT_HTML,
    RaceConfig,
    normalize_protocol_format,
)
from app.eliminator import (
    SEEDING_KEEP_ADJACENT,
    SEEDING_SPLIT_ADJACENT,
)
from app.file_io import KEY_VALUE_HEADER
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


def test_an_upload_names_its_section(tmp_path):
    _, first, _, _ = _upload(tmp_path)
    _, fourth, _, _ = _upload(tmp_path, section=4)
    assert b'name="section"\r\n\r\n1\r\n' in first
    assert b'name="section"\r\n\r\n4\r\n' in fourth


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


def test_the_eliminator_settings_survive_save_and_load():
    win = MainWindow()
    try:
        win._cfg.eliminator_small_final = False
        win._cfg.eliminator_seeding = SEEDING_KEEP_ADJACENT
        win._cfg.eliminator_laps = 3
        win._cfg.eliminator_ladder_file = "finals/ladders.txt"
        win._cfg.not_ridden_label = "unraced"
        win._cfg.show_qualification_place = False
        win._cfg.qualification_place_label = "Qual."
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            win._cfg.eliminator_small_final = True
            win._cfg.eliminator_seeding = SEEDING_SPLIT_ADJACENT
            win._cfg.eliminator_laps = 1
            win._cfg.eliminator_ladder_file = "ladders.txt"
            win._cfg.not_ridden_label = ""
            win._cfg.show_qualification_place = True
            win._cfg.qualification_place_label = ""
            win._load_race_info_from_path(path)
        assert win._cfg.eliminator_small_final is False
        assert win._cfg.eliminator_seeding == SEEDING_KEEP_ADJACENT
        assert win._cfg.eliminator_laps == 3
        assert win.findChild(QSpinBox, "eliminator_laps").value() == 3
        assert win._cfg.eliminator_ladder_file == "finals/ladders.txt"
        assert (
            win.findChild(QComboBox, "eliminator_seeding").currentText()
            == SEEDING_KEEP_ADJACENT
        )
        assert win._cfg.not_ridden_label == "unraced"
        assert not win.findChild(QCheckBox, "eliminator_small_final").isChecked()
        assert win._cfg.show_qualification_place is False
        assert win._cfg.qualification_place_label == "Qual."
        assert not win.findChild(QCheckBox, "show_qualification_place").isChecked()
    finally:
        win.deleteLater()


def test_a_config_without_the_tags_does_not_inherit_the_last_meetings_scheme():
    """The quiet reseeding the scheme setting exists to prevent.

    A file that does not carry the scheme means the regulations' default, not what
    the previous race left in the window -- nothing on screen would show that the
    ladder had been reseeded.
    """
    win = MainWindow()
    try:
        win._cfg.eliminator_seeding = SEEDING_KEEP_ADJACENT
        win._cfg.eliminator_small_final = False
        win._cfg.eliminator_laps = 4
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            win._save_race_info_to_path(str(path))
            text = path.read_text(encoding="utf-8")
            older, _, _ = text.partition("EliminatorSmallFinal\n")
            path.write_text(older, encoding="utf-8")
            win._load_race_info_from_path(str(path))
        assert win._cfg.eliminator_seeding == SEEDING_SPLIT_ADJACENT
        assert win._cfg.eliminator_small_final is True
        assert (
            win.findChild(QComboBox, "eliminator_seeding").currentText()
            == SEEDING_SPLIT_ADJACENT
        )
    finally:
        win.deleteLater()


def test_a_key_value_config_without_the_tags_does_not_inherit_them_either():
    win = MainWindow()
    try:
        win._cfg.eliminator_seeding = SEEDING_KEEP_ADJACENT
        win._cfg.eliminator_small_final = False
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            path.write_text(KEY_VALUE_HEADER + "\nRaceName: Test\n", encoding="utf-8")
            win._load_race_info_from_path(str(path))
        assert win._cfg.eliminator_seeding == SEEDING_SPLIT_ADJACENT
        assert win._cfg.eliminator_small_final is True
    finally:
        win.deleteLater()


def test_a_config_without_the_eliminator_tags_keeps_the_defaults():
    # Written by a build that predates them: the tag chain simply ends earlier.
    win = MainWindow()
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            win._save_race_info_to_path(str(path))
            text = path.read_text(encoding="utf-8")
            older, _, _ = text.partition("EliminatorLadderFile\n")
            path.write_text(older, encoding="utf-8")
            win._cfg.eliminator_small_final = False
            win._load_race_info_from_path(str(path))
        assert win._cfg.eliminator_small_final is True
        assert win._cfg.eliminator_seeding == SEEDING_SPLIT_ADJACENT
        assert win._cfg.eliminator_ladder_file == "ladders.txt"
    finally:
        win.deleteLater()


def test_an_old_config_without_the_format_sends_both():
    assert RaceConfig().http_protocol_format == PROTOCOL_FORMAT_BOTH
    assert normalize_protocol_format("HTML+Data typo") == PROTOCOL_FORMAT_BOTH


def _window_after_loading(text: str) -> MainWindow:
    win = MainWindow()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "fpg_info.txt"
        path.write_text(text, encoding="utf-8")
        win._cfg.http_protocol_format = PROTOCOL_FORMAT_BOTH
        win._combo_protocol_format.setCurrentText(PROTOCOL_FORMAT_BOTH)
        win._load_race_info_from_path(str(path))
    return win


def test_loaded_format_shows_in_the_window_from_the_saved_file():
    win = MainWindow()
    try:
        win._cfg.http_protocol_format = PROTOCOL_FORMAT_DATA
        win._cfg.protocol_language = "kk"
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "fpg_info.txt")
            win._save_race_info_to_path(path)
            text = Path(path).read_text(encoding="utf-8")
    finally:
        win.deleteLater()
    loaded = _window_after_loading(text)
    try:
        assert loaded._cfg.http_protocol_format == PROTOCOL_FORMAT_DATA
        assert loaded._combo_protocol_format.currentText() == PROTOCOL_FORMAT_DATA
        assert loaded.findChild(QLineEdit, "protocol_language").text() == "kk"
    finally:
        loaded.deleteLater()


def test_loaded_format_shows_in_the_window_from_a_key_value_file():
    from app.file_io import KEY_VALUE_HEADER

    text = f"{KEY_VALUE_HEADER}\nHttpProtocolFormat=Data\nProtocolLanguage=en\nEnd\n"
    loaded = _window_after_loading(text)
    try:
        assert loaded._cfg.http_protocol_format == PROTOCOL_FORMAT_DATA
        assert loaded._combo_protocol_format.currentText() == PROTOCOL_FORMAT_DATA
        assert loaded.findChild(QLineEdit, "protocol_language").text() == "en"
    finally:
        loaded.deleteLater()


def _refusing(tmp_path, **kwargs):
    import io
    import urllib.error

    html = tmp_path / "gr.html"
    html.write_text("<html></html>", encoding="utf-8")

    def refuse(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"detail": "too big"}')
        )

    errors: list[str] = []
    warnings: list[str] = []
    with patch("app.http_io.urllib.request.urlopen", side_effect=refuse):
        code = http_io.upload_protocol(
            "https://s",
            "tok",
            "group",
            str(html),
            errors_out=errors,
            warnings_out=warnings,
            **kwargs,
        )
    return code, errors, warnings


def test_a_refused_data_only_upload_is_told_apart_with_the_reason(tmp_path):
    code, errors, warnings = _refusing(tmp_path, document=DOCUMENT, send_html=False)
    assert code == http_io.REFUSED_DATA
    assert errors == []
    assert "too big" in warnings[0]


def test_a_refused_upload_with_html_stays_an_error(tmp_path):
    code, errors, _ = _refusing(tmp_path, document=DOCUMENT)
    assert code == -1
    assert "400" in errors[0]


def test_refused_data_only_publishes_the_html_instead():
    cfg = _cfg(PROTOCOL_FORMAT_DATA)
    cfg.http_absolute_action = "Nothing"
    calls: list[dict] = []

    def site(*args, **kwargs):
        calls.append(kwargs)
        if not kwargs["send_html"]:
            kwargs["warnings_out"].append("The site refused the protocol data: too big")
            return http_io.REFUSED_DATA
        return 0

    worker = _GenerateWorker(cfg)
    logged: list[str] = []
    worker.log_message.connect(logged.append)
    with patch("app.main_window.http_upload_protocol", side_effect=site):
        failed, errors = worker._do_uploads(cfg, [], DOCS)
    assert not failed and errors == []
    assert [(c["document"] is not None, c["send_html"]) for c in calls] == [
        (True, False),
        (False, True),
    ]
    assert any("too big" in line for line in logged)
    assert any("HTML was published instead" in line for line in logged)


def test_the_section_survives_save_and_load_and_a_file_without_it_is_the_first():
    win = MainWindow()
    try:
        win._cfg.http_section = 4
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fpg_info.txt"
            win._save_race_info_to_path(str(path))
            text = path.read_text(encoding="utf-8")
            # After every tag an older version knows, and newer tags go after it:
            # the reader walks them in the order they are written.
            older, marker, newer = text.partition("HttpSection\n4\n")
            assert marker
            assert "HttpSection" not in older
            assert "EliminatorLadderFile" in newer
            win._cfg.http_section = 2
            win._load_race_info_from_path(str(path))
            assert win._cfg.http_section == 4
            assert win.findChild(QSpinBox, "http_section").value() == 4
            broken = (older + "HttpSection\n0\n", older + "HttpSection\nx\n")
            for saved in (older, *broken):
                win._cfg.http_section = 4
                path.write_text(saved, encoding="utf-8")
                win._load_race_info_from_path(str(path))
                assert win._cfg.http_section == 1, saved[-30:]
    finally:
        win.deleteLater()
