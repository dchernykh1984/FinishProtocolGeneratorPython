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
    SEEDING_KEEP_ADJACENT,
    SEEDING_SCHEMES,
    SEEDING_SPLIT_ADJACENT,
    EliminatorBracket,
    EliminatorGroup,
    build_brackets,
    group_key,
    group_problems,
    heat_name,
    heat_names,
    heat_title,
    ladder_lines,
    missing_ladders,
    normalize_seeding,
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


def _no_small_final(heat_size: int = 4, rounds: int = 2) -> list[EliminatorGroup]:
    return [EliminatorGroup("G", heat_size, rounds, small_final=False)]


class TestScorableHeats:
    def test_a_one_round_ladder_has_no_small_final_to_walk(self) -> None:
        assert [heat.is_small_final for heat in _bracket(4, 1).all_heats()] == [False]

    def test_a_deeper_ladder_keeps_it(self) -> None:
        assert sum(h.is_small_final for h in _bracket(4, 2).all_heats()) == 1


class TestMeetingsWithoutASmallFinal:
    """Many meetings ride only the final. Then the last round simply drops riders."""

    def _bracket(self, rounds: int = 2) -> EliminatorBracket:
        return EliminatorBracket(EliminatorGroup("G", 4, rounds, small_final=False))

    def test_the_ladder_says_it_has_none(self) -> None:
        assert not self._bracket().has_small_final
        assert self._bracket(2).group.small_final is False

    def test_it_is_not_walked_scored_or_offered(self) -> None:
        bracket = self._bracket()
        assert not any(heat.is_small_final for heat in bracket.all_heats())
        assert not any(h.is_small_final for h in bracket.heats_in_stage(1))
        assert heat_names([bracket]) == [SEMI1, SEMI2, FINAL]

    def test_nobody_is_dropped_into_it(self) -> None:
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        bracket = event.build(_no_small_final(), _starts(list(range(1, 9))))[0][0]
        assert bracket.stages[1][0].numbers == ["101", "105", "102", "106"]
        assert bracket.small_final.taken == 0

    def test_a_start_recorded_for_it_belongs_to_no_heat(self) -> None:
        event = _Event().start(SMALL)
        _brackets, log = event.build(_no_small_final(), _starts(list(range(1, 9))))
        assert any("no heat of any ladder is called" in line for line in log)

    def test_a_stale_start_line_for_it_does_not_hold_up_the_group(self) -> None:
        event = _Event().start(SMALL, seconds=0.0).ride(SEMI1, ["101", "104"])
        brackets, log = event.build(_no_small_final(), _starts([1, 4]))
        assert brackets[0].stages[0][0].has_results
        assert any("no heat of any ladder is called" in line for line in log)

    def test_the_setting_reaches_the_ladders_through_the_file(self) -> None:
        assert parse_eliminator_groups(["G#4#2#"], small_final=False) == [
            EliminatorGroup("G", 4, 2, small_final=False)
        ]
        assert parse_eliminator_groups(["G#4#2#"]) == [EliminatorGroup("G", 4, 2)]

    def test_turning_it_on_is_the_default(self) -> None:
        assert EliminatorGroup("G", 4, 2).small_final is True


def _seeded(heat_size: int, rounds: int, seeding: str) -> list[tuple[int, ...]]:
    group = EliminatorGroup("G", heat_size, rounds, seeding)
    return [heat.seeds for heat in EliminatorBracket(group).stages[0]]


