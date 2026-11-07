"""What a ladder looks like once written: the HTML bracket and the site document."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import jsonschema
import pytest
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
        page = _html(_brackets([(_SEMI1, ["101", "105"]), (_SEMI2, [])]), _cfg())
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


class TestAHeatStillBeingRidden:
    """What the protocol says while riders are on the course."""

    def _page(self, cfg: RaceConfig | None = None) -> str:
        # Two of four across, nothing started after: the other two are still riding.
        return _html(_brackets([(_SEMI1, ["101", "105"])]), cfg or _cfg())

    def test_those_who_crossed_have_their_place_and_time(self) -> None:
        page = self._page()
        assert "00:00:01.0" in page and "00:00:02.0" in page

    def test_those_still_riding_are_not_marked_dnf(self) -> None:
        # The rider is on the course, not beaten. DNF here is a wrong result, not a
        # cosmetic one: it is what a protocol refreshed mid-heat would publish.
        assert "DNF" not in self._page()

    def test_they_are_marked_dnf_once_the_heat_is_over(self) -> None:
        page = _html(_brackets([(_SEMI1, ["101", "105"]), (_SEMI2, [])]), _cfg())
        assert "DNF" in page

    def test_the_site_is_not_told_they_did_not_finish(self) -> None:
        document = build_finals_document(
            _brackets([(_SEMI1, ["101", "105"])]), _starts(), _cfg()
        )
        statuses = [
            row.get("status")
            for section in document["sections"]
            for row in section["rows"]
        ]
        assert "dnf" not in statuses

    def test_whoever_crossed_in_a_going_on_place_is_already_above(self) -> None:
        document = build_finals_document(
            _brackets([(_SEMI1, ["101", "105"])]), _starts(), _cfg()
        )
        titles = [section["title"] for section in document["sections"]]
        assert any(title.endswith("- Final") for title in titles)


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


class TestDocument:
    def _document(self, **kwargs: Any) -> dict[str, Any]:
        return build_finals_document(_brackets(), _starts(), _cfg(**kwargs))

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
    )
    def test_the_site_accepts_it(self, shown: dict[str, bool]) -> None:
        # A document the site refuses is replaced by the HTML on the page, so the
        # finals would never be drawn as the site's own tables.
        document = self._document(**shown)
        jsonschema.validate(document, SCHEMA)
        check_document_rules(document)

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
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), [], [], log
        )
        document = build_finals_document(brackets, _starts(), _cfg())
        # Only the two seeded first-round heats carry riders.
        assert len(document["sections"]) == 2

    def test_rows_carry_the_places_and_the_riders(self) -> None:
        final = self._document()["sections"][0]
        assert [row["cells"]["place"] for row in final["rows"]] == ["1", "2", "3", "4"]
        assert final["rows"][0]["cells"]["bib"] == "101"

    def test_the_result_column_is_declared_and_filled(self) -> None:
        final = self._document()["sections"][0]
        assert [column["id"] for column in final["columns"]][-1] == "result"
        assert final["rows"][0]["cells"]["result"] == "00:00:01.0"

    def test_the_gap_sits_under_the_time_as_the_column_promises(self) -> None:
        # The column declares a sub-label for the difference, so the difference has
        # to arrive as a sub-line; inlined into the text it would leave that heading
        # with nothing under it.
        final = self._document(show_time_difference=True)["sections"][0]
        result_column = final["columns"][-1]
        assert result_column["sub_label"]
        winner, second = (row["cells"]["result"] for row in final["rows"][:2])
        assert winner == "00:00:01.0"
        assert second == {"text": "00:00:02.0", "sub": ["(+00:00:01.0)"]}

    def test_without_the_difference_the_column_promises_nothing(self) -> None:
        final = self._document(show_time_difference=False)["sections"][0]
        assert "sub_label" not in final["columns"][-1]
        assert final["rows"][1]["cells"]["result"] == "00:00:02.0"

    def test_the_result_column_is_absent_when_hidden(self) -> None:
        final = self._document(show_finish_time=False)["sections"][0]
        assert "result" not in [column["id"] for column in final["columns"]]

    def test_a_rider_who_did_not_finish_is_marked(self) -> None:
        document = build_finals_document(
            _brackets([(_SEMI1, ["101", "105"]), (_SEMI2, [])]), _starts(), _cfg()
        )
        statuses = [
            row.get("status")
            for section in document["sections"]
            for row in section["rows"]
        ]
        assert "dnf" in statuses

    def test_a_disqualified_rider_is_marked(self) -> None:
        starts, marks = _timed([(_SEMI1, ["105", "104", "108"])])
        marks.append(FinishCompetitorElement("101", 1030.0, "DSQ"))
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(), starts, marks, log
        )
        document = build_finals_document(brackets, _starts(), _cfg())
        statuses = [
            row.get("status")
            for section in document["sections"]
            for row in section["rows"]
        ]
        assert "dsq" in statuses

    def test_an_unraced_heat_says_so_in_its_title(self) -> None:
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("Men", 4, 2)], _starts(2), [], [], log
        )
        document = build_finals_document(
            brackets, _starts(2), _cfg(not_ridden_label="not ridden")
        )
        titles = [section["title"] for section in document["sections"]]
        assert any("(not ridden)" in title for title in titles)

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
        titles = [section["title"] for section in document["sections"]]
        assert not any("Small final" in title for title in titles)
        assert len(titles) == 3

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
def test_a_ladder_of_any_depth_writes_without_error(rounds: int) -> None:
    brackets = _brackets([], rounds=rounds)
    page = _html(brackets, _cfg())
    assert "Final" in page
    document = build_finals_document(brackets, _starts(4 * 2 ** (rounds - 1)), _cfg())
    jsonschema.validate(document, SCHEMA)
    check_document_rules(document)
