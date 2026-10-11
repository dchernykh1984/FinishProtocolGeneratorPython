"""Protocol inputs and outputs use the portable app folder, not launch cwd."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import paths
from app.config import RACE_TYPE_ELIMINATOR_QUALIFICATION, RaceConfig
from app.file_io import load_template, read_finish_times
from app.ftp_io import merge_files
from app.html_writer import write_absolute_protocol, write_group_protocol


@pytest.fixture
def race_dir(tmp_path, monkeypatch):
    race = tmp_path / "race"
    race.mkdir()
    unrelated = tmp_path / "working"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        paths.sys,
        "executable",
        str(
            race / "FinishProtocolGenerator.app/Contents/MacOS/FinishProtocolGenerator"
        ),
    )
    return race


def test_relative_inputs_and_template_are_read_next_to_app(race_dir):
    (race_dir / "results.txt").write_text("12#0 12:01:00#finish#\n", encoding="utf-8")
    (race_dir / "template.html").write_text("table-style\n", encoding="utf-8")
    assert len(read_finish_times("results.txt")) == 1
    styles = load_template("template.html")
    assert styles is not None
    assert styles.table_style == "table-style"


def test_relative_protocols_are_written_next_to_app(race_dir):
    cfg = RaceConfig(race_type=RACE_TYPE_ELIMINATOR_QUALIFICATION)
    write_group_protocol("gr.html", [], [], cfg)
    write_absolute_protocol("abs.html", [], [], cfg)
    assert (race_dir / "gr.html").exists()
    assert (race_dir / "abs.html").exists()
    assert (race_dir / "gr.html.txt").exists()
    assert not (Path.cwd() / "gr.html").exists()


def test_relative_merge_uses_app_files(race_dir):
    (race_dir / "results.txt").write_text("12#old#\n", encoding="utf-8")
    (race_dir / "download.txt").write_text("13#new#\n", encoding="utf-8")
    assert merge_files("results.txt", "download.txt", True) == 1
    assert (race_dir / "results.txt").read_text(encoding="utf-8") == (
        "12#old#\n13#new#\n"
    )


def test_site_snapshot_is_written_next_to_app(race_dir, monkeypatch):
    from app import main_window as mw

    monkeypatch.setattr(mw, "fetch_start_list", lambda *args: ["12#Rider#GroupA#"])
    cfg = RaceConfig(
        start_protocol_file="data/start.txt",
        http_site_url="https://site.test",
        http_upload_token="test-token",
    )
    worker = mw._FTPWorker(cfg)
    assert worker._fetch_start_list_from_site(cfg)
    assert (race_dir / "data/start.txt").read_text(encoding="utf-8") == (
        "12#Rider#GroupA#\n"
    )
    assert cfg.start_protocol_file == "data/start.txt"


def test_relative_race_config_round_trip_uses_app_folder(race_dir, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from app import main_window as mw

    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(mw.MainWindow, "_try_auto_load", lambda self: None)
    window = mw.MainWindow()
    try:
        window._cfg.start_protocol_file = "start.txt"
        window._save_race_info_to_path("fpg_info.txt")
        assert (race_dir / "fpg_info.txt").exists()
        window._cfg.start_protocol_file = "changed.txt"
        window._load_race_info_from_path("fpg_info.txt")
        assert window._cfg.start_protocol_file == "start.txt"
        assert not (Path.cwd() / "fpg_info.txt").exists()
    finally:
        window.deleteLater()
        application.processEvents()


def test_http_upload_reads_protocol_next_to_app(race_dir, monkeypatch):
    from unittest.mock import MagicMock

    from app import http_io

    (race_dir / "gr.html").write_text("right-protocol", encoding="utf-8")
    (Path.cwd() / "gr.html").write_text("wrong-protocol", encoding="utf-8")
    response = MagicMock()
    response.status = 200
    response.__enter__.return_value = response
    send = MagicMock(return_value=response)
    monkeypatch.setattr(http_io.urllib.request, "urlopen", send)
    assert (
        http_io.upload_protocol("https://site.test", "test-token", "groups", "gr.html")
        == 0
    )
    body = send.call_args.args[0].data
    assert b"right-protocol" in body
    assert b"wrong-protocol" not in body
