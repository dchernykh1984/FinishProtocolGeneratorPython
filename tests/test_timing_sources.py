"""Tests for the "timing source = site" pre-generation step in _FTPWorker.

When a group/finish/remote source is the site, the worker fetches the merged stream and
writes it to the matching local file(s) (group_time_file, finish_time_file,
results_<n>.txt) before generation; on a fetch error the local files are left untouched.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.config import START_LIST_SOURCE_LOCAL, START_LIST_SOURCE_SITE, RaceConfig
from app.main_window import _effective_ftp_actions, _FTPWorker

_app = QApplication.instance() or QApplication(sys.argv)


def _run(cfg: RaceConfig) -> tuple[list[str], list[str], list[str]]:
    ok: list[str] = []
    err: list[str] = []
    log: list[str] = []
    worker = _FTPWorker(cfg)
    worker.finished_ok.connect(lambda: ok.append("ok"))
    worker.finished_with_errors.connect(lambda: err.append("err"))
    worker.log_message.connect(log.append)
    worker.run()
    return ok, err, log


def _cfg(tmp: str) -> RaceConfig:
    cfg = RaceConfig()
    cfg.http_site_url = "https://site.com"
    cfg.http_upload_token = "tok"
    cfg.group_time_file = str(Path(tmp) / "groups.txt")
    cfg.finish_time_file = str(Path(tmp) / "results.txt")
    cfg.remote_points_path = str(Path(tmp) / "rp")
    cfg.n_remote_points = 2
    cfg.use_interface_logger = False
    cfg.use_file_logger = False
    return cfg


class TestGroupTimesSiteSource:
    def test_writes_fetched_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.group_times_source = START_LIST_SOURCE_SITE
            with patch(
                "app.main_window.fetch_group_times", return_value=["G1#0 0:0:1#"]
            ):
                ok, err, _ = _run(cfg)
            content = Path(cfg.group_time_file).read_text(encoding="utf-8")
        assert ok and not err
        assert content == "G1#0 0:0:1#\n"

    def test_fetch_error_preserves_local(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.group_times_source = START_LIST_SOURCE_SITE
            Path(cfg.group_time_file).write_text("local#\n", encoding="utf-8")
            with patch(
                "app.main_window.fetch_group_times", side_effect=ValueError("HTTP 500")
            ):
                ok, err, log = _run(cfg)
            content = Path(cfg.group_time_file).read_text(encoding="utf-8")
        assert content == "local#\n"
        assert err and not ok
        assert any("ERROR" in m for m in log)

    def test_site_source_ignores_stale_ftp_action(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.group_times_source = START_LIST_SOURCE_SITE
            cfg.group_times_action = "Download"
            with (
                patch("app.main_window.fetch_group_times", return_value=["site#"]),
                patch(
                    "app.main_window.download_file",
                    side_effect=AssertionError("must not use FTP"),
                ),
            ):
                ok, err, log = _run(cfg)
            content = Path(cfg.group_time_file).read_text(encoding="utf-8")
        assert ok and not err
        assert content == "site#\n"
        assert any(
            "Group times source conflict" in message and "using HTTP data" in message
            for message in log
        )

    def test_site_source_action_does_not_count_as_ftp_action(self) -> None:
        cfg = RaceConfig()
        cfg.group_times_source = START_LIST_SOURCE_SITE
        cfg.group_times_action = "Download"
        assert _effective_ftp_actions(cfg)["group_times"] == "None"


class TestFinishTimesSiteSource:
    def test_writes_fetched_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.finish_times_source = START_LIST_SOURCE_SITE
            with patch(
                "app.main_window.fetch_finish_times", return_value=["1#0 0:9:9#finish#"]
            ):
                ok, err, _ = _run(cfg)
            content = Path(cfg.finish_time_file).read_text(encoding="utf-8")
        assert ok and not err
        assert content == "1#0 0:9:9#finish#\n"

    def test_local_source_does_not_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.finish_times_source = START_LIST_SOURCE_LOCAL
            Path(cfg.finish_time_file).write_text("keep#\n", encoding="utf-8")
            with patch(
                "app.main_window.fetch_finish_times",
                side_effect=AssertionError("must not fetch for local source"),
            ):
                ok, err, _ = _run(cfg)
            content = Path(cfg.finish_time_file).read_text(encoding="utf-8")
        assert ok and not err
        assert content == "keep#\n"


class TestRemotePointsSiteSource:
    def test_writes_one_file_per_point(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.remote_points_source = START_LIST_SOURCE_SITE
            points = {1: ["1#0 0:1:0#", "2#0 0:1:5#"], 2: ["1#0 0:2:0#"]}
            with patch("app.main_window.fetch_remote_points", return_value=points):
                ok, err, _ = _run(cfg)
            p1 = Path(cfg.remote_points_path) / "results_1.txt"
            p2 = Path(cfg.remote_points_path) / "results_2.txt"
            c1 = p1.read_text(encoding="utf-8")
            c2 = p2.read_text(encoding="utf-8")
        assert ok and not err
        assert c1 == "1#0 0:1:0#\n2#0 0:1:5#\n"
        assert c2 == "1#0 0:2:0#\n"

    def test_missing_point_writes_empty_file(self) -> None:
        # n_remote_points=2 but the site has only point 1 -> point 2 file written empty.
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.remote_points_source = START_LIST_SOURCE_SITE
            with patch(
                "app.main_window.fetch_remote_points", return_value={1: ["1#0 0:1:0#"]}
            ):
                ok, err, _ = _run(cfg)
            p2 = Path(cfg.remote_points_path) / "results_2.txt"
            content = p2.read_text(encoding="utf-8")
        assert ok and not err
        assert content == ""

    def test_fetch_error_preserves_local(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.remote_points_source = START_LIST_SOURCE_SITE
            Path(cfg.remote_points_path).mkdir(parents=True, exist_ok=True)
            p1 = Path(cfg.remote_points_path) / "results_1.txt"
            p1.write_text("local#\n", encoding="utf-8")
            with patch(
                "app.main_window.fetch_remote_points",
                side_effect=ValueError("HTTP 500"),
            ):
                ok, err, log = _run(cfg)
            content = p1.read_text(encoding="utf-8")
        assert content == "local#\n"
        assert err and not ok
        assert any("ERROR" in m for m in log)

    def test_partial_write_error_reports_but_writes_others(self) -> None:
        # If writing point 2 fails, point 1 is still written and the run reports errors.
        from app import main_window as mw

        real_write = mw._FTPWorker._write_lines

        def flaky_write(self, path, lines, label):
            if path.endswith("results_2.txt"):
                self.log_message.emit(f"  ERROR: cannot write {label}")
                return False
            return real_write(self, path, lines, label)

        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            cfg.remote_points_source = START_LIST_SOURCE_SITE
            points = {1: ["1#0 0:1:0#"], 2: ["1#0 0:2:0#"]}
            with (
                patch("app.main_window.fetch_remote_points", return_value=points),
                patch.object(mw._FTPWorker, "_write_lines", flaky_write),
            ):
                ok, err, log = _run(cfg)
            c1 = (Path(cfg.remote_points_path) / "results_1.txt").read_text(
                encoding="utf-8"
            )
        assert c1 == "1#0 0:1:0#\n"
        assert err and not ok
        assert any("ERROR" in m for m in log)