class TestSeeding:
    """The UCI numbers are printed in UCI Cycling Regulations, Part 4 Mountain Bike,
    Annex 5 (XCE schedule, 32 riders, 4 per heat). A ladder that seeds differently
    sends the wrong riders against each other, so these are copied from it."""

    def test_eight_riders_pair_first_against_last(self) -> None:
        assert _seeded(4, 2, SEEDING_SPLIT_ADJACENT) == [(1, 4, 5, 8), (2, 3, 6, 7)]

    def test_four_riders_in_heats_of_two(self) -> None:
        assert _seeded(2, 2, SEEDING_SPLIT_ADJACENT) == [(1, 4), (2, 3)]

    def test_sixteen_riders_over_three_rounds(self) -> None:
        # Annex 5, the note on fields under 24: "Heat 1 > Bib 1-8-9-16, Heat 2 >
        # 4-5-12-13, Heat 3 > 2-7-10-15, Heat 4 > 3-6-11-14."
        assert _seeded(4, 3, SEEDING_SPLIT_ADJACENT) == [
            (1, 8, 9, 16),
            (4, 5, 12, 13),
            (2, 7, 10, 15),
            (3, 6, 11, 14),
        ]

    def test_thirty_two_riders_match_the_published_schedule(self) -> None:
        # Annex 5's own 1/8 final table, heats 1 to 8.
        assert _seeded(4, 4, SEEDING_SPLIT_ADJACENT) == [
            (1, 16, 17, 32),
            (8, 9, 24, 25),
            (4, 13, 20, 29),
            (5, 12, 21, 28),
            (2, 15, 18, 31),
            (7, 10, 23, 26),
            (3, 14, 19, 30),
            (6, 11, 22, 27),
        ]

    @pytest.mark.parametrize("heat_size", HEAT_SIZES)
    @pytest.mark.parametrize("rounds", [1, 2, 3])
    @pytest.mark.parametrize("seeding", SEEDING_SCHEMES)
    def test_every_place_gets_exactly_one_seat(
        self, heat_size: int, rounds: int, seeding: str
    ) -> None:
        group = EliminatorGroup("G", heat_size, rounds, seeding)
        bracket = EliminatorBracket(group)
        seats = [seed for heat in bracket.stages[0] for seed in heat.seeds]
        assert sorted(seats) == list(range(1, bracket.group.capacity + 1))

    @pytest.mark.parametrize("heat_size", HEAT_SIZES)
    @pytest.mark.parametrize("rounds", [2, 3, 4])
    @pytest.mark.parametrize("seeding", SEEDING_SCHEMES)
    def test_the_heats_of_a_round_are_of_equal_strength(
        self, heat_size: int, rounds: int, seeding: str
    ) -> None:
        # Both schemes balance a round by the sum of the places in it; that is not
        # what tells them apart.
        sums = {sum(seeds) for seeds in _seeded(heat_size, rounds, seeding)}
        assert len(sums) == 1


class TestKeepingAdjacentSeedsTogether:
    """The other scheme some race regulations are written with."""

    def test_eight_riders_keep_their_neighbours(self) -> None:
        assert _seeded(4, 2, SEEDING_KEEP_ADJACENT) == [(1, 2, 7, 8), (3, 4, 5, 6)]

    def test_it_carries_on_into_deeper_ladders(self) -> None:
        assert _seeded(4, 3, SEEDING_KEEP_ADJACENT) == [
            (1, 2, 15, 16),
            (7, 8, 9, 10),
            (3, 4, 13, 14),
            (5, 6, 11, 12),
        ]
        assert _seeded(4, 4, SEEDING_KEEP_ADJACENT)[0] == (1, 2, 31, 32)

    @pytest.mark.parametrize("rounds", [2, 3, 4])
    def test_the_two_fastest_meet_a_round_earlier_each_time(self, rounds: int) -> None:
        # The cost of the scheme, and the reason the UCI one splits them: here the
        # first two qualifiers are always in the same first-round heat.
        assert {1, 2} <= set(_seeded(4, rounds, SEEDING_KEEP_ADJACENT)[0])
        assert not {1, 2} <= set(_seeded(4, rounds, SEEDING_SPLIT_ADJACENT)[0])

    @pytest.mark.parametrize("rounds", [1, 2, 3, 4])
    def test_heats_of_two_cannot_tell_the_schemes_apart(self, rounds: int) -> None:
        # Nothing adjacent to keep together inside a heat that holds two riders.
        assert _seeded(2, rounds, SEEDING_KEEP_ADJACENT) == _seeded(
            2, rounds, SEEDING_SPLIT_ADJACENT
        )


