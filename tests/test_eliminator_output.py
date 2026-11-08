"""What a ladder looks like once written: the HTML bracket and the site document."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from protocol_scenarios import SCENARIOS
from test_protocol_document import SCHEMA, check_document_rules

from app.config import RACE_TYPE_ELIMINATOR_FINALS, RaceConfig
from app.eliminator import EliminatorGroup, build_brackets
from app.eliminator_output import (
    build_finals_document,
    heat_title,
    write_finals_protocol,
    write_heat_list,
    write_ladder_file,
)
from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
)
from app.protocol_document import build_group_document

_SEMI1 = "Men - 1/2 final 1"
_SEMI2 = "Men - 1/2 final 2"
_FINAL = "Men - Final"
_SMALL = "Men - Small final"

_FULL: list[tuple[str, list[str]]] = [
    (_SEMI1, ["101", "105", "104", "108"]),
    (_SEMI2, ["102", "106", "103", "107"]),
    (_FINAL, ["101", "102", "105", "106"]),
    (_SMALL, ["104", "103", "108", "107"]),
]


def _starts(count: int = 8) -> list[StartProtocolElement]:
    return [
        StartProtocolElement.from_line(
            f"{100 + p}#Rider {p}#Men#1#1#199{p % 10}#Team {p}#City {p}##{p}#",
            place_field=True,
        )
        for p in range(1, count + 1)
    ]


def _timed(
    heats: list[tuple[str, list[str]]],
) -> tuple[list[GroupStartElement], list[FinishCompetitorElement]]:
    """The chronometer's two files for heats ridden a minute apart, in order."""
    starts: list[GroupStartElement] = []
    marks: list[FinishCompetitorElement] = []
    clock = 1000.0
    for name, order in heats:
        starts.append(GroupStartElement(group_id=name, seconds=clock))
        for index, bib in enumerate(order, start=1):
            marks.append(FinishCompetitorElement(bib, clock + index, "finish"))
        clock += 60.0
    return starts, marks


def _cfg(**kwargs: Any) -> RaceConfig:
    cfg = RaceConfig()
    cfg.race_type = RACE_TYPE_ELIMINATOR_FINALS
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    return cfg


def _brackets(heats: list[tuple[str, list[str]]] | None = None, rounds: int = 2):
    if heats is None:
        heats = _FULL if rounds == 2 else []
    starts, marks = _timed(heats)
    log: list[str] = []
    return build_brackets(
        [EliminatorGroup("Men", 4, rounds)],
        _starts(4 * 2 ** (rounds - 1)),
        starts,
        marks,
        log,
    )


def _html(brackets, cfg: RaceConfig) -> str:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "ladder.html")
        write_finals_protocol(path, brackets, _starts(), cfg)
        return Path(path).read_text(encoding="utf-8")


def _table(page: str, title: str) -> list[list[str]]:
    """One heat's table off the page, as rows of plain cells."""
    head = page.find(f"<CENTER>{title}</CENTER>")
    block = page[head : page.find("</table>", head)]
    return [
        [
            re.sub(r"<[^>]+>", "", cell).strip()
            for cell in re.findall(r"<td.*?</td>", row, re.S)
        ]
        for row in re.findall(r"<tr.*?</tr>", block, re.S)
    ]


def _row(table: list[list[str]], bib: str) -> list[str]:
    return next(row for row in table if bib in row)


