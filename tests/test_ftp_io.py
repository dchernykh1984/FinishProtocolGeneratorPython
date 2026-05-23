"""Tests for ftp_io merge utilities (pure logic, no network calls)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.ftp_io import merge_files, similar_strings


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
