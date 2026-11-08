"""The one property the whole Eliminator Finals mode rests on, checked directly.

Every serious defect this mode has had was a violation of a single statement:

    every finish mark belongs to at most one heat, and a heat's marks are its own.

They looked like unrelated bugs -- a start time of midnight swallowing the morning's
marks, a missing start leaving the previous heat's span open to infinity, a lap mark
beating a finish, two heats sharing a start -- but each one is that sentence failing
in a different scenario. Finding them one scenario at a time is what a review does;
this module checks the sentence instead, over randomly generated meetings, so the
whole class fails loudly rather than one member of it at a time.

The checks run on what ``build_brackets`` produced, from the outside: a seat's time is
turned back into the moment of day it came from, and that moment has to be a real mark
of that rider, inside that heat's own span, used by no other heat.

``_own_span`` is the design in one line. Everything else here checks consequences of
it, so moving to a different rule for which marks a heat owns means changing that one
function and nothing else in this module.

What this does not cover, because random meetings almost never produce the shape: the
order of a heat that went through unraced above the first round. That rule has its own
test, ``TestUnraced`` in ``test_eliminator.py``. Both were checked by breaking the code
on purpose and confirming something fails.
"""

from __future__ import annotations

import random

import pytest

from app.eliminator import (
    HEAT_SIZES,
    SEEDING_SCHEMES,
    EliminatorBracket,
    EliminatorGroup,
    Heat,
    build_brackets,
    heat_name,
    heat_names,
)
from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
)

#: Enough meetings to hit the awkward combinations, fast enough to stay in the suite.
_CASES = 300
#: Fixed, so a failure is reproducible from the case number alone.
_SEED = 20261108
_CROSSINGS = ("finish", "nextLap")


# -- the meeting generator ----------------------------------------------------


