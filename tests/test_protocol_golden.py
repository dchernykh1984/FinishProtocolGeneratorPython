"""Every scenario's HTML stays byte for byte what the writers produced before.

The golden files were written by the code as it was before the protocol calculations
were pulled out of the writers (issue #310); set REGENERATE_GOLDEN=1 only when a change
to the HTML is meant.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from protocol_scenarios import GOLDEN, SCENARIOS

from app.html_writer import write_absolute_protocol, write_group_protocol


def _write(name: str, tmp: Path) -> dict[str, str]:
    race = SCENARIOS[name]()
    out = {}
    group_path = tmp / "group.html"
    write_group_protocol(
        str(group_path), race.protocol, race.groups, race.cfg, race.n_points
    )
    out["group.html"] = group_path.read_text(encoding="utf-8")
    text_path = Path(str(group_path) + ".txt")
    if text_path.exists():
        out["group.txt"] = text_path.read_text(encoding="utf-8")
    absolute_path = tmp / "absolute.html"
    write_absolute_protocol(
        str(absolute_path), race.protocol, race.groups, race.cfg, race.n_points
    )
    out["absolute.html"] = absolute_path.read_text(encoding="utf-8")
    return out


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_protocol_html_matches_golden(name, tmp_path):
    produced = _write(name, tmp_path)
    if os.environ.get("REGENERATE_GOLDEN"):
        GOLDEN.mkdir(parents=True, exist_ok=True)
        for kind, text in produced.items():
            (GOLDEN / f"{name}.{kind}").write_text(text, encoding="utf-8")
    for kind, text in produced.items():
        assert text == (GOLDEN / f"{name}.{kind}").read_text(encoding="utf-8"), (
            f"{name}.{kind}"
        )


@pytest.mark.parametrize(
    "name", ["mass_basic", "example_race", "tries_asc", "custom_basic"]
)
def test_writing_twice_gives_the_same_html(name, tmp_path):
    race = SCENARIOS[name]()
    outputs = []
    for i in range(2):
        for writer, kind in (
            (write_group_protocol, "g"),
            (write_absolute_protocol, "a"),
        ):
            path = tmp_path / f"{kind}{i}.html"
            writer(str(path), race.protocol, race.groups, race.cfg, race.n_points)
            outputs.append(path.read_text(encoding="utf-8"))
    assert outputs[:2] == outputs[2:]
