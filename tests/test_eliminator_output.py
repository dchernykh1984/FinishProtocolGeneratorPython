"""What a ladder looks like once written: the HTML bracket and the site document."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.config import RACE_TYPE_ELIMINATOR_FINALS, RaceConfig
from app.eliminator import EliminatorGroup, build_brackets
from app.eliminator_output import (
    build_finals_document,
    heat_title,
    write_finals_protocol,
)
from app.models import StartProtocolElement

_FULL_RESULTS = [
    ["101", "105", "104", "108"],
    ["102", "106", "103", "107"],
    ["101", "102", "105", "106"],
    ["104", "103", "108", "107"],
]


def _starts(count: int = 8) -> list[StartProtocolElement]:
    return [
        StartProtocolElement.from_line(
            f"{100 + p}#Rider {p}#Men#1#1#199{p % 10}#Team {p}#City {p}##{p}#",
            place_field=True,
        )
        for p in range(1, count + 1)
    ]


def _cfg(**kwargs: Any) -> RaceConfig:
    cfg = RaceConfig()
    cfg.race_type = RACE_TYPE_ELIMINATOR_FINALS
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    return cfg


def _brackets(results: list[list[str]] | None = None, rounds: int = 2):
    log: list[str] = []
    return build_brackets(
        [EliminatorGroup("Men", 4, rounds)],
        _starts(4 * 2 ** (rounds - 1)),
        results if results is not None else _FULL_RESULTS,
        log,
    )


def _html(brackets, cfg: RaceConfig) -> str:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "ladder.html")
        write_finals_protocol(path, brackets, _starts(), cfg)
        return Path(path).read_text(encoding="utf-8")


class TestHeatTitles:
    def test_the_rounds_are_named_as_fractions(self) -> None:
        bracket = _brackets(rounds=3)[0]
        assert heat_title(bracket, bracket.stages[0][0]) == "1/4 final 1"
        assert heat_title(bracket, bracket.stages[1][1]) == "1/2 final 2"
        assert heat_title(bracket, bracket.stages[2][0]) == "Final"
        assert heat_title(bracket, bracket.small_final) == "Small final"


class TestHtml:
    def test_every_heat_and_rider_is_on_the_page(self) -> None:
        page = _html(_brackets(), _cfg())
        for title in ("1/2 final 1", "1/2 final 2", "Final", "Small final"):
            assert title in page
        for bib in range(101, 109):
            assert str(bib) in page

    def test_the_group_is_named_once_per_ladder(self) -> None:
        cfg = _cfg(group_label="Group")
        assert _html(_brackets(), cfg).count("Group Men") == 1

    def test_a_rider_who_did_not_finish_reads_dnf(self) -> None:
        page = _html(_brackets([["101", "105"]]), _cfg())
        assert "DNF" in page

    def test_a_ladder_nobody_has_ridden_has_no_places(self) -> None:
        page = _html(_brackets([]), _cfg())
        assert "DNF" not in page

    def test_the_bracket_spans_rows_so_rounds_line_up(self) -> None:
        page = _html(_brackets(rounds=3), _cfg())
        # The last column carries the final above the small final, so it spans the
        # same two rows a semifinal does -- the shape the C++ version drew.
        assert "ROWSPAN=1" in page and "ROWSPAN=2" in page
        assert "ROWSPAN=4" not in page

    def test_rider_text_is_escaped(self) -> None:
        nasty = [
            StartProtocolElement.from_line(
                "101#<script>x</script>#Men#1#1#1990#T#C##1#", place_field=True
            )
        ]
        log: list[str] = []
        brackets = build_brackets([EliminatorGroup("Men", 4, 2)], nasty, [], log)
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "ladder.html")
            write_finals_protocol(path, brackets, nasty, cfg := _cfg())
            page = Path(path).read_text(encoding="utf-8")
        assert cfg.show_name
        assert "<script>x</script>" not in page
        assert "&lt;script&gt;" in page

    def test_hidden_columns_stay_out(self) -> None:
        page = _html(_brackets(), _cfg(show_team=False, show_city=False))
        assert "Team 1" not in page and "City 1" not in page


class TestDocument:
    def _document(self, **kwargs: Any) -> dict[str, Any]:
        return build_finals_document(_brackets(), _starts(), _cfg(**kwargs))

    def test_it_is_a_schema_one_document(self) -> None:
        document = self._document()
        assert document["schema"] == 1
        assert document["generator"]["name"] == "FinishProtocolGenerator"

    def test_one_plain_table_per_ridden_heat(self) -> None:
        sections = self._document()["sections"]
        assert {section["type"] for section in sections} == {"table"}
        assert len(sections) == 4

    def test_the_final_comes_first_for_a_phone(self) -> None:
        titles = [section["title"] for section in self._document()["sections"]]
        assert titles[0].endswith("Final")
        assert titles[-1].endswith("1/2 final 2")

    def test_a_heat_nobody_rode_is_left_out(self) -> None:
        log: list[str] = []
        brackets = build_brackets([EliminatorGroup("Men", 4, 2)], _starts(), [], log)
        document = build_finals_document(brackets, _starts(), _cfg())
        # Only the two seeded first-round heats carry riders.
        assert len(document["sections"]) == 2

    def test_rows_carry_the_places_and_the_riders(self) -> None:
        final = self._document()["sections"][0]
        assert [row["cells"][0] for row in final["rows"]] == ["1", "2", "3", "4"]
        assert final["rows"][0]["cells"][1] == "101"

    def test_a_rider_who_did_not_finish_is_marked(self) -> None:
        document = build_finals_document(_brackets([["101", "105"]]), _starts(), _cfg())
        statuses = [
            row.get("status")
            for section in document["sections"]
            for row in section["rows"]
        ]
        assert "dnf" in statuses

    def test_the_group_is_registered_for_the_site_filter(self) -> None:
        document = self._document()
        assert [group["label"] for group in document["groups"]] == ["Men"]
        assert {section["group"] for section in document["sections"]} == {
            document["groups"][0]["id"]
        }

    def test_it_serialises(self) -> None:
        assert json.loads(json.dumps(self._document()))["schema"] == 1

    def test_no_markup_reaches_the_site(self) -> None:
        document = build_finals_document(
            _brackets(), _starts(), _cfg(group_label="<b>G</b>")
        )
        assert not re.search(r"<[^>]+>", json.dumps(document, ensure_ascii=False))


@pytest.mark.parametrize("rounds", [1, 2, 3])
def test_a_ladder_of_any_depth_writes_without_error(rounds: int) -> None:
    brackets = _brackets([], rounds=rounds)
    page = _html(brackets, _cfg())
    assert "Final" in page
    assert build_finals_document(brackets, _starts(), _cfg())["schema"] == 1