class _Meeting:
    """One randomly shaped finals round, with the two chronometer files it produced.

    Deliberately includes the mistakes a referee makes: a heat saved before Start was
    pressed, a heat saved twice, a stray bib, a mark that arrives after the next heat
    has gone, a lap mark before the finish, a disqualification. Those are exactly the
    inputs that used to break the assignment.
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.group = EliminatorGroup(
            "G",
            rng.choice(HEAT_SIZES),
            rng.randint(1, 3),
            rng.choice(SEEDING_SCHEMES),
            rng.choice((1, 1, 1, 2, 3)),
            small_final=rng.random() < 0.7,
        )
        #: Thin fields on purpose: when a heat sends up only one rider, the round
        #: above cannot eliminate anybody and goes through unraced -- and there the
        #: seats hold arrival order, not qualification order. That is where unraced
        #: heats above the first round come from at all.
        self.sparse = rng.random() < 0.4
        #: The chronometer with "Finish mode" off stamps every crossing as a lap, so
        #: the heat has no finish mark at all and its last lap is the result. That is
        #: how the real one was set up, and it is the only way the lap counting is
        #: reached, so half the meetings are run that way.
        self.lap_mode = rng.random() < 0.5
        riders = rng.randint(0, self.group.capacity)
        self.start_list = [
            StartProtocolElement.from_line(
                f"{100 + place}#Rider {place}#G#1#1#1990#T#C##{place}#",
                place_field=True,
            )
            for place in range(1, riders + 1)
        ]
        self.starts: list[GroupStartElement] = []
        self.marks: list[FinishCompetitorElement] = []
        self._clock = 36000.0
        self._plan()

    def _plan(self) -> None:
        """Ride the heats in the order a meeting would, deciding each one's fate.

        Who is in a later heat is not knowable here -- the ladder decides it from the
        rounds below -- so every heat gets marks for a random handful of the group's
        riders, and the ladder credits whichever of them it actually seated. That is
        what gets riders, and these checks, above the first round at all.
        """
        shape = EliminatorBracket(self.group)
        for start in self.start_list:
            shape.place_competitor(start.competitor_id, start.start_place)
        pool = [start.competitor_id for start in self.start_list]
        for heat in shape.all_heats():
            # The first round's field is known from the seeding alone, so those heats
            # get their real occupants; above it nobody knows yet, so a handful of
            # the group's riders get marks and the ladder credits the ones it seated.
            own = [bib for bib in heat.numbers if bib]
            self._ride(heat_name(shape, heat), own if heat.stage == 0 else pool)

    def _ride(self, name: str, pool: list[str]) -> None:
        roll = self.rng.random()
        if roll < 0.15:
            return  # never started
        self._clock += self.rng.uniform(60.0, 300.0)
        when = 0.0 if roll < 0.2 else self._clock
        self.starts.append(GroupStartElement(group_id=name, seconds=when))
        if roll < 0.25:
            # Saved twice: the chronometer appends, the later line is the real one.
            self.starts.append(GroupStartElement(group_id=name, seconds=self._clock))
        if roll < 0.3:
            return  # started, nobody across yet
        field = (
            self.rng.sample(pool, min(len(pool), self.group.heat_size)) if pool else []
        )
        most = 1 if self.sparse else len(field)
        finishers = (
            self.rng.sample(field, self.rng.randint(0, min(most, len(field))))
            if field
            else []
        )
        for index, bib in enumerate(finishers):
            self._cross(bib, 20.0 + index * self.rng.uniform(0.2, 3.0))
        if self.rng.random() < 0.1:
            self.marks.append(
                FinishCompetitorElement("999", self._clock + 25.0, "finish")
            )
        if self.rng.random() < 0.1 and field:
            # A mark that turns up long after the next heat has gone.
            self.marks.append(
                FinishCompetitorElement(field[0], self._clock + 400.0, "finish")
            )

    def _cross(self, bib: str, offset: float) -> None:
        """One rider's marks in the heat that is being ridden."""
        at = self._clock
        laps = self.group.laps
        for lap in range(1, laps):
            # Every lap but the last. A rider is not past anybody until he has ridden
            # them all, so none of these may place him or send him up a round.
            self.marks.append(
                FinishCompetitorElement(bib, at + offset * lap / (laps + 1), "nextLap")
            )
        if self.rng.random() < 0.15:
            # Not a crossing at all, and must not be read as one.
            self.marks.append(
                FinishCompetitorElement(bib, at + offset / 3, "nextStage")
            )
        if self.lap_mode:
            self.marks.append(FinishCompetitorElement(bib, at + offset, "nextLap"))
        else:
            self.marks.append(FinishCompetitorElement(bib, at + offset, "finish"))
            if self.rng.random() < 0.15:
                # Stamped twice. The timed pipeline warns about this, so it happens,
                # and which of the two counts decides the heat.
                self.marks.append(
                    FinishCompetitorElement(bib, at + offset + 2.0, "finish")
                )
        if self.rng.random() < 0.1:
            self.marks.append(FinishCompetitorElement(bib, at + 40.0, "DSQ: cut in"))

    def build(self) -> tuple[list[EliminatorBracket], list[str]]:
        log: list[str] = []
        brackets = build_brackets(
            [self.group],
            self.start_list,
            self.starts,
            self.marks,
            log,
            1,
        )
        return brackets, log


# -- what the result has to satisfy -------------------------------------------


def _recorded_starts(meeting: _Meeting, bracket: EliminatorBracket) -> dict[str, float]:
    """The heat starts as the chronometer left them, last line winning.

    Read from the generated files, not from the heats the code filled in, so the
    span below is derived from the input rather than from the thing under test.
    """
    named = set(heat_names([bracket]))
    starts: dict[str, float] = {}
    for line in meeting.starts:
        if line.group_id in named:
            starts[line.group_id] = line.seconds
    return {name: when for name, when in starts.items() if when > 0}


def _own_span(starts: dict[str, float], heat_start: float) -> float:
    """Where a heat's claim on the marks ends.

    This is the design in one line: a heat owns the marks from its own start until
    the next heat starts, whichever ladder that heat belongs to. Everything else in
    this module checks consequences of it, so changing the design means changing
    this function and nothing else here.
    """
    nexts = [when for when in starts.values() if when > heat_start]
    return min(nexts) if nexts else float("inf")


def _ended_on(
    marks: list[FinishCompetitorElement], start: float, span: float, laps: int
) -> float | None:
    """When this rider ended a heat of ``laps`` laps running from ``start`` to
    ``span``: the crossing on which he completed the last of them. The action is not
    consulted -- "Finish mode" is one switch for the whole session, so it stamps
    every lap of a multi-lap heat as a finish."""
    inside = [mark for mark in marks if start <= mark.seconds < span]
    crossed = sorted(mark.seconds for mark in inside if mark.action in _CROSSINGS)
    return crossed[laps - 1] if len(crossed) >= laps else None


