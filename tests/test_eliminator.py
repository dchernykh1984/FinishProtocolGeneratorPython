"""The knockout ladder: seeding, byes, heat results and the places they produce.

The numbers here are the ones the C++ generator produced, because a ladder that
seeds differently sends the wrong riders against each other.
"""

from __future__ import annotations

import pytest

from app.eliminator import (
    HEAT_SIZES,
    EliminatorBracket,
    EliminatorGroup,
    build_brackets,
    group_problems,
    parse_eliminator_groups,
    read_heat_results,
)
from app.models import StartProtocolElement


def _starts(places: list[int], group: str = "G") -> list[StartProtocolElement]:
    """One rider per qualification place, bib = 100 + place."""
    return [
        StartProtocolElement.from_line(
            f"{100 + p}#Rider {p}#{group}#1#1#1990#Team#City##{p}#", place_field=True
        )
        for p in places
    ]


def _bracket(heat_size: int = 4, rounds: int = 2) -> EliminatorBracket:
    return EliminatorBracket(EliminatorGroup("G", heat_size, rounds))


class TestSeeding:
    def test_eight_riders_pair_first_against_last(self) -> None:
        # The C++ bracket put places 1,4,5,8 in one heat and 2,3,6,7 in the other.
        assert [h.seeds for h in _bracket(4, 2).stages[0]] == [
            (1, 4, 5, 8),
            (2, 3, 6, 7),
        ]

    def test_four_riders_in_heats_of_two(self) -> None:
        assert [h.seeds for h in _bracket(2, 2).stages[0]] == [(1, 4), (2, 3)]

    def test_sixteen_riders_over_three_rounds(self) -> None:
        assert [h.seeds for h in _bracket(4, 3).stages[0]] == [
            (1, 8, 9, 16),
            (4, 5, 12, 13),
            (2, 7, 10, 15),
            (3, 6, 11, 14),
        ]

    @pytest.mark.parametrize("heat_size", HEAT_SIZES)
    @pytest.mark.parametrize("rounds", [1, 2, 3])
    def test_every_place_gets_exactly_one_seat(
        self, heat_size: int, rounds: int
    ) -> None:
        bracket = _bracket(heat_size, rounds)
        seats = [seed for heat in bracket.stages[0] for seed in heat.seeds]
        assert sorted(seats) == list(range(1, bracket.group.capacity + 1))

    def test_the_final_holds_the_first_places(self) -> None:
        assert _bracket(4, 3).stages[-1][0].seeds == (1, 2, 3, 4)

    def test_the_small_final_follows_the_big_one(self) -> None:
        assert _bracket(4, 2).small_final.seeds == (5, 6, 7, 8)


class TestParsing:
    def test_a_ladder_line(self) -> None:
        assert parse_eliminator_groups(["Men#4#2#"]) == [EliminatorGroup("Men", 4, 2)]

    def test_an_unsupported_heat_size_is_skipped_and_reported(self) -> None:
        assert parse_eliminator_groups(["Men#8#2#"]) == []
        assert "only 2 and 4 are supported" in group_problems(["Men#8#2#"])[0]

    def test_too_few_rounds_is_skipped_and_reported(self) -> None:
        assert parse_eliminator_groups(["Men#4#0#"]) == []
        assert "at least one round" in group_problems(["Men#4#0#"])[0]

    def test_a_blank_line_is_neither_a_ladder_nor_a_problem(self) -> None:
        assert parse_eliminator_groups(["", "  "]) == []
        assert group_problems(["", "  "]) == []

    def test_heat_results_are_bibs_in_finishing_order(self) -> None:
        assert read_heat_results(["101#105#", "", "102#106#103#107#"]) == [
            ["101", "105"],
            ["102", "106", "103", "107"],
        ]


class TestSeatingQualifiers:
    def test_a_rider_takes_the_seat_of_their_place(self) -> None:
        bracket = _bracket(4, 2)
        assert bracket.place_competitor("101", 1)
        assert bracket.stages[0][0].numbers[0] == "101"

    def test_a_place_beyond_the_ladder_has_no_seat(self) -> None:
        bracket = _bracket(4, 2)
        assert not bracket.place_competitor("109", 9)
        assert not bracket.place_competitor("100", 0)

    def test_a_rider_outside_the_ladder_is_logged(self) -> None:
        log: list[str] = []
        build_brackets([EliminatorGroup("G", 4, 2)], _starts([9]), [], log)
        assert "outside the ladder" in log[0]

    def test_a_rider_of_another_group_is_left_alone(self) -> None:
        log: list[str] = []
        brackets = build_brackets(
            [EliminatorGroup("G", 4, 2)], _starts([1], group="Other"), [], log
        )
        assert brackets[0].stages[0][0].taken == 0
        assert log == []