class TestChoosingTheScheme:
    def test_a_name_the_ladders_know_is_kept(self) -> None:
        for scheme in SEEDING_SCHEMES:
            assert normalize_seeding(scheme) == scheme

    def test_anything_else_falls_back_to_the_uci_one(self) -> None:
        # A config from another build, or edited by hand, must not quietly reseed a
        # championship.
        for junk in ("", "1-2-7-8", "Keep adjacent seeds together ", "UCI"):
            assert normalize_seeding(junk) == SEEDING_SPLIT_ADJACENT

    def test_the_file_carries_the_shape_and_the_settings_carry_the_scheme(self) -> None:
        assert parse_eliminator_groups(["G#4#2#"], seeding=SEEDING_KEEP_ADJACENT) == [
            EliminatorGroup("G", 4, 2, SEEDING_KEEP_ADJACENT)
        ]
        assert parse_eliminator_groups(["G#4#2#"]) == [
            EliminatorGroup("G", 4, 2, SEEDING_SPLIT_ADJACENT)
        ]

    def test_a_junk_scheme_does_not_reach_a_ladder(self) -> None:
        assert parse_eliminator_groups(["G#4#2#"], seeding="nonsense") == [
            EliminatorGroup("G", 4, 2, SEEDING_SPLIT_ADJACENT)
        ]

    def test_the_scheme_decides_who_meets_whom(self) -> None:
        event = _Event().ride(SEMI1, ["101", "104", "105", "108"])
        split = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert split.stages[0][0].numbers == ["101", "104", "105", "108"]
        keep = _Event().build(
            [EliminatorGroup("G", 4, 2, SEEDING_KEEP_ADJACENT)],
            _starts(list(range(1, 9))),
        )[0][0]
        assert keep.stages[0][0].seeds == (1, 2, 7, 8)
        assert keep.stages[0][0].numbers == ["101", "102", "107", "108"]

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

    def test_the_list_covers_every_heat_in_the_order_it_is_ridden(self) -> None:
        # The small final goes before the big one, as a meeting runs them.
        assert heat_names([_bracket(4, 2)]) == [SEMI1, SEMI2, SMALL, FINAL]

    def test_a_one_round_ladder_is_just_the_final(self) -> None:
        # No round below it to drop anybody out of, so its small final can never
        # hold a rider and must not be offered as a heat to start.
        assert heat_names([_bracket(4, 1)]) == [FINAL]
        assert not _bracket(4, 1).has_small_final
        assert _bracket(4, 2).has_small_final

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
        # The next heat has started, so this one is over and they did not finish.
        event = _Event().ride(SEMI1, ["101", "105"]).start(SEMI2)
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        heat = bracket.stages[0][0]
        assert bracket.finishing_places(heat) == [1, 2, None, None]
        # Nobody was classified behind them, so the small final stays empty.
        assert bracket.small_final.taken == 0

    def test_a_started_heat_with_no_marks_yet_places_nobody(self) -> None:
        brackets, log = _Event().start(SEMI1).build(_ladder(), _starts([1, 4, 5, 8]))
        semi = brackets[0].stages[0][0]
        assert not semi.complete
        assert brackets[0].finishing_places(semi) == [None] * 4
        assert any("is being ridden" in line for line in log)

    def test_the_round_above_an_unfinished_heat_stays_empty(self) -> None:
        event = _Event()
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.start(SEMI1)
        brackets, _log = event.build(_ladder(), _starts(list(range(1, 9))))
        final = brackets[0].stages[1][0]
        assert not final.has_results
        assert final.taken == 2

    def test_a_heat_nobody_started_stays_empty(self) -> None:
        bracket = _Event().build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert not bracket.stages[0][0].has_results
        assert bracket.finishing_places(bracket.stages[0][0]) == [None] * 4

    def test_a_start_that_belongs_to_no_heat_is_logged(self) -> None:
        event = _Event().start("G - 1/2 final 7")
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert any("no heat of any ladder is called" in line for line in log)

    def test_the_first_start_of_a_heat_saved_twice_wins(self) -> None:
        # The two cases that give a heat a second start line are the same bytes in
        # the file: a heat restarted after a false start, and a heat already ridden
        # saved again off the top of a restarted chronometer's list. The first start
        # is the one kept, because its damage is the smaller of the two -- the heat
        # keeps its finishing order and only its times are measured from too early,
        # where taking the later line wiped the heat and every heat above it. The
        # repeat is reported either way, for the referee to take the wrong line out.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.start(SEMI1, seconds=2000.0)
        event.marks.append(FinishCompetitorElement("101", 2001.0, "finish"))
        event.start(SEMI2, seconds=3000.0)
        brackets, log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert brackets[0].stages[0][0].times[0] == pytest.approx(1001.0)
        assert any(
            line.startswith("ERROR:") and "more than one start recorded" in line
            for line in log
        )

    def test_a_heat_saved_again_hours_later_keeps_its_result(self) -> None:
        # After a chronometer restart every heat is offered again and the ridden one
        # is selected, so Save group gives it a start from the middle of the
        # afternoon. Taking that one wiped the heat, the final above it and the small
        # final with it, and said nothing at ERROR level about any of it.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.starts.append(GroupStartElement(group_id=SEMI1, seconds=9000.0))
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi = brackets[0].stages[0][0]
        assert semi.has_results and semi.complete
        assert brackets[0].finishing_places(semi) == [1, 2, 3, 4]
        assert any("more than one start recorded" in line for line in log)

    def test_a_heat_saved_again_with_an_empty_start_field_is_not_reported(
        self,
    ) -> None:
        # The second line carries no start time, so there is no second start to
        # report and the first one stands.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1001.0, "finish"))
        event.starts.append(GroupStartElement(group_id=SEMI1, seconds=0.0))
        event.start(SEMI2, seconds=3000.0)
        brackets, log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert brackets[0].stages[0][0].times[0] == pytest.approx(1.0)
        assert not any("more than one start recorded" in line for line in log)
        assert not any("no start time" in line for line in log)

    def test_a_heat_saved_without_a_start_and_then_started_is_not_reported(
        self,
    ) -> None:
        # A line with no start time is not a start, so the heat's real start is the
        # later line and there is nothing to report.
        event = _Event()
        event.start(SEMI1, seconds=0.0)
        event.start(SEMI1, seconds=2000.0)
        event.marks.append(FinishCompetitorElement("101", 2001.0, "finish"))
        event.start(SEMI2, seconds=3000.0)
        brackets, log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert brackets[0].stages[0][0].times[0] == pytest.approx(1.0)
        assert not any("more than one start recorded" in line for line in log)
        assert not any("no start time" in line for line in log)

    def test_a_rider_is_placed_and_sent_on_the_moment_he_crosses(self) -> None:
        # One of four across, the other three still on the course. His place cannot
        # change -- nobody still riding can finish ahead of him -- so it is his now,
        # and so is his seat in the round above.
        event = _Event().ride(SEMI1, ["101"])
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi = brackets[0].stages[0][0]
        assert semi.has_results and not semi.complete
        assert brackets[0].finishing_places(semi) == [1, None, None, None]
        assert brackets[0].stages[1][0].numbers[:1] == ["101"]
        assert any("is being ridden" in line for line in log)

    def test_those_still_riding_are_not_beaten_yet(self) -> None:
        event = _Event().ride(SEMI1, ["101", "105"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        semi = bracket.stages[0][0]
        # Two crossed, two on the course: placed, blank, not DNF.
        assert not semi.complete
        assert bracket.finishing_places(semi) == [1, 2, None, None]
        assert semi.times[2] == -1.0

    def test_the_round_above_is_not_scored_while_the_one_below_is_ridden(self) -> None:
        # Its seats fill as riders cross, but nothing in it is decided until the
        # heats below are over -- otherwise a refresh hands out places mid-race.
        event = _Event().ride(SEMI1, ["101", "105"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        final = bracket.stages[1][0]
        assert final.numbers[:2] == ["101", "105"]
        assert not final.has_results
        assert bracket.finishing_places(final) == [None] * 4

    def test_the_next_heat_starting_settles_the_one_before_it(self) -> None:
        # Two of four crossed, then the next heat went: the other two did not finish.
        event = _Event().ride(SEMI1, ["101", "105"]).start(SEMI2)
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        semi = bracket.stages[0][0]
        assert semi.complete
        assert bracket.finishing_places(semi) == [1, 2, None, None]

    def test_the_last_rider_crossing_ends_the_heat(self) -> None:
        event = _Event().ride(SEMI1, ["101", "105", "104", "108"])
        bracket = event.build(_ladder(), _starts([1, 4, 5, 8]))[0][0]
        assert bracket.stages[0][0].complete

    def test_a_disqualification_also_accounts_for_a_rider(self) -> None:
        # The way a crashed rider is settled without waiting for the next heat.
        event = _Event().ride(SEMI1, ["101", "105", "104"], dsq=("108",))
        bracket = event.build(_ladder(), _starts([1, 4, 5, 8]))[0][0]
        assert bracket.stages[0][0].complete

    def test_the_next_heat_starting_closes_the_one_before_it(self) -> None:
        event = _Event().ride(SEMI1, ["101"]).start(SEMI2)
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        semi = bracket.stages[0][0]
        assert semi.has_results
        assert bracket.finishing_places(semi) == [1, None, None, None]

    def test_a_heat_whose_field_all_crossed_is_sealed_at_once(self) -> None:
        # Nothing after it, but there is nobody left to wait for.
        event = _Event().ride(SEMI1, ["101", "105", "104", "108"])
        bracket = event.build(_ladder(), _starts([1, 4, 5, 8]))[0][0]
        assert bracket.stages[0][0].has_results

    def test_a_closed_heat_with_no_marks_at_all_is_an_error(self) -> None:
        event = _Event().start(SEMI1, seconds=1000.0).start(SEMI2, seconds=2000.0)
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert brackets[0].stages[0][0].has_results
        assert any("has no finish marks at all" in line for line in log)

    def test_a_start_naming_no_heat_still_closes_the_window(self) -> None:
        # The meeting rides no small final, but somebody started one anyway. Its
        # marks must not fall back into the semi-final before it.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.start(SMALL, seconds=event.starts[0].seconds + 120.0)
        event.marks.append(
            FinishCompetitorElement("101", event.starts[0].seconds + 150.0, "finish")
        )
        brackets, log = event.build(_no_small_final(), _starts(list(range(1, 9))))
        semi = brackets[0].stages[0][0]
        assert semi.times[semi.numbers.index("101")] == pytest.approx(1.0)
        assert any("no heat of any ladder is called" in line for line in log)

    def test_a_heat_saved_without_a_start_is_an_error(self) -> None:
        # The chronometer's start-time field reads "0 00:00:00.000" until Start is
        # pressed, and Save group writes whatever the field holds.
        event = _Event().start(SEMI1, seconds=0.0)
        _brackets, log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert any("was saved with no start time" in line for line in log)

    def test_an_unusable_start_does_not_hold_up_the_rest_of_the_meeting(self) -> None:
        # One heat saved without pressing Start must not stop every other group: the
        # protocol is meant to be refreshed while the racing goes on, so the heat is
        # reported and then counts as not ridden.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.start(FINAL, seconds=0.0)
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi = brackets[0].stages[0][0]
        assert semi.has_results
        assert brackets[0].finishing_places(semi) == [1, 2, 3, 4]
        assert any(
            line.startswith("ERROR:") and "was saved with no start time" in line
            for line in log
        )
        assert not brackets[0].stages[1][0].was_started

    def test_a_heat_restarted_properly_is_not_reported(self) -> None:
        # The chronometer appends, so a heat saved without a start and then started
        # again has both lines; the later one is the real one.
        event = _Event()
        event.start(SEMI1, seconds=0.0)
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1001.0, "nextLap"))
        brackets, log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert not any("no start time" in line for line in log)
        assert brackets[0].stages[0][0].times[0] == pytest.approx(1.0)

    def test_a_dead_small_final_cannot_hold_up_its_group(self) -> None:
        # A one-round ladder has no small final to ride, so a stale line naming one
        # must not be able to block scoring either.
        brackets, _log = (
            _Event()
            .start(SMALL, seconds=0.0)
            .build(_ladder(4, 1), _starts([1, 2, 3, 4]))
        )
        assert brackets[0].stages[0][0].taken == 4

    def test_two_heats_on_one_start_are_reported_by_name(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.start(SEMI2, seconds=1000.0)
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        same = [line for line in log if "starting at the same time" in line]
        assert same and same[0].startswith("ERROR:")
        assert SEMI1 in same[0] and SEMI2 in same[0]

    def test_the_heat_that_copied_a_start_time_is_not_scored(self) -> None:
        # Semi-final 2 was saved without pressing Start, so it carries semi-final 1's
        # time and would have its own times measured from it -- three minutes out.
        # Semi-final 1 was recorded correctly and keeps its result.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        for gap, bib in enumerate(["101", "105", "104", "108"]):
            event.marks.append(FinishCompetitorElement(bib, 1038.0 + gap, "finish"))
        event.start(SEMI2, seconds=1000.0)
        for gap, bib in enumerate(["102", "106", "103", "107"]):
            event.marks.append(FinishCompetitorElement(bib, 1218.0 + gap, "finish"))
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi1, semi2 = brackets[0].stages[0]
        assert semi1.was_started and semi1.has_results
        assert brackets[0].finishing_places(semi1) == [1, 2, 3, 4]
        assert not semi2.was_started and not semi2.has_results
        assert any("starting at the same time" in line for line in log)

    def test_a_final_sharing_a_semi_finals_start_is_not_scored(self) -> None:
        # The chronometer keeps the start time in its field after Save group, so the
        # final saved without pressing Start again carries the semi-final's. Scoring
        # it from that span gave the final the semi-final's times and left the riders
        # of the other semi-final as DNF.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.start(FINAL, seconds=event.starts[0].seconds)
        for gap, bib in enumerate(["101", "102", "105", "106"]):
            event.marks.append(FinishCompetitorElement(bib, 2000.0 + gap, "finish"))
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi1 = brackets[0].stages[0][0]
        final = brackets[0].stages[1][0]
        assert not final.was_started
        assert not final.has_results
        # The semi-final it copied the time from was recorded correctly, so it keeps
        # its result and the rest of the meeting carries on.
        assert semi1.has_results
        assert brackets[0].finishing_places(semi1) == [1, 2, 3, 4]
        assert any("starting at the same time" in line for line in log)

    def test_a_late_disqualification_reaches_the_heat_the_rider_won(self) -> None:
        # The chronometer stamps a disqualification when the jury decides, which on a
        # video or a protest is after the next heat has gone off. The mark then fell
        # outside every window and the rider kept the heat he should have lost.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.start(SMALL, seconds=1120.0)
        event.marks.append(FinishCompetitorElement("106", 1130.0, "DSQ: cut in"))
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi2 = brackets[0].stages[0][1]
        assert semi2.disqualified[semi2.numbers.index("106")]
        assert "106" not in brackets[0].stages[1][0].numbers
        assert "103" in brackets[0].stages[1][0].numbers
        assert not any("belongs to no heat" in line for line in log)

    def test_a_rider_pulled_during_a_heat_is_disqualified_in_that_heat(self) -> None:
        # He won his semi-final and was taken off the course during the final. The
        # final's own window holds the mark, so the decision stays in the final and
        # the semi-final he won is untouched.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.ride(FINAL, ["102", "105", "106"], dsq=("101",))
        brackets, _log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi1 = brackets[0].stages[0][0]
        final = brackets[0].stages[1][0]
        assert not semi1.disqualified[semi1.numbers.index("101")]
        assert final.disqualified[final.numbers.index("101")]

    def test_a_disqualification_that_belongs_to_no_heat_is_an_error(self) -> None:
        # A bib nobody rides: the mark is a typo, and it used to be reported as a
        # finish mark, which told the referee to look in the wrong place.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.marks.append(FinishCompetitorElement("999", 1005.0, "DSQ: wrong bib"))
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert any(
            line.startswith("ERROR:") and "the disqualification of 999" in line
            for line in log
        )

    def test_a_rider_who_rode_on_after_a_late_disqualification_is_reported(
        self,
    ) -> None:
        # The jury decided between his heats and he rode the next one anyway. The
        # decision belongs to the heat he had last finished, which is where he was
        # when it was taken, and the heat he was not entitled to is worth a word.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.marks.append(FinishCompetitorElement("101", 1070.0, "DSQ: cut in"))
        event.ride(FINAL, ["101", "102", "105", "106"])
        brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        semi1 = brackets[0].stages[0][0]
        assert semi1.disqualified[semi1.numbers.index("101")]
        assert any(
            line.startswith("WARNING:") and "rode on after being disqualified" in line
            for line in log
        )

    def test_a_crossing_recorded_twice_is_dropped_by_the_minimal_lap_time(
        self,
    ) -> None:
        # Two timekeepers on the finish line, so every crossing is in the file twice.
        # Every other race type has dropped the copy all along.
        event = _Event().ride(SEMI1, ["101", "105", "104", "108"])
        for bib, when in (
            ("101", 1001.2),
            ("105", 1002.2),
            ("104", 1003.2),
            ("108", 1004.2),
        ):
            event.marks.append(FinishCompetitorElement(bib, when, "finish"))
        log: list[str] = []
        brackets = build_brackets(
            _ladder(),
            _starts(list(range(1, 9))),
            event.starts,
            event.marks,
            log,
            1,
            10.0,
        )
        semi = brackets[0].stages[0][0]
        assert semi.times[0] == pytest.approx(1.0)
        assert not [line for line in log if "crossed the line more often" in line]
        # Dropping a crossing is never silent: with the setting too large for the
        # lap it would be the ladder throwing real laps away.
        assert [line for line in log if "was dropped" in line]

    def test_without_the_setting_the_copy_is_still_counted(self) -> None:
        # The filter is off by default, so the ladder says what it sees.
        event = _Event().ride(SEMI1, ["101", "105", "104", "108"])
        event.marks.append(FinishCompetitorElement("101", 1001.2, "finish"))
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert [line for line in log if "crossed the line more often" in line]

    def test_a_start_saved_twice_still_closes_another_heats_window(self) -> None:
        # A heat saved again late in the day proves the heats before it are over, so
        # a rider of the final who abandoned is DNF rather than left on the course
        # for ever.
        event = _Event()
        event.ride(SEMI1, ["101", "105", "104", "108"])
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.ride(FINAL, ["101", "102", "105"])
        event.starts.append(GroupStartElement(group_id=SEMI1, seconds=9000.0))
        brackets, _log = event.build(_ladder(), _starts(list(range(1, 9))))
        final = brackets[0].stages[1][0]
        assert final.complete
        assert brackets[0].finishing_places(final) == [1, 2, 3, None]

    def test_a_heats_own_repeat_line_does_not_cut_its_window(self) -> None:
        # The other reading of a second line: a heat restarted after a false start.
        # Its own later line must not bound the ride it is the record of.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.start(SEMI1, seconds=2000.0)
        event.marks.append(FinishCompetitorElement("101", 2001.0, "finish"))
        event.start(SEMI2, seconds=3000.0)
        brackets, _log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert brackets[0].stages[0][0].times[0] == pytest.approx(1001.0)

    def test_a_heat_being_ridden_says_so_once(self) -> None:
        event = _Event()
        event.ride(SEMI2, ["102", "106", "103", "107"])
        event.start(SEMI1)
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        riding = [line for line in log if "is being ridden" in line]
        assert len(riding) == 1
        assert SEMI1 in riding[0]
        assert "4 of its rider(s) have not finished their laps" in riding[0]


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


class TestOnlyCrossingsCount:
    def test_a_lap_mark_is_a_crossing(self) -> None:
        # A one-lap heat timed with the chronometer in lap mode writes "nextLap".
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1002.0, "nextLap"))
        event.marks.append(FinishCompetitorElement("104", 1001.0, "nextLap"))
        bracket = event.build(_ladder(), _starts([1, 4]))[0][0]
        assert bracket.stages[0][0].numbers[:2] == ["104", "101"]

    def test_a_mark_that_is_not_a_crossing_does_not_beat_a_finish(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1005.0, "nextStage"))
        event.marks.append(FinishCompetitorElement("101", 1030.0, "finish"))
        event.marks.append(FinishCompetitorElement("104", 1025.0, "finish"))
        bracket = event.build(_ladder(), _starts([1, 4]))[0][0]
        semi = bracket.stages[0][0]
        assert semi.numbers[:2] == ["104", "101"]
        assert semi.times[semi.numbers.index("101")] == pytest.approx(30.0)

    def test_a_heat_with_only_other_marks_has_placed_nobody(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1005.0, "nextStage"))
        brackets, log = event.build(_ladder(), _starts([1, 4, 5, 8]))
        assert any("is being ridden" in line for line in log)
        assert not brackets[0].stages[0][0].complete
        assert brackets[0].finishing_places(brackets[0].stages[0][0]) == [None] * 4

    def _two_lap_event(self) -> _Event:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        for bib, laps in (("101", (10.0, 60.0)), ("104", (20.0, 50.0))):
            for gap in laps:
                event.marks.append(
                    FinishCompetitorElement(bib, 1000.0 + gap, "nextLap")
                )
        return event

    def test_the_last_lap_is_the_finish_not_the_first(self) -> None:
        # Scoring the earliest crossing would publish whoever led lap one.
        bracket = self._two_lap_event().build(
            [EliminatorGroup("G", 4, 2, laps=2)], _starts([1, 4])
        )[0][0]
        semi = bracket.stages[0][0]
        assert semi.numbers[:2] == ["104", "101"]
        assert semi.times[0] == pytest.approx(50.0)

    def test_a_rider_on_his_first_lap_is_not_placed_or_sent_on(self) -> None:
        # The live protocol rests on a placed rider being past the others. He is not
        # past anybody while they are all still riding the same lap he is.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1010.0, "nextLap"))
        brackets, _log = event.build(
            [EliminatorGroup("G", 4, 2, laps=3)], _starts(list(range(1, 9)))
        )
        semi = brackets[0].stages[0][0]
        assert brackets[0].finishing_places(semi) == [None] * 4
        assert brackets[0].stages[1][0].taken == 0

    def test_one_lap_is_the_default_so_a_crossing_is_a_result(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1010.0, "nextLap"))
        brackets, _log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert brackets[0].finishing_places(brackets[0].stages[0][0])[0] == 1
        assert brackets[0].stages[1][0].numbers[:1] == ["101"]

    def test_a_finish_mark_does_not_bypass_the_lap_count(self) -> None:
        # "Finish mode" is one switch for the whole session, so on a multi-lap heat
        # it stamps lap one as a finish too. Believing it places the lap-one leader.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1010.0, "finish"))
        brackets, _log = event.build(
            [EliminatorGroup("G", 4, 2, laps=3)], _starts(list(range(1, 9)))
        )
        assert brackets[0].finishing_places(brackets[0].stages[0][0]) == [None] * 4

    def test_every_lap_counts_however_it_was_stamped(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        for gap in (10.0, 20.0):
            event.marks.append(FinishCompetitorElement("101", 1000.0 + gap, "finish"))
        brackets, _log = event.build(
            [EliminatorGroup("G", 4, 2, laps=2)], _starts(list(range(1, 9)))
        )
        semi = brackets[0].stages[0][0]
        assert brackets[0].finishing_places(semi)[0] == 1
        assert semi.times[0] == pytest.approx(20.0)

    def test_crossing_more_often_than_the_heat_has_laps_is_reported(self) -> None:
        # The signal that the laps per heat setting is wrong.
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        for gap in (10.0, 20.0, 30.0):
            event.marks.append(FinishCompetitorElement("101", 1000.0 + gap, "nextLap"))
        _brackets, log = event.build(_ladder(), _starts(list(range(1, 9))))
        assert any("more often than the 1 lap(s)" in line for line in log)

    def test_the_lap_count_reaches_the_ladder_from_the_settings(self) -> None:
        assert parse_eliminator_groups(["G#4#2#"], laps=3)[0].laps == 3
        assert parse_eliminator_groups(["G#4#2#"])[0].laps == 1
        assert parse_eliminator_groups(["G#4#2#"], laps=0)[0].laps == 1

    def test_a_finish_mark_beats_a_later_lap_mark(self) -> None:
        event = _Event()
        event.start(SEMI1, seconds=1000.0)
        event.marks.append(FinishCompetitorElement("101", 1030.0, "finish"))
        event.marks.append(FinishCompetitorElement("101", 1040.0, "nextLap"))
        event.marks.append(FinishCompetitorElement("104", 1035.0, "finish"))
        bracket = event.build(_ladder(), _starts([1, 4]))[0][0]
        assert bracket.stages[0][0].numbers[:2] == ["101", "104"]


class TestGroupNamesWithStrayWhitespace:
    def test_a_padded_group_still_finds_its_ladder(self) -> None:
        start_list = [
            StartProtocolElement.from_line(
                f"{100 + p}#Rider#  G  #1#1#1990#T#C##{p}#", place_field=True
            )
            for p in (1, 4)
        ]
        brackets, log = _Event().build(_ladder(), start_list)
        assert brackets[0].stages[0][0].taken == 2
        # Nothing about the group being unknown or its riders having no seat.
        assert not [line for line in log if "ladder" in line]

    def test_the_key_is_just_the_trimmed_name(self) -> None:
        assert group_key("  G  ") == "G"
        assert group_key("") == ""

    def test_a_padded_group_is_not_reported_as_having_no_ladder(self) -> None:
        start_list = [
            StartProtocolElement.from_line(
                "101#Rider#  G  #1#1#1990#T#C##1#", place_field=True
            )
        ]
        assert start_list_groups(start_list) == ["G"]
        assert missing_ladders(_ladder(), start_list) == []


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
        event.start(SMALL)
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
        brackets, log = _Event().build(_ladder(), _starts([1, 2]))
        final = brackets[0].stages[1][0]
        assert final.has_results
        assert not final.ridden
        assert final.numbers[:2] == ["101", "102"]
        assert brackets[0].finishing_places(final)[:2] == [1, 2]
        # Medals handed out on qualification order deserve to be said out loud.
        assert any(
            line.startswith("WARNING:") and "was not ridden" in line for line in log
        )

    def test_an_unraced_round_below_the_final_is_only_noted(self) -> None:
        _brackets, log = _Event().build(_ladder(), _starts([1, 4]))
        notes = [line for line in log if "was not ridden" in line]
        assert notes
        assert not any(line.startswith("WARNING:") for line in notes[:1])

    def test_an_empty_heat_is_not_announced(self) -> None:
        _brackets, log = _Event().build(_ladder(), _starts([], group="Other"))
        assert not any("was not ridden" in line for line in log)

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

    def test_a_gap_the_protocol_cannot_print_is_a_tie(self) -> None:
        # The default protocol shows one decimal, so 2.00 and 2.003 come out the
        # same on the page -- and a difference nobody can see is one nobody can
        # defend when the result is protested.
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 2.0, 2.003, 4.0])
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("ERROR:")

    def test_a_gap_over_half_a_bucket_that_still_prints_the_same_is_a_tie(
        self,
    ) -> None:
        # 2.06 and 2.14 are 0.08 apart, more than half of the tenth the protocol
        # prints, and both come out as 00:00:02.1. The old rule looked for a gap
        # under half a tenth and let the other half of every bucket through
        # unreported -- on the line that sends riders on, here.
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 2.06, 2.14, 4.0])
        tie = [line for line in log if "share a time" in line]
        assert tie and tie[0].startswith("ERROR:")
        assert "decides who goes on" in tie[0]

    def test_a_gap_the_protocol_does_print_is_no_tie(self) -> None:
        # 2.04 and 2.06 are 0.02 apart, which the old rule called a tie, but they
        # print as 00:00:02.0 and 00:00:02.1 and the page tells them apart.
        log = self._tie(SEMI1, ["101", "105", "104", "108"], [1.0, 2.04, 2.06, 4.0])
        assert not [line for line in log if "share a time" in line]

    def test_a_finer_protocol_tells_the_two_apart(self) -> None:
        event = _Event().ride(
            SEMI1, ["101", "105", "104", "108"], offsets=[1.0, 2.0, 2.003, 4.0]
        )
        log: list[str] = []
        build_brackets(
            _ladder(),
            _starts(list(range(1, 9))),
            event.starts,
            event.marks,
            log,
            3,
        )
        assert not [line for line in log if "share a time" in line]

    def test_an_exact_dead_heat_in_a_heat_shares_a_place(self) -> None:
        # Both rode the same millisecond and both keep their own line.
        event = _Event().ride(
            SEMI1, ["101", "105", "104", "108"], offsets=[1.0, 2.0, 2.0, 4.0]
        )
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert bracket.finishing_places(bracket.stages[0][0]) == [1, 2, 2, 4]

    def test_times_that_only_print_the_same_keep_their_own_places(self) -> None:
        # 2.06 and 2.14 come out as the same tenth and are reported as such, but the
        # riders did not ride the same time and the ladder does not say they did.
        event = _Event().ride(
            SEMI1, ["101", "105", "104", "108"], offsets=[1.0, 2.06, 2.14, 4.0]
        )
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert bracket.finishing_places(bracket.stages[0][0]) == [1, 2, 3, 4]

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

    def test_a_disqualified_finalist_does_not_move_the_small_final_up(self) -> None:
        # The small final was ridden for fifth to eighth. A finalist losing his
        # classification does not vacate a place for riders who already rode.
        event = self._full_event()
        event.ride(SMALL, ["104", "103", "108", "107"])
        event.ride(FINAL, ["102", "105", "106"], dsq=("101",))
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
        assert bracket.finishing_places(bracket.small_final) == [5, 6, 7, 8]

    def test_a_finalist_who_did_not_finish_does_not_either(self) -> None:
        event = self._full_event()
        event.ride(SMALL, ["104", "103", "108", "107"])
        event.ride(FINAL, ["101", "102", "105"])
        bracket = event.build(_ladder(), _starts(list(range(1, 9))))[0][0]
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
