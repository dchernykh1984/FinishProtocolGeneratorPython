"""Tests for the "Start list source = site" pre-generation step in _FTPWorker.

When the source is the site the worker fetches the merged start list and writes it to
the local start file; on any fetch error the local file is left untouched.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.config import START_LIST_SOURCE_LOCAL, START_LIST_SOURCE_SITE, RaceConfig
from app.main_window import _FTPWorker

_app = QApplication.instance() or QApplication(sys.argv)


def _run_ftp_worker(cfg: RaceConfig) -> tuple[list[str], list[str], list[str]]:
    """Run _FTPWorker.run() synchronously: (finished_ok, finished_with_errors, logs)."""
    ok: list[str] = []
    err: list[str] = []
    log: list[str] = []
    worker = _FTPWorker(cfg)
    worker.finished_ok.connect(lambda: ok.append("ok"))
    worker.finished_with_errors.connect(lambda: err.append("err"))
    worker.log_message.connect(log.append)
    worker.run()
    return ok, err, log


def _cfg(tmp: str, source: str) -> RaceConfig:
    cfg = RaceConfig()
    cfg.start_list_source = source
    cfg.http_site_url = "https://site.com"
    cfg.http_upload_token = "tok"
    cfg.start_protocol_file = str(Path(tmp) / "start.txt")
    cfg.use_interface_logger = False
    cfg.use_file_logger = False
    return cfg


class TestStartListSiteSource:
    def test_site_source_writes_fetched_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, START_LIST_SOURCE_SITE)
            with patch(
                "app.main_window.fetch_start_list",
                return_value=["1#A##1#", "2#B##1#"],
            ):
                ok, err, _ = _run_ftp_worker(cfg)
            content = Path(cfg.start_protocol_file).read_text(encoding="utf-8")
        assert ok and not err
        assert content == "1#A##1#\n2#B##1#\n"

    def test_fetch_error_does_not_overwrite_local(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, START_LIST_SOURCE_SITE)
            Path(cfg.start_protocol_file).write_text("local#data#\n", encoding="utf-8")
            with patch(
                "app.main_window.fetch_start_list",
                side_effect=ValueError("HTTP 500: Server Error"),
            ):
                ok, err, log = _run_ftp_worker(cfg)
            content = Path(cfg.start_protocol_file).read_text(encoding="utf-8")
        # Local file is preserved and the run reports errors.
        assert content == "local#data#\n"
        assert err and not ok
        assert any("ERROR" in m for m in log)

    def test_missing_credentials_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, START_LIST_SOURCE_SITE)
            cfg.http_site_url = ""
            ok, err, log = _run_ftp_worker(cfg)
        assert err and not ok
        assert any("ERROR" in m for m in log)

    def test_local_source_neither_fetches_nor_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, START_LIST_SOURCE_LOCAL)
            Path(cfg.start_protocol_file).write_text("local#data#\n", encoding="utf-8")
            with patch(
                "app.main_window.fetch_start_list",
                side_effect=AssertionError("must not be called for local source"),
            ):
                ok, err, _ = _run_ftp_worker(cfg)
            content = Path(cfg.start_protocol_file).read_text(encoding="utf-8")
        assert ok and not err
        assert content == "local#data#\n"
