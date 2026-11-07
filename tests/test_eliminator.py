"""The knockout ladder: seeding, heats scored from times, and the places they give.

The seeding numbers here are the ones the C++ generator produced, because a ladder
that seeds differently sends the wrong riders against each other. Everything about
timing is new: a heat is an ordinary group to the chronometer, so it has a start time
and its riders have finish marks, and the ladder has to pick each heat's own marks out
of a file in which one bib legitimately appears several times.
"""

from __future__ import annotations

import pytest

from app.eliminator import (
    HEAT_SIZES,
    EliminatorBracket,
    EliminatorGroup,
    build_brackets,
    group_problems,
    heat_name,
    heat_names,
    heat_title,
    ladder_lines,
    missing_ladders,
    parse_eliminator_groups,
    start_list_groups,
)
from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
)

SEMI1 = "G - 1/2 final 1"
SEMI2 = "G - 1/2 final 2"
FINAL = "G - Final"
SMALL = "G - Small final"


def _starts(places: list[int], group: str = "G") -> list[StartProtocolElement]:
    """One rider per qualification place, bib = 100 + place."""
    return [
        StartProtocolElement.from_line(
            f"{100 + p}#Rider {p}#{group}#1#1#1990#Team#City##{p}#", place_field=True
        )
        for p in places
    ]


class _Event:
    """The two chronometer files, built heat by heat in the order they were ridden.

    Heats are 60 s apart, which is what keeps every heat's marks inside its own
    window; a test that wants them to collide says so by passing the time itself.
    """

    def __init__(self) -> None:
        self.starts: list[GroupStartElement] = []
        self.marks: list[FinishCompetitorElement] = []
        self._clock = 1000.0

    def ride(
        self,
        name: str,
        order: list[str],
        dsq: tuple[str, ...] = (),
        offsets: list[float] | None = None,
    ) -> _Event:
        self.start(name)
        for index, bib in enumerate(order):
            gap = offsets[index] if offsets else float(index + 1)
            self.marks.append(
                FinishCompetitorElement(bib, self._clock - 60.0 + gap, "finish")
            )
        for bib in dsq:
            self.marks.append(
                FinishCompetitorElement(bib, self._clock - 60.0 + 30.0, "DSQ: cut in")
            )
        return self

    def start(self, name: str, seconds: float | None = None) -> _Event:
        """Record a start without any marks behind it."""
        when = self._clock if seconds is None else seconds
        self.starts.append(GroupStartElement(group_id=name, seconds=when))
        self._clock = when + 60.0
        return self

    def build(
        self, groups: list[EliminatorGroup], start_list: list[StartProtocolElement]
    ) -> tuple[list[EliminatorBracket], list[str]]:
        log: list[str] = []
        brackets = build_brackets(groups, start_list, self.starts, self.marks, log)
        return brackets, log


def _bracket(heat_size: int = 4, rounds: int = 2) -> EliminatorBracket:
    return EliminatorBracket(EliminatorGroup("G", heat_size, rounds))


def _ladder(heat_size: int = 4, rounds: int = 2) -> list[EliminatorGroup]:
    return [EliminatorGroup("G", heat_size, rounds)]


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

    def test_a_group_that_was_copied_from_the_chronometer_is_not_a_ladder(self) -> None:
        # groups.txt holds "group # time of day #", and that is exactly the file a
        # referee copies by mistake. It must not look like a four-rider ladder.
        line = "Men#0 00:00:00.000#"
        assert parse_eliminator_groups([line]) == []
        assert "rides 0 per heat" in group_problems([line])[0]

    def test_a_round_trip_through_the_file_keeps_the_ladder(self) -> None:
        assert ladder_lines([("Men", "4", "2")]) == ["Men#4#2#"]
        assert parse_eliminator_groups(ladder_lines([("Men", "4", "2")])) == [
            EliminatorGroup("Men", 4, 2)
        ]

    def test_a_group_waiting_for_its_shape_keeps_its_line(self) -> None:
        assert ladder_lines([("Men", "", "")]) == ["Men###"]
        assert parse_eliminator_groups(["Men###"]) == []

    def test_a_row_without_a_group_is_dropped(self) -> None:
        assert ladder_lines([("  ", "4", "2")]) == []