class TestHeatResults:
    def test_a_full_order_places_everyone(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [["101", "105", "104", "108"]],
            log,
        )[0]
        heat = bracket.stages[0][0]
        assert heat.numbers == ["101", "105", "104", "108"]
        assert bracket.finishing_places(heat) == [1, 2, 3, 4]

    def test_the_top_half_goes_on_and_the_rest_drop_to_the_small_final(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [["101", "105", "104", "108"], ["102", "106", "103", "107"]],
            log,
        )[0]
        assert bracket.stages[1][0].numbers == ["101", "105", "102", "106"]
        assert bracket.small_final.numbers == ["104", "108", "103", "107"]

    def test_listing_only_the_qualifiers_marks_the_others_dnf(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [["101", "105"]],
            log,
        )[0]
        heat = bracket.stages[0][0]
        assert bracket.finishing_places(heat) == [1, 2, None, None]
        # Nobody was classified behind them, so the small final stays empty.
        assert bracket.small_final.taken == 0

    def test_a_result_for_a_heat_that_cannot_run_yet_is_refused(self) -> None:
        # The final's riders are not known until both of its feeders have been ridden.
        bracket = _bracket(4, 2)
        for place, bib in enumerate(["101", "104", "105", "108"], start=1):
            bracket.place_competitor(bib, (1, 4, 5, 8)[place - 1])
        assert bracket.apply_result(["101", "104"]) is bracket.stages[0][0]

    def test_an_unknown_result_is_logged(self) -> None:
        log: list[str] = []
        build_brackets(
            [EliminatorGroup("G", 4, 2)], _starts(list(range(1, 9))), [["999"]], log
        )
        assert "no heat is waiting" in log[0]

    def test_results_are_not_applied_twice(self) -> None:
        log: list[str] = []
        order = ["101", "105", "104", "108"]
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [order, order],
            log,
        )[0]
        assert bracket.stages[0][0].numbers == order
        assert "no heat is waiting" in log[0]


class TestByes:
    def test_a_half_empty_heat_is_not_ridden(self) -> None:
        # Two riders in a heat of four cannot eliminate anyone: both go through.
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)], _starts([1, 4]), [], log
        )[0]
        assert bracket.stages[0][0].has_results
        assert bracket.stages[1][0].numbers[:2] == ["101", "104"]

    def test_a_full_heat_still_has_to_be_ridden(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)], _starts([1, 4, 5]), [], log
        )[0]
        assert not bracket.stages[0][0].has_results

    def test_a_bye_does_not_reach_past_an_unridden_heat(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)], _starts(list(range(1, 9))), [], log
        )[0]
        assert not bracket.stages[1][0].has_results


class TestPlaces:
    def test_the_small_final_carries_on_from_the_big_one(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [
                ["101", "105", "104", "108"],
                ["102", "106", "103", "107"],
                ["101", "102", "105", "106"],
                ["104", "103", "108", "107"],
            ],
            log,
        )[0]
        assert bracket.finishing_places(bracket.stages[1][0]) == [1, 2, 3, 4]
        assert bracket.finishing_places(bracket.small_final) == [5, 6, 7, 8]

    def test_an_empty_seat_has_no_place(self) -> None:
        bracket = _bracket(4, 2)
        assert bracket.finishing_places(bracket.stages[0][0]) == [None] * 4


class TestLadderShape:
    def test_the_last_stage_holds_both_finals(self) -> None:
        bracket = _bracket(4, 2)
        heats = bracket.heats_in_stage(1)
        assert [h.is_small_final for h in heats] == [False, True]

    def test_heat_lookup_matches_the_stage_lists(self) -> None:
        bracket = _bracket(4, 3)
        assert bracket.heat(0, 2) is bracket.stages[0][2]
        assert bracket.heat(2, 1) is bracket.small_final


class TestSmallFinalRiddenFirst:
    """At a real event the small final is ridden before the big one."""

    def test_its_places_do_not_collide_with_the_medals(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [
                ["101", "105", "104", "108"],
                ["102", "106", "103", "107"],
                ["104", "103", "108", "107"],
            ],
            log,
        )[0]
        assert not bracket.stages[1][0].has_results
        assert bracket.finishing_places(bracket.small_final) == [5, 6, 7, 8]

    def test_the_big_final_still_numbers_from_one(self) -> None:
        log: list[str] = []
        bracket = build_brackets(
            [EliminatorGroup("G", 4, 2)],
            _starts(list(range(1, 9))),
            [
                ["101", "105", "104", "108"],
                ["102", "106", "103", "107"],
                ["104", "103", "108", "107"],
                ["101", "102", "105", "106"],
            ],
            log,
        )[0]
        assert bracket.finishing_places(bracket.stages[1][0]) == [1, 2, 3, 4]
        assert bracket.finishing_places(bracket.small_final) == [5, 6, 7, 8]


class TestDuplicatePlaces:
    def test_two_riders_on_one_place_are_reported(self) -> None:
        log: list[str] = []
        starts = [
            StartProtocolElement.from_line(line, place_field=True)
            for line in (
                "101#A#G#1#1#1990#T#C##1#",
                "102#B#G#1#1#1990#T#C##1#",
            )
        ]
        bracket = build_brackets([EliminatorGroup("G", 4, 2)], starts, [], log)[0]
        assert any("both hold qualification place 1" in message for message in log)
        # One of them still rides; the other is named in the log rather than lost.
        assert bracket.stages[0][0].numbers[0] == "102"
        assert any("101 loses its seat" in message for message in log)