def _heats(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Every heat's table, ladder by ladder, stage by stage in the order ridden."""
    return [
        heat
        for ladder in document["sections"]
        for stage in ladder["sections"]
        for heat in stage["sections"]
    ]


def _heat(document: dict[str, Any], title: str) -> dict[str, Any]:
    return next(heat for heat in _heats(document) if heat["title"] == title)


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

    def test_the_qualification_place_is_a_column_of_every_heat(self) -> None:
        # The place the ladder seated him by, so a heat can be read against the
        # qualification without the other page beside it.
        page = _html(_brackets(), _cfg(qualification_place_label="Qual."))
        assert page.count("Qual.") == 4
        final = _table(page, "Final")
        assert final[0][6] == "Qual."
        # 101 and 102 won their semi-finals from qualification places 1 and 2; 105
        # and 106 came second from places 5 and 6.
        assert [_row(final, bib)[6] for bib in ("101", "102", "105", "106")] == [
            "1",
            "2",
            "5",
            "6",
        ]

    def test_the_qualification_place_can_be_turned_off(self) -> None:
        page = _html(
            _brackets(),
            _cfg(show_qualification_place=False, qualification_place_label="Qual."),
        )
        assert "Qual." not in page

    def test_a_rider_with_no_qualification_place_shows_none(self) -> None:
        # A bib the start protocol does not carry has no place to show, and a zero
        # in the column would read as a place of its own.
        brackets = _brackets()
        brackets[0].stages[0][0].numbers[0] = "999"
        page = _html(brackets, _cfg(qualification_place_label="Qual."))
        assert _row(_table(page, "1/2 final 1"), "999")[6] == ""

    def test_the_group_is_named_once_per_ladder(self) -> None:
        cfg = _cfg(group_label="Group")
        assert _html(_brackets(), cfg).count("Group Men") == 1

    def test_a_rider_who_did_not_finish_reads_dnf(self) -> None:
        page = _html(_brackets([(_SEMI1, ["101", "105"]), (_SEMI2, [])]), _cfg())
        assert "DNF" in page

    def test_the_last_heat_of_the_day_still_reads_dnf(self) -> None:
        # Nothing starts after the final, so its window never closes. Waiting for
        # that left the rider who pulled out of it with an empty cell for good.
        heats = _FULL[:3]
        heats[2] = (_FINAL, ["101", "102", "105"])
        page = _html(_brackets(heats), _cfg())
        assert _row(_table(page, "Final"), "106")[0] == "DNF"

    def test_a_ladder_nobody_has_ridden_has_no_places(self) -> None:
        # Drawn and not yet raced: no start of any heat is recorded, so every seeded
        # rider is DNS and nobody is DNF or placed. This is the whole ladder saying
        # what a timed protocol says before its groups go off.
        page = _html(_brackets([]), _cfg())
        assert "DNF" not in page
        table = _table(page, "1/2 final 1")
        assert [row[0] for row in table[1:]] == ["DNS"] * 4
        assert page.count("DNS") == 8

    def test_a_heat_nobody_started_reads_dns(self) -> None:
        # The small final of a group that was sent home after the big one: its riders
        # never went to the gate, which is DNS, the same as a rider whose group never
        # went off in a timed race. An empty cell said nothing at all.
        heats = [h for h in _FULL if h[0] != _SMALL]
        table = _table(_html(_brackets(heats), _cfg()), "Small final")
        assert [_row(table, bib)[0] for bib in ("103", "104", "107", "108")] == [
            "DNS"
        ] * 4

    def test_a_heat_still_to_be_ridden_reads_dns_too(self) -> None:
        # Mid-meeting: the semi-finals are in, the final has not gone off. Its riders
        # have not started it, so the protocol says so rather than leaving a gap.
        table = _table(_html(_brackets(_FULL[:2]), _cfg()), "Final")
        assert [_row(table, bib)[0] for bib in ("101", "102", "105", "106")] == [
            "DNS"
        ] * 4

    def test_a_heat_holding_another_heats_start_reads_dns_too(self) -> None:
        # Saved without pressing Start, so the time in its line belongs to the heat
        # before it. The group file holds no start of this heat, which is what the
        # cell goes by, and the error tells the referee to repair the line.
        starts, marks = _timed(_FULL[:2])
        starts.append(GroupStartElement(group_id=_FINAL, seconds=starts[-1].seconds))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        table = _table(_html(brackets, _cfg()), "Final")
        assert [_row(table, bib)[0] for bib in ("101", "102", "105", "106")] == [
            "DNS"
        ] * 4
        assert any("starting at the same time" in line for line in log)

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
        brackets = build_brackets([EliminatorGroup("Men", 4, 2)], nasty, [], [], log)
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

    def test_stretching_widens_the_ladder_and_its_heats(self) -> None:
        page = _html(_brackets(), _cfg(stretch=True))
        # The ladder table and every heat table inside it.
        assert page.count("width=100%") == 1 + 4


class TestAHeatThatHasGoneOff:
    """What the protocol says about a rider whose heat has started.

    The same as every other race type says about a rider whose group has gone off
    and whose finish has not been seen: DNF until his time comes in. The ladder used
    to leave the cell blank until a later heat closed this one's window, which read
    as nothing at all on a protocol that was otherwise finished.
    """

    def _page(self, cfg: RaceConfig | None = None) -> str:
        # Two of four across, nothing started after.
        return _html(_brackets([(_SEMI1, ["101", "105"])]), cfg or _cfg())

    def test_those_who_crossed_have_their_place_and_time(self) -> None:
        page = self._page()
        assert "00:00:01.0" in page and "00:00:02.0" in page

    def test_those_without_a_time_yet_read_dnf(self) -> None:
        table = _table(self._page(), "1/2 final 1")
        assert [_row(table, bib)[0] for bib in ("101", "105")] == ["1", "2"]
        assert [_row(table, bib)[0] for bib in ("104", "108")] == ["DNF", "DNF"]

    def test_they_are_still_dnf_once_the_heat_is_over(self) -> None:
        page = _html(_brackets([(_SEMI1, ["101", "105"]), (_SEMI2, [])]), _cfg())
        assert "DNF" in page

    def test_the_site_is_told_they_have_not_finished(self) -> None:
        document = build_finals_document(
            _brackets([(_SEMI1, ["101", "105"])]), _starts(), _cfg()
        )
        statuses = [
            row.get("status") for heat in _heats(document) for row in heat["rows"]
        ]
        assert "dnf" in statuses

    def test_whoever_crossed_in_a_going_on_place_is_already_above(self) -> None:
        document = build_finals_document(
            _brackets([(_SEMI1, ["101", "105"])]), _starts(), _cfg()
        )
        assert _heat(document, "Final")["rows"]


class TestTimesOnThePage:
    def test_the_result_column_carries_the_time_ridden(self) -> None:
        page = _html(_brackets(), _cfg(finish_time_label="Result"))
        assert "Result" in page
        # Four riders a second apart, measured from their own heat's start, in the
        # same clock format the rest of the protocols use.
        assert "00:00:01.0" in page and "00:00:04.0" in page

    def test_the_gap_is_measured_inside_the_heat(self) -> None:
        page = _html(_brackets(), _cfg(show_time_difference=True))
        assert "(+00:00:01.0)" in page
        # The heat winner has nothing to be behind.
        assert "(+00:00:00.0)" not in page

    def test_the_gap_can_be_turned_off(self) -> None:
        page = _html(_brackets(), _cfg(show_time_difference=False))
        assert "(+" not in page

    def test_the_result_column_can_be_turned_off(self) -> None:
        page = _html(_brackets(), _cfg(show_finish_time=False, finish_time_label="Res"))
        assert "Res" not in page

    def test_an_unraced_heat_says_so_and_shows_no_time(self) -> None:
        # Two riders in a group of eight seats: nobody can be eliminated.
        starts, marks = _timed([])
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(2), starts, marks, log
        )
        page = _html(brackets, _cfg(not_ridden_label="not ridden"))
        assert "1/2 final 1 (not ridden)" in page
        assert "Final (not ridden)" in page

    def test_a_ridden_heat_is_not_labelled(self) -> None:
        page = _html(_brackets(), _cfg(not_ridden_label="not ridden"))
        assert "not ridden" not in page

    def test_a_disqualified_rider_reads_dsq(self) -> None:
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(FinishCompetitorElement("101", 1030.0, "DSQ: cut in"))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        page = _html(brackets, _cfg())
        assert "DSQ" in page

    def test_the_reason_fills_the_result_cell_of_a_disqualified_rider(self) -> None:
        # The timed protocols print the reason where the time would be, and the
        # referee cannot read a protocol that says only DSQ: the reason was in the
        # results file and nowhere on the page.
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(
            FinishCompetitorElement("101", 1030.0, "DSQ: cut across the first turn")
        )
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        row = _row(_table(_html(brackets, _cfg()), "1/2 final 1"), "101")
        assert row[0] == "DSQ"
        assert row[-1] == "cut across the first turn"

    def test_a_reason_is_escaped_and_several_stack(self) -> None:
        # Free referee text typed into the chronometer, so it can hold anything.
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(FinishCompetitorElement("101", 1020.0, "DSQ: cut <the> turn"))
        marks.append(FinishCompetitorElement("101", 1030.0, "DSQ: and the next"))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        page = _html(brackets, _cfg())
        assert "cut &lt;the&gt; turn<BR>and the next" in page
        assert "<the>" not in page

    def test_a_bare_disqualification_leaves_the_cell_empty(self) -> None:
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(FinishCompetitorElement("101", 1030.0, "DSQ"))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        row = _row(_table(_html(brackets, _cfg()), "1/2 final 1"), "101")
        assert row[0] == "DSQ"
        assert row[-1] == ""