class TestLadderCoverage:
    def test_a_group_with_qualifiers_and_no_ladder_is_named(self) -> None:
        assert missing_ladders([], _starts([1, 2])) == ["G"]

    def test_a_group_with_a_ladder_is_not_named(self) -> None:
        assert missing_ladders(_ladder(), _starts([1, 2])) == []

    def test_each_group_is_named_once_in_start_protocol_order(self) -> None:
        start_list = _starts([1], group="B") + _starts([1, 2], group="A")
        assert start_list_groups(start_list) == ["B", "A"]
        assert missing_ladders([], start_list) == ["B", "A"]


class TestHeatNames:
    def test_a_name_carries_the_group_and_the_round(self) -> None:
        bracket = _bracket(4, 2)
        assert heat_name(bracket, bracket.stages[0][1]) == SEMI2
        assert heat_name(bracket, bracket.stages[1][0]) == FINAL
        assert heat_name(bracket, bracket.small_final) == SMALL

    def test_the_list_covers_every_heat_of_the_ladder(self) -> None:
        assert heat_names([_bracket(4, 2)]) == [SEMI1, SEMI2, FINAL, SMALL]

    def test_a_one_round_ladder_is_just_the_two_finals(self) -> None:
        assert heat_names([_bracket(4, 1)]) == [FINAL, SMALL]

    def test_the_title_leaves_the_group_out(self) -> None:
        bracket = _bracket(4, 3)
        assert heat_title(bracket, bracket.stages[0][0]) == "1/4 final 1"


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
        _brackets, log = _Event().build(_ladder(), _starts([9]))
        assert "outside the ladder" in log[0]

    def test_a_rider_of_another_group_is_left_alone(self) -> None:
        brackets, log = _Event().build(_ladder(), _starts([1], group="Other"))
        assert brackets[0].stages[0][0].taken == 0
        assert log == []


