"""Tests for ftp_io merge utilities (pure logic, no network calls)."""

from __future__ import annotations

import ftplib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ftp_io import merge_files, similar_strings, upload_file


class TestSimilarStrings:
    def test_full_match(self) -> None:
        assert similar_strings("1#Alice#G", "1#Alice#G", only_id=False)

    def test_full_no_match(self) -> None:
        assert not similar_strings("1#Alice#G", "1#Bob#G", only_id=False)

    def test_id_only_same_id_different_name(self) -> None:
        assert similar_strings("1#Alice#G", "1#Bob#G", only_id=True)

    def test_id_only_different_id(self) -> None:
        assert not similar_strings("1#Alice#G", "2#Alice#G", only_id=True)

    def test_id_only_no_hash(self) -> None:
        assert similar_strings("42", "42", only_id=True)
        assert not similar_strings("42", "43", only_id=True)

    def test_trailing_newline_ignored_full(self) -> None:
        assert similar_strings("1#Alice\n", "1#Alice", only_id=False)

    def test_trailing_cr_lf_ignored(self) -> None:
        assert similar_strings("1#Alice\r\n", "1#Alice", only_id=False)


class TestMergeFiles:
    def _make(self, lines: list[str], encoding: str = "utf-8") -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding=encoding
        ) as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
            return f.name

    def test_adds_new_lines_from_source(self) -> None:
        to_f = self._make(["1#Alice#G"])
        from_f = self._make(["2#Bob#G"])
        added = merge_files(to_f, from_f, merge_by_id=False)
        assert added == 1
        content = Path(to_f).read_text(encoding="utf-8")
        assert "1#Alice#G" in content
        assert "2#Bob#G" in content

    def test_skips_exact_duplicates(self) -> None:
        to_f = self._make(["1#Alice#G"])
        from_f = self._make(["1#Alice#G"])
        added = merge_files(to_f, from_f, merge_by_id=False)
        assert added == 0
        lines = [ln for ln in Path(to_f).read_text(encoding="utf-8").splitlines() if ln]
        assert lines.count("1#Alice#G") == 1

    def test_from_file_replaces_matching_to_line_by_id(self) -> None:
        to_f = self._make(["1#Alice#G#old"])
        from_f = self._make(["1#Alice#G#new"])
        merge_files(to_f, from_f, merge_by_id=True)
        content = Path(to_f).read_text(encoding="utf-8")
        assert "1#Alice#G#new" in content
        assert "1#Alice#G#old" not in content

    def test_from_file_replaces_by_full_line(self) -> None:
        to_f = self._make(["1#Alice#G"])
        from_f = self._make(["1#Alice#G"])
        merge_files(to_f, from_f, merge_by_id=False)
        lines = [ln for ln in Path(to_f).read_text(encoding="utf-8").splitlines() if ln]
        assert lines.count("1#Alice#G") == 1

    def test_deduplicates_within_to_file(self) -> None:
        to_f = self._make(["1#Alice#G", "1#Alice#G"])
        from_f = self._make([])
        merge_files(to_f, from_f, merge_by_id=False)
        lines = [ln for ln in Path(to_f).read_text(encoding="utf-8").splitlines() if ln]
        assert lines.count("1#Alice#G") == 1

    def test_deduplicates_within_from_file(self) -> None:
        to_f = self._make([])
        from_f = self._make(["1#Alice#G", "1#Alice#G"])
        merge_files(to_f, from_f, merge_by_id=False)
        lines = [ln for ln in Path(to_f).read_text(encoding="utf-8").splitlines() if ln]
        assert lines.count("1#Alice#G") == 1

    def test_merge_into_nonexistent_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            to_f = str(Path(tmpdir) / "output.txt")
            from_f = self._make(["1#Alice#G", "2#Bob#G"])
            added = merge_files(to_f, from_f, merge_by_id=False)
            assert added == 2
            assert Path(to_f).exists()

    def test_error_on_missing_from_file(self) -> None:
        to_f = self._make(["1#Alice#G"])
        result = merge_files(to_f, "/nonexistent/path.txt", merge_by_id=False)
        assert result == -1

    def test_merge_by_id_different_ids_both_kept(self) -> None:
        to_f = self._make(["1#Alice#G"])
        from_f = self._make(["2#Bob#G"])
        added = merge_files(to_f, from_f, merge_by_id=True)
        assert added == 1
        content = Path(to_f).read_text(encoding="utf-8")
        assert "1#Alice#G" in content
        assert "2#Bob#G" in content

    def test_empty_lines_ignored(self) -> None:
        to_f = self._make(["1#Alice#G", "", "   "])
        from_f = self._make(["2#Bob#G"])
        merge_files(to_f, from_f, merge_by_id=False)
        lines = [
            ln
            for ln in Path(to_f).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        assert len(lines) == 2

    @pytest.mark.parametrize("merge_by_id", [True, False])
    def test_multiple_new_lines_counted(self, merge_by_id: bool) -> None:
        to_f = self._make(["1#Alice#G"])
        from_f = self._make(["2#Bob#G", "3#Eve#G"])
        added = merge_files(to_f, from_f, merge_by_id=merge_by_id)
        assert added == 2

    def test_from_file_keeps_last_duplicate_by_id(self) -> None:
        to_f = self._make([])
        from_f = self._make(["1#Alice#G#first", "1#Alice#G#last"])
        merge_files(to_f, from_f, merge_by_id=True)
        content = Path(to_f).read_text(encoding="utf-8")
        assert "1#Alice#G#last" in content
        assert "1#Alice#G#first" not in content

    def test_cp1251_cyrillic_preserved(self) -> None:
        ivan = "\u0418\u0432\u0430\u043d"  # Ivan
        maria = "\u041c\u0430\u0440\u0438\u044f"  # Maria
        to_f = self._make([f"1#{ivan}#G"], encoding="cp1251")
        from_f = self._make([f"2#{maria}#G"], encoding="cp1251")
        added = merge_files(to_f, from_f, merge_by_id=False)
        assert added == 1
        content = Path(to_f).read_text(encoding="utf-8")
        assert ivan in content
        assert maria in content


class TestUploadFile:
    """Unit tests for upload_file \u2014 ftplib calls are mocked, no real network."""

    def _local(self, content: str = "data") -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(content)
            return f.name

    def test_returns_minus1_when_ftp_path_empty(self) -> None:
        assert upload_file("", "user", "pass", self._local()) == -1

    def test_returns_minus1_when_local_path_empty(self) -> None:
        assert upload_file("ftp://host", "user", "pass", "") == -1

    def test_returns_minus1_on_connect_error(self) -> None:
        local = self._local()
        with patch("ftplib.FTP") as mock_ftp_cls:
            mock_ftp_cls.return_value.__enter__ = MagicMock(
                side_effect=OSError("connection refused")
            )
            mock_ftp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = upload_file("ftp://bad.host", "user", "pass", local)
        assert result == -1

    def test_returns_minus1_on_login_error(self) -> None:
        local = self._local()
        mock_ftp = MagicMock()
        mock_ftp.connect.return_value = None
        mock_ftp.login.side_effect = ftplib.error_perm("530 Login incorrect")  # noqa: S321
        with patch("ftplib.FTP") as mock_ftp_cls:
            mock_ftp_cls.return_value.__enter__ = MagicMock(return_value=mock_ftp)
            mock_ftp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = upload_file("ftp://host", "bad_user", "bad_pass", local)
        assert result == -1

    def test_returns_minus1_on_missing_local_file(self) -> None:
        result = upload_file(
            "ftp://host", "user", "pass", "/nonexistent/path/file.html"
        )
        assert result == -1

    def test_returns_0_on_success(self) -> None:
        local = self._local()
        mock_ftp = MagicMock()
        mock_ftp.connect.return_value = None
        mock_ftp.login.return_value = None
        mock_ftp.storbinary.return_value = None
        with patch("ftplib.FTP") as mock_ftp_cls:
            mock_ftp_cls.return_value.__enter__ = MagicMock(return_value=mock_ftp)
            mock_ftp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = upload_file("ftp://host/remote/", "user", "pass", local)
        assert result == 0
        mock_ftp.storbinary.assert_called_once()

    def test_invalid_url_returns_minus1(self) -> None:
        local = self._local()
        result = upload_file("not_a_url\x00\x01", "user", "pass", local)
        assert result == -1

    def test_errors_out_populated_with_host_and_exception(self) -> None:
        local = self._local()
        errors: list[str] = []
        with patch("ftplib.FTP") as mock_ftp_cls:
            mock_ftp_cls.return_value.__enter__ = MagicMock(
                side_effect=OSError("connection refused")
            )
            mock_ftp_cls.return_value.__exit__ = MagicMock(return_value=False)
            upload_file("ftp://bad.host/uploads/", "user", "pass", local, errors)
        assert len(errors) == 1
        assert "bad.host" in errors[0]
        assert "connection refused" in errors[0]

    def test_errors_out_contains_filename(self) -> None:
        local = self._local()
        errors: list[str] = []
        with patch("ftplib.FTP") as mock_ftp_cls:
            mock_ftp_cls.return_value.__enter__ = MagicMock(
                side_effect=OSError("550 No such file")
            )
            mock_ftp_cls.return_value.__exit__ = MagicMock(return_value=False)
            upload_file("ftp://host/remote/", "user", "pass", local, errors)
        assert len(errors) == 1
        assert ".html" in errors[0]

    def test_errors_out_empty_on_success(self) -> None:
        local = self._local()
        errors: list[str] = []
        mock_ftp = MagicMock()
        mock_ftp.connect.return_value = None
        mock_ftp.login.return_value = None
        mock_ftp.storbinary.return_value = None
        with patch("ftplib.FTP") as mock_ftp_cls:
            mock_ftp_cls.return_value.__enter__ = MagicMock(return_value=mock_ftp)
            mock_ftp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = upload_file("ftp://host/remote/", "user", "pass", local, errors)
        assert result == 0
        assert errors == []

    def test_errors_out_empty_path_message(self) -> None:
        errors: list[str] = []
        upload_file("", "user", "pass", self._local(), errors)
        assert len(errors) == 1
        assert "empty" in errors[0].lower()