class TestDocument:
    def _document(self, **kwargs: Any) -> dict[str, Any]:
        return build_finals_document(_brackets(), _starts(), _cfg(**kwargs))

    def test_the_qualification_place_is_a_cell_of_its_own(self) -> None:
        final = _heat(self._document(qualification_place_label="Qual."), "Final")
        assert ("qual", "Qual.") in [
            (column["id"], column["label"]) for column in final["columns"]
        ]
        assert [row["cells"]["qual"] for row in final["rows"]] == ["1", "2", "5", "6"]

    def test_it_is_a_schema_one_document(self) -> None:
        document = self._document()
        assert document["schema"] == 1
        assert document["generator"]["name"] == "FinishProtocolGenerator"

    @pytest.mark.parametrize(
        "shown",
        [
            {},
            {"show_place": False},
            {"show_finish_time": False},
            {"show_time_difference": False},
            {"show_additional_info": True},
        ],
        ids=["default", "no-place", "no-time", "no-gap", "extra"],
    )
    def test_the_site_accepts_it(self, shown: dict[str, bool]) -> None:
        # A document the site refuses is replaced by the HTML on the page, so the
        # finals would never be drawn as the site's own tables.
        document = self._document(**shown)
        jsonschema.validate(document, SCHEMA)
        check_document_rules(document)

    def test_each_group_is_a_ladder_of_its_stages_in_the_order_ridden(self) -> None:
        (ladder,) = self._document()["sections"]
        assert ladder["type"] == "ladder"
        assert ladder["title"] == "Group Men"
        assert [stage["title"] for stage in ladder["sections"]] == [
            "1/2 final",
            "Final",
        ]
        assert [
            [heat["title"] for heat in stage["sections"]]
            for stage in ladder["sections"]
        ] == [["1/2 final 1", "1/2 final 2"], ["Final", "Small final"]]
        assert {heat["type"] for heat in _heats(self._document())} == {"table"}

    def test_a_stage_is_named_as_its_heats_are(self) -> None:
        (ladder,) = build_finals_document(_brackets([], rounds=4), _starts(32), _cfg())[
            "sections"
        ]
        assert [stage["title"] for stage in ladder["sections"]] == [
            "1/8 final",
            "1/4 final",
            "1/2 final",
            "Final",
        ]
        for stage in ladder["sections"]:
            for heat in stage["sections"]:
                if heat["title"] != "Small final":
                    assert heat["title"].startswith(stage["title"]), heat["title"]

    def test_a_heat_nobody_is_seated_in_keeps_its_place_empty(self) -> None:
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), [], [], log
        )
        document = build_finals_document(brackets, _starts(), _cfg())
        # The two seeded first-round heats carry riders; the finals wait, empty.
        assert [len(heat["rows"]) for heat in _heats(document)] == [4, 4, 0, 0]

    def test_rows_carry_the_places_and_the_riders(self) -> None:
        final = _heat(self._document(), "Final")
        assert [row["cells"]["place"] for row in final["rows"]] == ["1", "2", "3", "4"]
        assert final["rows"][0]["cells"]["bib"] == "101"

    def test_the_result_column_is_declared_and_filled(self) -> None:
        final = _heat(self._document(), "Final")
        assert [column["id"] for column in final["columns"]][-1] == "result"
        assert final["rows"][0]["cells"]["result"] == "00:00:01.0"

    def test_the_gap_sits_under_the_time_as_the_column_promises(self) -> None:
        # The column declares a sub-label for the difference, so the difference has
        # to arrive as a sub-line; inlined into the text it would leave that heading
        # with nothing under it.
        final = _heat(self._document(show_time_difference=True), "Final")
        result_column = final["columns"][-1]
        assert result_column["sub_label"]
        winner, second = (row["cells"]["result"] for row in final["rows"][:2])
        assert winner == "00:00:01.0"
        assert second == {"text": "00:00:02.0", "sub": ["(+00:00:01.0)"]}

    def test_without_the_difference_the_column_promises_nothing(self) -> None:
        final = _heat(self._document(show_time_difference=False), "Final")
        assert "sub_label" not in final["columns"][-1]
        assert final["rows"][1]["cells"]["result"] == "00:00:02.0"

    def test_the_result_column_is_absent_when_hidden(self) -> None:
        final = _heat(self._document(show_finish_time=False), "Final")
        assert "result" not in [column["id"] for column in final["columns"]]

    def test_the_columns_are_declared_as_a_timed_protocols(self) -> None:
        # The site keeps the number and the name in view by their roles and hides the
        # minor columns by priority, so a column the finals share with a timed
        # protocol is declared alike; the order stays the finals HTML's.
        race = SCENARIOS["mass_all_columns"]()
        timed = build_group_document(race.protocol, race.groups, race.cfg)
        declared = {
            column["id"]: (column.get("role"), column.get("priority"))
            for column in timed["sections"][0]["columns"]
        }
        final = _heat(self._document(show_additional_info=True), "Final")
        ids = [column["id"] for column in final["columns"]]
        assert ids == [
            "place",
            "bib",
            "name",
            "year",
            "team",
            "city",
            "extra",
            "qual",
            "result",
        ]
        for column in final["columns"]:
            if column["id"] in ("qual", "result"):
                # The two the finals do not share: a timed protocol has no
                # qualification place at all, and a heat's time matters less than a
                # timed race's.
                continue
            role_and_priority = (column.get("role"), column.get("priority"))
            assert role_and_priority == declared[column["id"]], column["id"]

    def test_on_a_narrow_screen_only_place_and_name_always_stay(self) -> None:
        # A heat is decided by the order of crossing: its time is left out after the
        # year, the city and the team, and before the number. The site keeps the
        # columns without a priority of their own -- place and name -- in every width.
        final = _heat(self._document(), "Final")
        priority = {column["id"]: column.get("priority") for column in final["columns"]}
        assert priority["place"] is None
        assert priority["name"] is None
        assert priority["team"] > priority["result"] > priority["bib"] > 1

    def test_a_rider_who_did_not_finish_is_marked(self) -> None:
        document = build_finals_document(
            _brackets([(_SEMI1, ["101", "105"]), (_SEMI2, [])]), _starts(), _cfg()
        )
        statuses = [
            row.get("status") for heat in _heats(document) for row in heat["rows"]
        ]
        assert "dnf" in statuses

    def test_a_rider_in_a_heat_nobody_started_is_marked_dns(self) -> None:
        heats = [h for h in _FULL if h[0] != _SMALL]
        document = build_finals_document(_brackets(heats), _starts(), _cfg())
        small = _heat(document, "Small final")
        assert {row.get("status") for row in small["rows"]} == {"dns"}
        assert {row["cells"]["place"] for row in small["rows"]} == {"DNS"}
        check_document_rules(document)
        jsonschema.validate(document, SCHEMA)

    def test_a_disqualified_rider_is_marked(self) -> None:
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(FinishCompetitorElement("101", 1030.0, "DSQ"))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        document = build_finals_document(brackets, _starts(), _cfg())
        statuses = [
            row.get("status") for heat in _heats(document) for row in heat["rows"]
        ]
        assert "dsq" in statuses

    def test_the_reason_is_a_note_under_the_row(self) -> None:
        # The site has no room for it in the cell and shows a note instead, which is
        # what the timed protocol's document does with the same text.
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(FinishCompetitorElement("101", 1030.0, "DSQ: cut in"))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        document = build_finals_document(brackets, _starts(), _cfg())
        notes = {
            row["cells"].get("bib"): row.get("note")
            for heat in _heats(document)
            for row in heat["rows"]
        }
        assert notes["101"] == "cut in"
        assert notes["105"] is None
        check_document_rules(document)
        jsonschema.validate(document, SCHEMA)

    def test_an_unraced_heat_says_so_in_its_title(self) -> None:
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(2), [], [], log
        )
        document = build_finals_document(
            brackets, _starts(2), _cfg(not_ridden_label="not ridden")
        )
        titles = [heat["title"] for heat in _heats(document)]
        assert "1/2 final 1 (not ridden)" in titles

    def test_the_group_is_registered_for_the_site_filter(self) -> None:
        document = self._document()
        assert [group["label"] for group in document["groups"]] == ["Men"]
        assert {ladder["group"] for ladder in document["sections"]} == {
            document["groups"][0]["id"]
        }

    def test_the_lap_switches_of_a_timed_protocol_give_the_finals_none(self) -> None:
        # The switches are for laps a heat does not have; looking for them must not
        # stumble on a ladder, which has no columns of its own.
        document = self._document(
            use_buttons=True, use_all_buttons=True, show_lap_times=True
        )
        assert document["toggles"] == []

    def test_it_serialises(self) -> None:
        assert json.loads(json.dumps(self._document()))["schema"] == 1

    def test_no_markup_reaches_the_site(self) -> None:
        document = build_finals_document(
            _brackets(), _starts(), _cfg(group_label="<b>G</b>")
        )
        assert not re.search(r"<[^>]+>", json.dumps(document, ensure_ascii=False))