def _claims(bracket: EliminatorBracket) -> list[tuple[str, float, Heat]]:
    """Every (bib, moment of day, heat) the ladder decided to credit."""
    out: list[tuple[str, float, Heat]] = []
    for heat in bracket.all_heats():
        for seat, bib in enumerate(heat.numbers):
            if bib and heat.times[seat] >= 0:
                out.append((bib, heat.start_seconds + heat.times[seat], heat))
    return out


def _check_every_credit_is_a_real_crossing(
    meeting: _Meeting, bracket: EliminatorBracket, where: str
) -> None:
    """A credited time is a crossing of that rider, and no crossing is spent twice.

    The second half is the sentence the whole mode rests on: a rider rides several
    heats, his bib carries several honest marks, and each heat must take its own.
    """
    claims = _claims(bracket)
    crossings = {
        (mark.competitor_id, round(mark.seconds, 6))
        for mark in meeting.marks
        if mark.action in _CROSSINGS
    }
    for bib, moment, heat in claims:
        assert (bib, round(moment, 6)) in crossings, (
            f"{where}: {heat_name(bracket, heat)} credits {bib} with a time that is "
            "no crossing of theirs"
        )
    spent = [(bib, round(moment, 6)) for bib, moment, _heat in claims]
    assert len(spent) == len(set(spent)), f"{where}: a crossing was credited twice"


def _check_credits_come_from_the_heats_own_span(
    meeting: _Meeting, bracket: EliminatorBracket, where: str
) -> None:
    """A credited crossing is inside the heat's span, and it is the one the rider
    ended the heat on: the last finish mark, or the last lap mark when the
    chronometer was never told which crossing was the finish.

    An earlier crossing is a lap, and scoring it publishes whoever led lap one.
    """
    starts = _recorded_starts(meeting, bracket)
    by_bib: dict[str, list[FinishCompetitorElement]] = {}
    for mark in meeting.marks:
        by_bib.setdefault(mark.competitor_id, []).append(mark)
    for bib, moment, heat in _claims(bracket):
        span = _own_span(starts, heat.start_seconds)
        assert heat.was_started, f"{where}: a heat with no start credited {bib}"
        assert heat.start_seconds <= moment < span, (
            f"{where}: {heat_name(bracket, heat)} credits {bib} with a crossing "
            "from outside its own span"
        )
        ended = _ended_on(
            by_bib.get(bib, []), heat.start_seconds, span, bracket.group.laps
        )
        assert ended is not None and round(moment, 6) == round(ended, 6), (
            f"{where}: {heat_name(bracket, heat)} credits {bib} with a crossing "
            "that is not the one they ended the heat on"
        )


def _check_each_heat_is_in_crossing_order(
    bracket: EliminatorBracket, where: str
) -> None:
    """A ridden heat is ordered by those crossings. This is what decides who goes
    up, so it is the one ordering that has consequences."""
    for heat in bracket.all_heats():
        if not heat.ridden:
            continue
        timed = [
            (heat.times[seat], bib)
            for seat, bib in enumerate(heat.numbers)
            if bib and heat.times[seat] >= 0
        ]
        assert timed == sorted(timed), (
            f"{where}: {heat_name(bracket, heat)} is not in the order its riders "
            "crossed"
        )


def _check_a_result_has_a_reason(bracket: EliminatorBracket, where: str) -> None:
    """A heat has a result because it was ridden, or because riding it was pointless,
    and it is over only when it has the right to be.

    Over means every rider accounted for, or a later heat already started. Calling a
    heat over early is what turns riders still on the course into DNF and lets the
    round above go through on a bye.
    """
    for heat in bracket.all_heats():
        if not heat.has_results:
            continue
        assert not heat.ridden or heat.start_seconds > 0, (
            f"{where}: {heat_name(bracket, heat)} is marked as ridden although its "
            "recorded start is midnight of day zero, which is no start at all"
        )
        assert heat.ridden == heat.was_started, (
            f"{where}: {heat_name(bracket, heat)} is marked ridden={heat.ridden} "
            f"with was_started={heat.was_started}"
        )
        if not heat.ridden:
            assert bracket.is_bye(heat), (
                f"{where}: {heat_name(bracket, heat)} went through unraced although "
                "riding it would have eliminated somebody"
            )
            assert all(time < 0 for time in heat.times), (
                f"{where}: {heat_name(bracket, heat)} was not ridden yet has times"
            )
            assert heat.complete, (
                f"{where}: {heat_name(bracket, heat)} went through unraced but is "
                "not over, so its riders would show as neither placed nor DNF"
            )
        elif heat.complete:
            assert heat.accounted >= heat.taken or heat.window_end != float("inf"), (
                f"{where}: {heat_name(bracket, heat)} is over with "
                f"{heat.taken - heat.accounted} rider(s) unaccounted for and no later "
                "heat started, so they may still be on the course"
            )


