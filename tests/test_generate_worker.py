"""Tests for _GenerateWorker upload error logging.

Verifies that upload failures are logged via log_message (not error.emit),
and that the detailed error appears AFTER protocol-check messages (end of log).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app.config import RaceConfig
from app.main_window import _GenerateWorker

_app = QApplication.instance() or QApplication(sys.argv)


def _base_cfg(tmp_dir: str) -> RaceConfig:
    """Minimal RaceConfig pointing at example data, writing HTML to tmp_dir."""
    cfg = RaceConfig()
    cfg.start_protocol_file = "data/start.txt"
    cfg.group_time_file = "data/groups.txt"
    cfg.finish_time_file = "data/results.txt"
    cfg.group_protocol_file = str(Path(tmp_dir) / "grp.html")
    cfg.absolute_protocol_file = str(Path(tmp_dir) / "abs.html")
    cfg.use_interface_logger = False
    cfg.use_file_logger = False
    return cfg


def _run_worker(cfg: RaceConfig) -> tuple[list[str], list[str], list[str]]:
    """Run _GenerateWorker.run() synchronously.

    Returns (errors, finished_flags, log_msgs).
    """
    errors: list[str] = []
    finished: list[str] = []
    log_msgs: list[str] = []
    worker = _GenerateWorker(cfg)
    worker.error.connect(errors.append)
    worker.finished_ok.connect(lambda: finished.append("ok"))
    worker.log_message.connect(log_msgs.append)
    worker.run()
    return errors, finished, log_msgs


def _fail_with_detail(ftp_path, _login, _password, local_path, errors_out=None):
    """upload_file side_effect: returns -1, fills errors_out with realistic detail."""
    if errors_out is not None:
        filename = Path(local_path).name
        errors_out.append(f"Upload to {ftp_path}/{filename} failed: 550 No such file")
    return -1


class TestGenerateWorkerUploadSignals:
    def test_upload_failure_no_error_signal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.upload_groups = True
            cfg.ftp_path = "ftp://bad.host"

            with patch("app.main_window.upload_file", side_effect=_fail_with_detail):
                errors, *_ = _run_worker(cfg)

        assert len(errors) == 0

    def test_upload_failure_still_emits_finished(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.upload_groups = True
            cfg.ftp_path = "ftp://bad.host"

            with patch("app.main_window.upload_file", side_effect=_fail_with_detail):
                _, finished, _ = _run_worker(cfg)

        assert len(finished) == 1

    def test_upload_error_detail_logged_after_checks(self) -> None:
        """Detailed upload error must appear in log AFTER 'Checking protocol...'."""
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.upload_groups = True
            cfg.ftp_path = "ftp://host"

            with patch("app.main_window.upload_file", side_effect=_fail_with_detail):
                _, _, log_msgs = _run_worker(cfg)

        upload_idx = next(i for i, m in enumerate(log_msgs) if "Uploading" in m)
        check_idx = next(i for i, m in enumerate(log_msgs) if "Checking protocol" in m)
        error_idx = next(
            i for i, m in enumerate(log_msgs) if "ERROR" in m and "Upload to" in m
        )

        assert upload_idx < check_idx < error_idx
        assert "ftp://host" in log_msgs[error_idx]
        assert "550" in log_msgs[error_idx]

    def test_both_uploads_fail_two_errors_logged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.upload_groups = True
            cfg.upload_absolute = True
            cfg.ftp_path = "ftp://bad.host"

            with patch("app.main_window.upload_file", side_effect=_fail_with_detail):
                errors, finished, log_msgs = _run_worker(cfg)

        assert len(errors) == 0
        assert len(finished) == 1
        error_lines = [m for m in log_msgs if "ERROR" in m and "Upload to" in m]
        assert len(error_lines) == 2

    def test_upload_success_no_error_in_log(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.upload_groups = True
            cfg.ftp_path = "ftp://good.host"

            with patch("app.main_window.upload_file", return_value=0):
                errors, finished, log_msgs = _run_worker(cfg)

        assert len(errors) == 0
        assert len(finished) == 1
        assert not any("ERROR" in m and "Upload" in m for m in log_msgs)

    def test_no_upload_configured_emits_finished(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.upload_groups = False
            cfg.upload_absolute = False

            errors, finished, _ = _run_worker(cfg)

        assert len(errors) == 0
        assert len(finished) == 1