class TestWithoutASmallFinal:
    def _brackets(self):
        starts, marks = _timed(
            [
                (_SEMI1, ["101", "105", "104", "108"]),
                (_SEMI2, ["102", "106", "103", "107"]),
                (_FINAL, ["101", "102", "105", "106"]),
            ]
        )
        log: list[str] = []
        return build_brackets(
            [EliminatorGroup("Men", 4, 2, small_final=False)],
            _starts(),
            starts,
            marks,
            log,
        )

    def test_the_page_does_not_draw_it(self) -> None:
        page = _html(self._brackets(), _cfg())
        assert "Small final" not in page
        assert "1/2 final 1" in page and "Final" in page

    def test_the_page_still_holds_every_other_heat(self) -> None:
        page = _html(self._brackets(), _cfg())
        # Four semi-finalists plus the four who rode the final.
        for bib in range(101, 109):
            assert str(bib) in page

    def test_the_site_is_not_sent_it(self) -> None:
        document = build_finals_document(self._brackets(), _starts(), _cfg())
        titles = [heat["title"] for heat in _heats(document)]
        assert titles == ["1/2 final 1", "1/2 final 2", "Final"]

    def test_the_heat_list_leaves_it_out(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "heats.txt")
            write_heat_list(path, self._brackets())
            assert Path(path).read_text(encoding="utf-8").splitlines() == [
                _SEMI1,
                _SEMI2,
                _FINAL,
            ]


class TestGeneratedFiles:
    def test_the_heat_list_is_one_name_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "heats.txt")
            write_heat_list(path, _brackets())
            # In the order a meeting rides them: the small final before the big.
            assert Path(path).read_text(encoding="utf-8").splitlines() == [
                _SEMI1,
                _SEMI2,
                _SMALL,
                _FINAL,
            ]

    def test_the_ladder_file_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "ladders.txt")
            write_ladder_file(path, [("Men", "4", "2"), ("Women", "", "")])
            assert Path(path).read_text(encoding="utf-8").splitlines() == [
                "Men#4#2#",
                "Women###",
            ]


@pytest.mark.parametrize("rounds", [1, 2, 3, 4])
def test_a_ladder_of_any_depth_is_written_and_the_site_accepts_it(rounds: int) -> None:
    brackets = _brackets([], rounds=rounds)
    page = _html(brackets, _cfg())
    assert "Final" in page
    document = build_finals_document(brackets, _starts(4 * 2 ** (rounds - 1)), _cfg())
    jsonschema.validate(document, SCHEMA)
    check_document_rules(document)