def _check_a_round_waits_for_the_one_below(
    bracket: EliminatorBracket, where: str
) -> None:
    """Nothing is scored or waved through above a heat that is still being ridden.

    Riders move up the moment they cross, so the heat above fills early on purpose.
    What it must not do is be scored, or go through on a bye, while a rider who could
    still join it is on the course.
    """
    for heat in bracket.all_heats():
        if heat.stage == 0 or not heat.has_results:
            continue
        # The small final takes the riders the big final's own feeders dropped.
        fed = bracket.stages[-1][0] if heat.is_small_final else heat
        feeders = [
            bracket.stages[fed.stage - 1][fed.number * 2 + side] for side in range(2)
        ]
        assert all(feeder.complete for feeder in feeders), (
            f"{where}: {heat_name(bracket, heat)} has a result although a heat "
            "feeding it is still being ridden"
        )


def _check_crossing_is_enough_to_be_placed(
    bracket: EliminatorBracket, where: str
) -> None:
    """A rider who crossed is placed and sent on at once, without waiting for the
    heat to end. His place cannot change: nobody still on the course can finish
    ahead of somebody who has already finished.
    """
    for heat in bracket.all_heats():
        if not heat.ridden:
            continue
        for seat, bib in enumerate(heat.numbers):
            if not bib:
                continue
            crossed = heat.times[seat] >= 0
            assert crossed == heat.finished[seat], (
                f"{where}: {heat_name(bracket, heat)} seat {seat} has "
                f"crossed={crossed} but classified={heat.finished[seat]}"
            )
            if crossed and seat < heat.advancing and bracket.parent(heat) is not None:
                above = bracket.parent(heat)
                assert above is not None and bib in above.numbers, (
                    f"{where}: {bib} crossed {seat + 1} of {heat.advancing} going on "
                    f"in {heat_name(bracket, heat)} but is not in the round above"
                )


def _check_only_seated_riders_and_once_each(
    meeting: _Meeting, bracket: EliminatorBracket, where: str
) -> None:
    """A rider sits in one seat of a heat, in one heat per round, and is somebody the
    start protocol knows."""
    known = {start.competitor_id for start in meeting.start_list}
    for heat in bracket.all_heats():
        field = [bib for bib in heat.numbers if bib]
        assert len(field) == len(set(field)), f"{where}: a rider twice in one heat"
        for bib in field:
            assert bib in known, f"{where}: {bib} is in no start protocol"
    for stage in range(bracket.group.rounds):
        riders = [
            bib for heat in bracket.heats_in_stage(stage) for bib in heat.numbers if bib
        ]
        assert len(riders) == len(set(riders)), f"{where}: a rider twice in a round"


def _check_the_heat_set_is_one_set(bracket: EliminatorBracket, where: str) -> None:
    """The heats offered to the referee are the heats that are scored, and none of
    them could never hold a rider.

    Offering a small final that cannot be filled makes the referee start a heat whose
    marks then belong to nothing; two places disagreeing about the set is what
    published a blank protocol once.
    """
    assert sorted(heat_names([bracket])) == sorted(
        heat_name(bracket, heat) for heat in bracket.all_heats()
    ), f"{where}: the heat list and the scored ladder disagree"
    walked = [heat for heat in bracket.all_heats() if heat.is_small_final]
    assert bracket.has_small_final == bool(walked), (
        f"{where}: has_small_final={bracket.has_small_final} but the ladder walks "
        f"{len(walked)} of them"
    )
    assert bracket.has_small_final == (
        bracket.group.rounds > 1 and bracket.group.small_final
    ), f"{where}: the small final exists against the settings"


def _check_unraced_heats_follow_qualification(
    bracket: EliminatorBracket, where: str
) -> None:
    """Seat order will not do: the first round pairs first against last, and above it
    the seats hold whoever the heats below sent up, in the order those were scored."""
    for heat in bracket.all_heats():
        if heat.has_results and not heat.ridden:
            seated = [bib for bib in heat.numbers if bib]
            places = [bracket.places.get(bib, 0) for bib in seated]
            assert places == sorted(places), (
                f"{where}: {heat_name(bracket, heat)} went through unraced but not "
                f"in qualification order: {seated}"
            )


