"""The refusals of the federation-protocol skill's collect script: race data it
cannot read the way the generator wrote it stops the run rather than print a wrong
official paper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).resolve().parents[1]
    / ".claude"
    / "skills"
    / "federation-protocol"
    / "scripts"
    / "collect.py"
)
_spec = importlib.util.spec_from_file_location("federation_collect", _PATH)
assert _spec is not None and _spec.loader is not None
collect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect)

_HEAT = '<FONT SIZE="3" COLOR="#000000"><B><CENTER>Final</CENTER></B></FONT>'
_ROW = "<table><tr><td>1</td><td>7</td></tr></table>"


def _config(folder: Path, text: str) -> Path:
    (folder / "fpg_info.txt").write_text(text, encoding="utf-8")
    return folder


def test_a_key_value_config_is_refused(tmp_path: Path) -> None:
    folder = _config(tmp_path, "# FPG Race Info\nRaceName=x\n")
    with pytest.raises(SystemExit, match="key=value"):
        collect.config(folder)


def test_a_config_that_does_not_line_up_is_refused(tmp_path: Path) -> None:
    # The race type is the 13th line; anything unknown there means a shifted file.
    lines = [*"abcdefghi", "0", "0", "1", "nonsense"]
    folder = _config(tmp_path, "\n".join(lines) + "\n")
    with pytest.raises(SystemExit, match="does not line up"):
        collect.config(folder)


def test_a_setting_with_no_whole_number_reads_as_the_default() -> None:
    assert collect.number({"time_limit": "abc"}, "time_limit") == 0
    assert collect.number({}, "n_signs_after_point") == 1
    assert collect.number({"n_signs_after_point": "3"}, "n_signs_after_point") == 3


def test_a_qualification_without_a_header_row_is_refused(tmp_path: Path) -> None:
    (tmp_path / "gr.html").write_text(f"<U>Group A</U>{_ROW}", encoding="utf-8")
    with pytest.raises(SystemExit, match="no rider rows"):
        collect.qualification(tmp_path, {})


def test_a_heat_without_a_header_row_is_refused(tmp_path: Path) -> None:
    (tmp_path / "gr.html").write_text(f"<U>Group A</U>{_HEAT}{_ROW}", encoding="utf-8")
    with pytest.raises(SystemExit, match="A, Final: no header row"):
        collect.ladders(tmp_path, {})


def test_runs_that_disagree_on_the_groups_are_refused() -> None:
    # A group renamed between the runs would otherwise lose its finals unseen.
    heats = {"A 2012": {"Final": [{"bib": "1", "place": "1", "status": "ok"}]}}
    with pytest.raises(SystemExit, match="disagree on the groups"):
        collect.agree({"A 2012-2013": ["1"]}, heats)


def test_a_finalist_missing_from_the_qualification_is_refused() -> None:
    heats = {"A": {"Final": [{"bib": "9", "place": "1", "status": "ok"}]}}
    with pytest.raises(SystemExit, match="A #9"):
        collect.agree({"A": ["1"]}, heats)