class TestHeatsScoredFromTimes:
    def test_the_order_of_the_marks_is_the_order_of_the_heat(self) -> None:
        event = _Event().ride(SEMI1, ["101", "105", "104", "108"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        heat = bracket.stages[0][0]
        assert heat.numbers == ["101", "105", "104", "108"]
        assert bracket.finishing_places(heat) == [1, 2, 3, 4]
        assert heat.ridden
        assert heat.times == [1.0, 2.0, 3.0, 4.0]

    def test_the_top_half_goes_on_and_the_rest_drop_to_the_small_final(self) -> None:
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert bracket.stages[1][0].numbers == ["101", "105", "102", "106"]
        assert bracket.small_final.numbers == ["104", "108", "103", "107"]

    def test_a_rider_with_no_mark_of_his_own_is_dnf(self) -> None:
        event = _Event().ride(SEMI1, ["101", "105"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        heat = bracket.stages[0][0]
        assert bracket.finishing_places(heat) == [1, 2, None, None]
        # Nobody was classified behind them, so the small final stays empty.
        assert bracket.small_final.taken == 0

    def test_a_started_heat_with_no_marks_at_all_is_an_error(self) -> None:
        _brackets, log = _Event().start(SEMI1).build(_ladder(), _starts([1, 4, 5, 8]))
        assert any("was started but has no finish marks" in line for line in log)

    def test_a_heat_nobody_started_stays_empty(self) -> None:
        bracket = _Event().build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert not bracket.stages[0][0].has_results
        assert bracket.finishing_places(bracket.stages[0][0]) == [None] * 4

    def test_a_start_that_belongs_to_no_heat_is_logged(self) -> None:
        event = _Event().start("G - 1/2 final 7")
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert any("no heat of any ladder is called" in line for line in log)

    def test_the_later_start_of_a_restarted_heat_wins(self) -> None:
        # The chronometer appends a line per start and never rewrites, so a heat
        # started again after a false start has two lines.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.start(SEMI1, seconds=2000.0)
        event.marks.append(FinishCompetitorElement("101", 2001.0, "finish"))
        bracket = event.build(_ladder(), _starts([1, 4, 5, 8]))[0][0]
        assert bracket.stages[0][0].times[0] == pytest.approx(1.0)

    def test_two_heats_sharing_a_start_time_are_reported(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.start(SEMI2, seconds=1000.0)
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert any("starting at the same time" in line for line in log)


class TestMarkWindows:
    def test_a_riders_second_heat_takes_his_second_mark(self) -> None:
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.ride(SMALL, ["104", "103", "108", "107"])
        event.ride(FINAL, ["101", "102", "105", "106"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        final = bracket.stages[1][0]
        assert final.numbers == ["101", "102", "105", "106"]
        assert final.times == [1.0, 2.0, 3.0, 4.0]

    def test_a_mark_past_the_next_start_is_not_this_heats(self) -> None:
        # 101's mark in his own heat went missing and turned up after the next heat
        # had started. Taking it would hand him a win he did not ride for.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        for bib, gap in (("105", 2.0), ("104", 3.0), ("108", 4.0)):
            event.marks.append(FinishCompetitorElement(bib, 1000.0 + gap, "finish"))
        event.start(SEMI2, seconds=2000.0)
        event.marks.append(FinishCompetitorElement("101", 2001.0, "finish"))
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        semi = bracket.stages[0][0]
        assert semi.numbers == ["105", "104", "108", "101"]
        assert semi.times[semi.numbers.index("101")] == -1.0
        assert bracket.finishing_places(semi) == [1, 2, 3, None]


class TestDisqualification:
    def test_a_disqualified_rider_does_not_go_on(self) -> None:
        event = _Event()
        event.ride(SEMI1, ["105", "104", "108"], dsq=("101",))
        event.ride(SEMI2, ["102", "106", "103", "107"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        semi = bracket.stages[0][0]
        assert semi.numbers == ["105", "104", "108", "101"]
        assert semi.disqualified == [False, False, False, True]
        assert "101" not in bracket.stages[1][0].numbers

    def test_a_disqualification_beats_a_finish_mark_whenever_it_was_stamped(
        self,
    ) -> None:
        # The jury stamps it after the rider has already crossed, so the earlier
        # finish mark must not win the seat back.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1001.0, "finish"))
        event.marks.append(FinishCompetitorElement("101", 1030.0, "DSQ"))
        event.marks.append(FinishCompetitorElement("104", 1002.0, "finish"))
        bracket = event.build(_ladder(), _starts([1, 4]))[0][0]
        semi = bracket.stages[0][0]
        assert semi.numbers[0] == "104"
        assert semi.disqualified[semi.numbers.index("101")]
        assert bracket.stages[1][0].numbers[:1] == ["104"]


class TestUnraced:
    def test_a_half_empty_heat_goes_through_unraced(self) -> None:
        # Two riders in a heat of four cannot eliminate anyone: both go through.
        bracket = _Event().build(_ladder(), _starts([1, 4]))[0][0]
        semi = bracket.stages[0][0]
        assert semi.has_results
        assert not semi.ridden
        assert bracket.stages[1][0].numbers[:2] == ["101", "104"]

    def test_the_better_qualifier_comes_first_in_an_unraced_heat(self) -> None:
        # Seats hold places 1,4,5,8, so seat order is not merit order.
        bracket = _Event().build(_ladder(), _starts([5, 1]))[0][0]
        assert bracket.stages[0][0].numbers[:2] == ["101", "105"]

    def test_an_unraced_heat_has_no_times(self) -> None:
        bracket = _Event().build(_ladder(), _starts([1, 4]))[0][0]
        assert bracket.stages[0][0].times == [-1.0] * 4

    def test_the_better_qualifier_comes_first_above_stage_zero_too(self) -> None:
        # Seats above the first round hold whoever the heats below sent up, in the
        # order those were scored, so seat order is not merit order there either.
        # Semi 1 classifies only place 8; semi 2 only place 7.
        event = _Event()
        event.ride(SEMI1, ["108"])
        event.ride(SEMI2, ["107"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        final = bracket.stages[1][0]
        assert not final.ridden
        assert final.numbers[:2] == ["107", "108"]
        assert bracket.finishing_places(final)[:2] == [1, 2]

    def test_a_full_heat_waits_to_be_ridden(self) -> None:
        bracket = _Event().build(_ladder(), _starts([1, 4, 5]))[0][0]
        assert not bracket.stages[0][0].has_results

    def test_a_final_that_was_ridden_is_scored_from_its_times(self) -> None:
        # Two riders in the whole group: the organizers chose to ride the final.
        event = _Event().ride(FINAL, ["102", "101"])
        bracket = event.build(_ladder(), _starts([1, 2]))[0][0]
        final = bracket.stages[1][0]
        assert final.ridden
        assert final.numbers[:2] == ["102", "101"]

    def test_a_final_nobody_started_falls_back_to_qualification_order(self) -> None:
        bracket = _Event().build(_ladder(), _starts([1, 2]))[0][0]
        final = bracket.stages[1][0]
        assert final.has_results
        assert not final.ridden
        assert final.numbers[:2] == ["101", "102"]
        assert bracket.finishing_places(final)[:2] == [1, 2]

    def test_a_bye_does_not_reach_past_a_heat_still_to_be_ridden(self) -> None:
        bracket = _Event().build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert not bracket.stages[1][0].has_results


class TestTies:
    def _tie(self, name: str, order: list[str], offsets: list[float]) -> list[str]:
        event = _Event().ride(name, order, offsets=offsets)
        return event.build(_ladder(), _starts(list(range(1, 9))))[1]

    def test_a_tie_among_those_going_on_is_a_warning(self) -> None:
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 1.0, 3.0, 4.0])
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("WARNING:")

    def test_a_tie_across_the_line_that_sends_riders_on_is_an_error(self) -> None:
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 2.0, 2.0, 4.0])
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("ERROR:")
        assert "decides who goes on" in tie[0]

    def test_a_tie_among_those_already_out_is_a_warning(self) -> None:
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 2.0, 3.0, 3.0])
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("WARNING:")

    def test_a_tie_for_a_medal_in_the_big_final_is_an_error(self) -> None:
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.ride(FINAL, ["101", "102", "105", "106"], offsets=[1.0, 1.0, 3.0, 4.0])
        log = event.build(_ladder(), _starts(list(range(1, 9))))[1]
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("ERROR:")

    def test_a_tie_in_the_small_final_is_a_warning(self) -> None:
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.ride(SMALL, ["104", "103", "108", "107"], offsets=[1.0, 1.0, 3.0, 4.0])
        log = event.build(_ladder(), _starts(list(range(1, 9))))[1]
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("WARNING:")

    def test_distinct_times_raise_nothing(self) -> None:
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 2.0, 3.0, 4.0])
        assert not [line for line in log if "share a time" in line]

    def test_three_riders_on_one_time_are_reported_once(self) -> None:
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 1.0, 1.0, 4.0])
        assert len([line for line in log if "share a time" in line]) == 1


class TestPlaces:
    def _full_event(self) -> _Event:
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        return event

    def test_the_small_final_carries_on_from_the_big_one(self) -> None:
        event = self._full_event()
        event.ride(FINAL, ["101", "102", "105", "106"])
        event.ride(SMALL, ["104", "103", "108", "107"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert bracket.finishing_places(bracket.stages[1][0]) == [1, 2, 3, 4]
        assert bracket.finishing_places(bracket.small_final) == [5, 6, 7, 8]

    def test_the_small_final_ridden_first_does_not_collide_with_the_medals(
        self,
    ) -> None:
        event = self._full_event()
        event.ride(SMALL, ["104", "103", "108", "107"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert not bracket.stages[1][0].has_results
        assert bracket.finishing_places(bracket.small_final) == [5, 6, 7, 8]

    def test_the_big_final_ridden_after_it_still_numbers_from_one(self) -> None:
        event = self._full_event()
        event.ride(SMALL, ["104", "103", "108", "107"])
        event.ride(FINAL, ["101", "102", "105", "106"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
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

    def test_only_the_last_stage_holds_the_big_final(self) -> None:
        bracket = _bracket(4, 2)
        assert bracket.is_big_final(bracket.stages[1][0])
        assert not bracket.is_big_final(bracket.small_final)
        assert not bracket.is_big_final(bracket.stages[0][0])

    def test_a_heat_sends_on_half_its_seats(self) -> None:
        assert _bracket(4, 2).stages[0][0].advancing == 2
        assert _bracket(2, 2).stages[0][0].advancing == 1


class TestDuplicatePlaces:
    def test_two_riders_on_one_place_are_reported(self) -> None:
        starts = [
            StartProtocolElement.from_line(line, place_field=True)
            for line in (
                "101#A#G#1#1#1990#T#C##1#",
                "102#B#G#1#1#1990#T#C##1#",
            )
        ]
        bracket, log = _Event().build(_ladder(), starts)
        assert any("both hold qualification place 1" in message for message in log)
        # One of them still rides; the other is named in the log rather than lost.
        assert bracket[0].stages[0][0].numbers[0] == "102"
        assert any("101 loses its seat" in message for message in log)


class TestBrokenInput:
    def test_a_group_with_two_ladders_keeps_the_first(self) -> None:
        brackets, log = _Event().build(
            [EliminatorGroup("G", 4, 2), EliminatorGroup("G", 2, 1)], _starts([1, 4])
        )
        assert len(brackets) == 1
        assert brackets[0].group.heat_size == 4
        assert any("more than one ladder" in message for message in log)