def _check_places_and_advancement(bracket: EliminatorBracket, where: str) -> None:
    """Places inside a heat run in order without repeats, only classified seats have
    one, and whoever went up was classified in the top half of the heat below."""
    for heat in bracket.all_heats():
        places = bracket.finishing_places(heat)
        numbered = [place for place in places if place is not None]
        assert numbered == sorted(numbered), f"{where}: places out of order"
        assert len(numbered) == len(set(numbered)), f"{where}: a place twice"
        for seat, place in enumerate(places):
            assert (place is None) != heat.finished[seat], (
                f"{where}: {heat_name(bracket, heat)} seat {seat} has place "
                f"{place} with finished={heat.finished[seat]}"
            )
    for stage in range(bracket.group.rounds - 1):
        for heat in bracket.stages[stage]:
            if not heat.has_results:
                continue
            above = bracket.stages[stage + 1][heat.number // 2]
            for seat in range(heat.advancing):
                bib = heat.numbers[seat]
                if bib and heat.finished[seat]:
                    assert bib in above.numbers, (
                        f"{where}: {bib} was classified to go on but is not in "
                        f"{heat_name(bracket, above)}"
                    )


def _check(meeting: _Meeting, bracket: EliminatorBracket, case: int) -> None:
    where = f"case {case} ({bracket.group})"
    _check_every_credit_is_a_real_crossing(meeting, bracket, where)
    _check_credits_come_from_the_heats_own_span(meeting, bracket, where)
    _check_each_heat_is_in_crossing_order(bracket, where)
    _check_a_result_has_a_reason(bracket, where)
    _check_a_round_waits_for_the_one_below(bracket, where)
    _check_crossing_is_enough_to_be_placed(bracket, where)
    _check_only_seated_riders_and_once_each(meeting, bracket, where)
    _check_the_heat_set_is_one_set(bracket, where)
    _check_unraced_heats_follow_qualification(bracket, where)
    _check_places_and_advancement(bracket, where)


@pytest.mark.parametrize("case", range(_CASES))
def test_the_mark_assignment_holds(case: int) -> None:
    meeting = _Meeting(random.Random(_SEED + case))  # noqa: S311
    brackets, _log = meeting.build()
    for bracket in brackets:
        _check(meeting, bracket, case)


def test_the_generator_actually_produces_awkward_meetings() -> None:
    """A property test that only ever sees tidy input proves nothing.

    Every count here is a situation that broke this mode once, so if a change to the
    generator stops producing one of them, that is a hole in the net and this fails
    rather than the suite quietly getting weaker.
    """
    seen = dict.fromkeys(
        (
            "zero start",
            "saved twice",
            "never started",
            "disqualified",
            "lap mark",
            "not a crossing",
            "stray bib",
            "late mark",
            "stamped twice",
            "unraced",
            "the other seeding scheme",
        ),
        0,
    )
    for case in range(_CASES):
        meeting = _Meeting(random.Random(_SEED + case))  # noqa: S311
        names = [start.group_id for start in meeting.starts]
        actions = {mark.action for mark in meeting.marks}
        full = len(heat_names([EliminatorBracket(meeting.group)]))
        seen["zero start"] += any(line.seconds <= 0 for line in meeting.starts)
        seen["saved twice"] += len(names) != len(set(names))
        seen["never started"] += len(set(names)) < full
        seen["disqualified"] += any(mark.is_dsq for mark in meeting.marks)
        seen["lap mark"] += "nextLap" in actions
        seen["not a crossing"] += "nextStage" in actions
        seen["stray bib"] += any(m.competitor_id == "999" for m in meeting.marks)
        seen["the other seeding scheme"] += meeting.group.seeding == SEEDING_SCHEMES[1]
        stamps = [
            (m.competitor_id, round(m.seconds / 1000))
            for m in meeting.marks
            if m.action == "finish"
        ]
        seen["stamped twice"] += len(stamps) != len(set(stamps))
        seen["late mark"] += len(meeting.marks) > 0 and any(
            mark.seconds > max(line.seconds for line in meeting.starts) + 350.0
            for mark in meeting.marks
        )
        for bracket in meeting.build()[0]:
            seen["unraced"] += any(
                heat.has_results and not heat.ridden and heat.taken
                for heat in bracket.all_heats()
            )
    thin = {name: count for name, count in seen.items() if count < 5}
    assert not thin, f"the generator stopped producing: {thin} (of {_CASES} cases)"
