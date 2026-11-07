"""Knockout brackets for Eliminator Finals.

A port of the C++ generator's ``GroupEliminator`` / ``FinalRound``. The bracket is
fully determined by two numbers -- how many ride each heat and how many rounds deep
the ladder goes -- so it is built here as plain lists of heats per stage instead of
the original tree of pointers, which computes the same seats in far less code.

In this mode the three input files mean this:

* ``ladders.txt`` -- ``group id # riders per heat # rounds #``, one ladder per group.
  A separate file because ``groups.txt`` is the chronometer's own, and the chronometer
  appends a line to it on every start.
* ``start.txt``   -- field 9 holds the qualification place, not a start delay. That
  is the field the seeding export writes, already renumbered past anyone the
  qualification disqualified.
* ``groups.txt``  -- one line per heat ridden: the heat's name and when it started.
  The chronometer writes it by picking the heat from its group list, so each heat is
  an ordinary "group" to it.
* ``results.txt`` -- plain finish marks, ``bib # time of day # action #``, exactly as
  in a timed race. A heat's result is the order of its own marks.

A heat is scored from times when a start was recorded for it. A heat that cannot
eliminate anybody and was never started is not worth riding, so its riders go through
in qualification order and the protocol says it was not ridden. Anything else is still
to come and stays empty.

Stage 0 is the first round ridden and stage ``rounds - 1`` is the final; the small
final shares that last stage, as heat number 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
    get_field,
)

#: The C++ version accepted only these, and threw on anything else. Kept: the seeding
#: formula below pairs a rider against one opponent, so a heat splits exactly in two.
HEAT_SIZES = (2, 4)
#: Each heat is fed by two heats of the previous stage. The C++ code carried this as a
#: configurable "elimination coefficient" but only ever passed 2.0.
_FEEDERS = 2
#: Default gap below which two times count as equal: half of a tenth, the protocol's
#: own default precision. A difference the protocol cannot print is one a referee
#: cannot defend, so the run is told the real precision instead where it knows it.
_TIE = 0.05
#: What the chronometers write for a line crossing. They also write "nextStage", and
#: a penalty record carries its own action, and neither is a rider finishing a heat.
_CROSSINGS = ("finish", "nextLap")
#: A window with nothing after it: this heat is the last one started, so it may still
#: be being ridden.
_OPEN = float("inf")
#: Places that get a medal in the big final, so a tie between them is not a detail.
_PODIUM = 3

#: How the qualification places are spread over the first round's heats.
#:
#: The UCI way splits riders who qualified next to each other into different heats,
#: so the two fastest can only meet in the final. It is the one in the UCI Cycling
#: Regulations, Part 4 Mountain Bike, Annex 5 (XCE schedule): for sixteen riders the
#: regulations print exactly 1-8-9-16, 4-5-12-13, 2-7-10-15, 3-6-11-14.
SEEDING_SPLIT_ADJACENT = "Split adjacent seeds (UCI)"
#: The other way keeps riders who qualified next to each other together: eight riders
#: become 1-2-7-8 and 3-4-5-6. Some race regulations are written this way. It balances
#: the heats by the sum of their places just as well, but the two fastest then meet a
#: round earlier for every round the ladder gains -- in the semi-final with eight
#: riders, the quarter-final with sixteen, the 1/8 with thirty-two. Beyond two heats
#: no regulation spells it out; it is the same idea carried on.
SEEDING_KEEP_ADJACENT = "Keep adjacent seeds together"
SEEDING_SCHEMES = (SEEDING_SPLIT_ADJACENT, SEEDING_KEEP_ADJACENT)


@dataclass(frozen=True)
class EliminatorGroup:
    """One ladder: which group it is for, and its shape."""

    group_id: str
    heat_size: int
    rounds: int
    #: Which way the qualification places are spread over the first round.
    seeding: str = SEEDING_SPLIT_ADJACENT
    #: How many laps a heat of this ladder is. One almost everywhere, and the code
    #: needs to be told: a rider is only past the others once he has ridden them all,
    #: and until then a crossing of his is a lap, not a result.
    laps: int = 1
    #: Whether the meeting rides a small final for places behind the podium. Many do
    #: not, and then the riders the last round dropped simply have no further heat.
    small_final: bool = True

    @property
    def capacity(self) -> int:
        """How many qualification places the ladder has seats for."""
        return _FEEDERS ** (self.rounds - 1) * self.heat_size


@dataclass
class Heat:
    """One race in the ladder, and its outcome once it has been ridden."""

    stage: int
    number: int
    #: Qualification places seeded into this heat; only stage 0 is seeded directly.
    seeds: tuple[int, ...] = ()
    #: Bibs by finishing order once the result is in, "" for a seat nobody filled.
    numbers: list[str] = field(default_factory=list)
    #: Whether the rider in each seat has crossed the line. False reads as DNF once
    #: the heat is complete, and as a rider still on the course before that.
    finished: list[bool] = field(default_factory=list)
    #: Time ridden per seat, -1 where there is none.
    times: list[float] = field(default_factory=list)
    #: Whether the rider in each seat was disqualified in this heat.
    disqualified: list[bool] = field(default_factory=list)
    has_results: bool = False
    #: Whether the heat is over, so a rider without a crossing did not finish. A heat
    #: can hold results without being complete: a rider's place is settled the moment
    #: he crosses -- nobody still on the course can finish ahead of him -- while
    #: whether the others are DNF or still riding is not settled until the heat ends.
    complete: bool = False
    is_small_final: bool = False
    #: When this heat was started, -1 when no start was recorded for it.
    start_seconds: float = -1.0
    #: The next start after this one: a mark past it belongs to another heat.
    window_end: float = float("inf")
    #: Whether it was actually raced, as opposed to going through unraced.
    ridden: bool = False

    @property
    def taken(self) -> int:
        """How many seats actually hold a rider."""
        return sum(1 for number in self.numbers if number)

    @property
    def advancing(self) -> int:
        """How many of its riders this heat sends on to the next round."""
        return len(self.numbers) // _FEEDERS

    @property
    def accounted(self) -> int:
        """How many of its riders this heat knows the fate of: they crossed the line
        or they were disqualified. The rest are still on the course, or did not
        finish once the heat is over."""
        return sum(
            1
            for seat, bib in enumerate(self.numbers)
            if bib and (self.times[seat] >= 0 or self.disqualified[seat])
        )

    @property
    def was_started(self) -> bool:
        """Whether a real start time was recorded for this heat.

        Midnight of day zero is not one. The chronometer's start-time field reads
        "0 00:00:00.000" until Start is pressed and it saves whatever the field
        holds, so a heat saved without a start carries that -- and a window opening
        there would swallow the whole morning's marks.
        """
        return self.start_seconds > 0


class EliminatorBracket:
    """The heats of one group, and the rules that move riders between them."""

    def __init__(self, group: EliminatorGroup) -> None:
        self.group = group
        #: Qualification place per bib, so a heat that was not ridden can be ordered
        #: by it at any stage, not only where the seats still hold the seeding.
        self.places: dict[str, int] = {}
        #: Below this a gap between two times is no gap at all. Set from the digits
        #: the protocol actually prints, because a difference it cannot show is one
        #: nobody can defend when the result is protested.
        self.tie_tolerance = _TIE
        size = group.heat_size
        # stages[0] is the first round ridden; the last stage holds the final.
        self.stages: list[list[Heat]] = []
        for stage in range(group.rounds):
            count = _FEEDERS ** (group.rounds - 1 - stage)
            self.stages.append(
                [self._blank(stage, number, size) for number in range(count)]
            )
        self.small_final = self._blank(group.rounds - 1, 1, size)
        self.small_final.seeds = tuple(range(size + 1, 2 * size + 1))
        self.small_final.is_small_final = True
        self._seed()

    @staticmethod
    def _blank(stage: int, number: int, size: int) -> Heat:
        return Heat(
            stage=stage,
            number=number,
            numbers=[""] * size,
            finished=[False] * size,
            times=[-1.0] * size,
            disqualified=[False] * size,
        )

    # -- construction ---------------------------------------------------------

    def _seed(self) -> None:
        """Hand every seat in the ladder the qualification place that belongs in it.

        The final holds places 1..n; descending one stage, each heat keeps its own
        places and gains their mirror images about ``2^depth * n + 1``. Which of its
        places each side keeps is what the seeding scheme decides.
        """
        size = self.group.heat_size
        self.stages[-1][0].seeds = tuple(range(1, size + 1))
        for stage in range(self.group.rounds - 1, 0, -1):
            depth = self.group.rounds - stage
            mirror = _FEEDERS**depth * size + 1
            for parent in self.stages[stage]:
                for side in range(_FEEDERS):
                    child = self.stages[stage - 1][parent.number * _FEEDERS + side]
                    child.seeds = _child_seeds(
                        parent.seeds, side, size, mirror, self.group.seeding
                    )

    # -- lookup ---------------------------------------------------------------

    def heat(self, stage: int, number: int) -> Heat:
        """The heat at ``stage``/``number``; number 1 of the last stage is the small
        final, which is where the C++ version kept it too."""
        if stage == self.group.rounds - 1 and number == 1:
            return self.small_final
        return self.stages[stage][number]

    def heats_in_stage(self, stage: int) -> list[Heat]:
        """Every heat of a stage this ladder can hold riders in, small final and all.

        The one place that decides whether the small final exists, so a heat offered
        to the referee, a heat that is scored and a heat that is drawn are the same
        set -- two of those disagreeing is what published a blank protocol once.
        """
        heats = list(self.stages[stage])
        if stage == self.group.rounds - 1 and self.has_small_final:
            heats.append(self.small_final)
        return heats

    def all_heats(self) -> list[Heat]:
        """Every heat of the ladder, first round first."""
        return [
            heat
            for stage in range(self.group.rounds)
            for heat in self.heats_in_stage(stage)
        ]

    def is_big_final(self, heat: Heat) -> bool:
        return not heat.is_small_final and heat.stage == self.group.rounds - 1

    @property
    def has_small_final(self) -> bool:
        """Whether this ladder has a small final at all.

        Either the meeting does not ride one, or the ladder is a single final: there
        is then no round below it to drop anybody out of, so its small final could
        never hold a rider whatever the setting says.
        """
        return self.group.rounds > 1 and self.group.small_final

    def parent(self, heat: Heat) -> Heat | None:
        """The heat this one sends its riders up to, or None for a final.

        Public because the path a rider can still take through the ladder is fixed by
        the shape alone, before any result -- which is what lets a finish mark be
        bounded without knowing who won.
        """
        return self._parent(heat)

    def _parent(self, heat: Heat) -> Heat | None:
        if heat.is_small_final or heat.stage + 1 >= self.group.rounds:
            return None
        return self.stages[heat.stage + 1][heat.number // _FEEDERS]

    def _feeders(self, heat: Heat) -> list[Heat]:
        if heat.is_small_final or heat.stage == 0:
            return []
        below = self.stages[heat.stage - 1]
        return [below[heat.number * _FEEDERS + side] for side in range(_FEEDERS)]

    # -- filling --------------------------------------------------------------

    def place_competitor(
        self, bib: str, place: int, log: list[str] | None = None
    ) -> bool:
        """Seat a qualified rider by their qualification place. False when it has no
        seat in this ladder -- a place beyond the bracket simply does not ride.

        Two riders given the same place is a slip in the seeding file, and one of
        them loses their ride, so it is reported rather than silently applied.
        """
        if not 1 <= place <= self.group.capacity:
            return False
        for heat in self.stages[0]:
            for seat, seeded in enumerate(heat.seeds):
                if seeded != place:
                    continue
                displaced = heat.numbers[seat]
                if displaced and log is not None:
                    log.append(
                        f"ERROR: {bib} and {displaced} both hold qualification "
                        f"place {place} in group {self.group.group_id}; "
                        f"{displaced} loses its seat"
                    )
                heat.numbers[seat] = bib
                self.places[bib] = place
                return True
        return False

    def ready(self, heat: Heat) -> bool:
        """Whether the heats that feed this one are over.

        Over, not merely scored. Riders move up the moment they cross, so a heat
        below may already have sent somebody on while others are still riding; acting
        on that would let this heat be scored, or go through on a bye, against a field
        that is not final yet -- which is how a protocol refreshed every half minute
        would hand out medals in the middle of a race.
        """
        if heat.stage == 0:
            return True
        if heat.is_small_final:
            return all(f.complete for f in self._feeders(self.stages[-1][0]))
        return all(feeder.complete for feeder in self._feeders(heat))

    def is_bye(self, heat: Heat) -> bool:
        """Whether this heat cannot eliminate anybody, so riding it is pointless."""
        return heat.taken * _FEEDERS <= len(heat.numbers)

    def ride_unraced(self, heat: Heat) -> None:
        """Send a heat's riders through in qualification order, without times.

        Seat order will not do. At stage 0 the seats pair first against last, and
        above it they hold whoever the heats below sent up, in the order those were
        scored -- so in both cases the better qualifier can be sitting second. The
        qualification place is the only standing a heat nobody rode can go on.
        """
        unplaced = len(self.places) + 1
        order = sorted(
            (bib for bib in heat.numbers if bib),
            key=lambda bib: self.places.get(bib, unplaced),
        )
        self._record(heat, order, len(order), {}, set(), ridden=False, complete=True)

    def ride_timed(
        self, heat: Heat, marks: list[FinishCompetitorElement], log: list[str]
    ) -> list[FinishCompetitorElement]:
        """Score a heat from the marks that fall inside its own start window, and say
        which marks it used, so a mark no heat claimed can be reported.

        Everything known is written at once: a rider who has crossed gets his time
        and his place there and then, and goes up to the next round if that place is
        inside the two the heat sends on. Nobody still on the course can finish ahead
        of him, so neither is going to change.

        The heat is over once every one of its riders is accounted for, or once a
        later heat has started. Until then the riders without a crossing are shown
        with nothing against them rather than as DNF.
        """
        times, dsq, used = _heat_marks(heat, marks, self.group.laps)
        accounted = len(set(times) | dsq)
        complete = accounted >= heat.taken or heat.window_end != _OPEN
        order = sorted(times, key=lambda bib: times[bib])
        log.extend(self._tie_problems(heat, order, times))
        if complete and heat.taken and not accounted:
            log.append(
                f"ERROR: {heat_name(self, heat)} was ridden but has no finish marks "
                "at all; every rider in it is shown as DNF"
            )
        self._record(
            heat, order, len(order), times, dsq, ridden=True, complete=complete
        )
        return used

    def _tie_problems(
        self, heat: Heat, order: list[str], times: dict[str, float]
    ) -> list[str]:
        """Equal times, told apart by whether they decide anything.

        Two riders cannot really share a hundredth, so a tie is a timing slip either
        way; what changes is the damage. A tie across the line that sends riders on,
        or between medals in the big final, has to be resolved before the protocol
        means anything -- the rest only has to be noticed.
        """
        problems: list[str] = []
        for tied in _tied_runs(order, times, self.tie_tolerance):
            first, last = tied[0], tied[-1]
            if self.is_big_final(heat):
                decisive = first < _PODIUM
            elif heat.is_small_final:
                decisive = False
            else:
                decisive = first < heat.advancing <= last
            level = "ERROR" if decisive else "WARNING"
            bibs = ", ".join(order[i] for i in tied)
            tail = " and it decides who goes on" if decisive else ""
            problems.append(
                f"{level}: {bibs} share a time in {heat_name(self, heat)}{tail}"
            )
        return problems

    def _record(
        self,
        heat: Heat,
        order: list[str],
        classified_count: int,
        times: dict[str, float],
        dsq: set[str],
        *,
        ridden: bool,
        complete: bool,
    ) -> None:
        """Write what is known of a heat into it and move its riders onward.

        Only the riders who have crossed are classified; the seats left over keep the
        heat's other riders unclassified. Whether that reads as DNF or as a rider
        still on the course is what ``complete`` decides -- the places themselves do
        not wait for it, because a rider who has crossed cannot be overtaken by one
        who has not. A disqualified rider is never classified, whatever the clock
        said, so he sits past the classified seats like a rider who never finished.
        """
        rest = [number for number in heat.numbers if number and number not in order]
        filled = order + rest
        size = len(heat.numbers)
        heat.numbers = (filled + [""] * size)[:size]
        heat.finished = [
            i < classified_count and bool(heat.numbers[i]) for i in range(size)
        ]
        heat.times = [times.get(number, -1.0) for number in heat.numbers]
        heat.disqualified = [number in dsq for number in heat.numbers]
        heat.has_results = True
        heat.ridden = ridden
        heat.complete = complete
        if heat.is_small_final:
            return
        going_on = [
            heat.numbers[i]
            for i in range(heat.advancing)
            if heat.finished[i] and heat.numbers[i]
        ]
        parent = self._parent(heat)
        if parent is not None:
            _fill_free_seats(parent, going_on)
        if heat.stage + 2 == self.group.rounds and self.has_small_final:
            dropped = [
                heat.numbers[i]
                for i in range(heat.advancing, size)
                if heat.finished[i] and heat.numbers[i]
            ]
            _fill_free_seats(self.small_final, dropped)

    def finishing_places(self, heat: Heat) -> list[int | None]:
        """The place shown against each seat, or None where the protocol says DNF.

        The small final carries on from the big one, so its winner is fifth in a
        four-rider ladder rather than first all over again.
        """
        offset = 0
        if heat.is_small_final:
            # Everyone who was in the big final placed ahead of this heat, whether
            # they were classified there or not: a finalist who abandoned or was
            # disqualified did not vacate a place for a rider who had already ridden
            # for fifth. Falling back to the seat count matters because the small
            # final is usually ridden first, when the big one holds nobody yet.
            big_final = self.stages[-1][0]
            offset = big_final.taken or len(big_final.numbers)
        return [
            offset + seat + 1 if heat.has_results and classified else None
            for seat, classified in enumerate(heat.finished)
        ]


def _child_seeds(
    parent_seeds: tuple[int, ...],
    side: int,
    size: int,
    mirror: int,
    seeding: str = SEEDING_SPLIT_ADJACENT,
) -> tuple[int, ...]:
    """The places feeding one side of a parent heat.

    A heat of two holds one place of its parent and that place's mirror whichever
    scheme is asked for: there is no pair of adjacent places inside it to keep
    together or to split, so the schemes cannot differ there.
    """
    if size == 2:
        kept = parent_seeds[side]
        return (kept, mirror - kept)
    if seeding == SEEDING_KEEP_ADJACENT:
        first, second = parent_seeds[2 * side], parent_seeds[2 * side + 1]
    else:
        first, second = parent_seeds[side], parent_seeds[3 - side]
    return (first, second, mirror - second, mirror - first)


def normalize_seeding(value: str) -> str:
    """A scheme name the ladders understand; anything else falls back to the UCI one.

    A config written by another build, or edited by hand, must not quietly change how
    a championship is seeded, so only an exact name is honoured.
    """
    return value if value in SEEDING_SCHEMES else SEEDING_SPLIT_ADJACENT


def _fill_free_seats(heat: Heat, bibs: list[str]) -> None:
    for bib in bibs:
        for seat, taken in enumerate(heat.numbers):
            if not taken:
                heat.numbers[seat] = bib
                break


def _heat_marks(
    heat: Heat, marks: list[FinishCompetitorElement], laps: int = 1
) -> tuple[dict[str, float], set[str], list[FinishCompetitorElement]]:
    """The time each rider of this heat rode, who was disqualified in it, and which
    marks the heat accounted for.

    A disqualification wins over a finish mark however they are ordered: the
    chronometer stamps it when the jury decides, which is usually after the rider
    has already crossed.
    """
    times: dict[str, float] = {}
    dsq: set[str] = set()
    used: list[FinishCompetitorElement] = []
    for bib in heat.numbers:
        if not bib:
            continue
        seen = [
            mark
            for mark in marks
            if mark.competitor_id == bib
            and heat.start_seconds <= mark.seconds < heat.window_end
        ]
        used.extend(seen)
        crossing = finish_crossing(seen, laps)
        if any(mark.is_dsq for mark in seen):
            dsq.add(bib)
        elif crossing is not None:
            times[bib] = crossing - heat.start_seconds
    return times, dsq, used


def finish_crossing(
    marks: list[FinishCompetitorElement], laps: int = 1
) -> float | None:
    """When this rider finished the heat, out of their marks inside its window.

    A real finish mark wins: that is the chronometer being told which crossing was
    the finish, so there is nothing to count. Otherwise the chronometer is stamping
    laps, and the rider has finished once he has ridden the lap count of the heat --
    before that his crossings are laps, and placing him on one would publish whoever
    led lap one as the winner and send him up a round.
    """
    finishes = [mark.seconds for mark in marks if mark.action == "finish"]
    if finishes:
        return max(finishes)
    crossed = sorted(mark.seconds for mark in marks if mark.action in _CROSSINGS)
    return crossed[laps - 1] if len(crossed) >= max(laps, 1) else None


def tie_tolerance(n_signs_after_point: int) -> float:
    """Half of the smallest difference the protocol prints, so two times that come
    out identical on the page are treated as identical in the ladder."""
    return 0.5 * 10.0 ** -max(n_signs_after_point, 0)


def _tied_runs(
    order: list[str], times: dict[str, float], tolerance: float
) -> list[list[int]]:
    """Positions in the finishing order that share a time, as runs of two or more."""
    runs: list[list[int]] = []
    current: list[int] = []
    for index in range(1, len(order)):
        if abs(times[order[index]] - times[order[index - 1]]) < tolerance:
            current = current or [index - 1]
            current.append(index)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def heat_title(bracket: EliminatorBracket, heat: Heat) -> str:
    """ "1/4 final 2", "Final" or "Small final", as the C++ version titled them."""
    remaining = 2 ** (bracket.group.rounds - heat.stage - 1)
    if remaining != 1:
        return f"1/{remaining} final {heat.number + 1}"
    return "Small final" if heat.is_small_final else "Final"


def heat_name(bracket: EliminatorBracket, heat: Heat) -> str:
    """What this heat is called in the chronometer's group list.

    Generated at both ends and never parsed back, so there is one spelling and a
    rename in the chronometer's list shows up as a heat nobody started.
    """
    return f"{bracket.group.group_id} - {heat_title(bracket, heat)}"


def heat_names(brackets: list[EliminatorBracket]) -> list[str]:
    """Every heat of every ladder, in the order a meeting rides them.

    The small final goes before the big one, which is the order it is ridden in, so
    the referee picks heats off the top of the chronometer's list as the day runs.
    """
    names: list[str] = []
    for bracket in brackets:
        for stage in range(bracket.group.rounds):
            heats = [heat for heat in bracket.all_heats() if heat.stage == stage]
            heats.sort(key=lambda heat: not heat.is_small_final)
            names.extend(heat_name(bracket, heat) for heat in heats)
    return names


def parse_eliminator_groups(
    lines: list[str],
    sep: str = "#",
    small_final: bool = True,
    seeding: str = SEEDING_SPLIT_ADJACENT,
    laps: int = 1,
) -> list[EliminatorGroup]:
    """Read the ladders out of the ladder file, skipping lines that describe none.

    Whether a small final is ridden and how the places are spread over the heats are
    decisions for the meeting as a whole -- they come out of its regulations -- so
    they come from the settings rather than from the file, which carries only the
    shape of each group's ladder.
    """
    groups: list[EliminatorGroup] = []
    for line in lines:
        group_id = get_field(line, 0, sep).strip()
        if not group_id:
            continue
        heat_size = _as_int(get_field(line, 1, sep))
        rounds = _as_int(get_field(line, 2, sep))
        if heat_size not in HEAT_SIZES or rounds < 1:
            continue
        groups.append(
            EliminatorGroup(
                group_id,
                heat_size,
                rounds,
                normalize_seeding(seeding),
                max(laps, 1),
                small_final,
            )
        )
    return groups


def ladder_lines(rows: list[tuple[str, str, str]]) -> list[str]:
    """The ladder file as text, the inverse of ``parse_eliminator_groups``.

    Takes the numbers as typed rather than parsed, so a group waiting for its shape
    keeps its line: the referee sees it again next time instead of the group quietly
    going missing, and the run refuses while it is still blank.
    """
    return [
        f"{group.strip()}#{heat.strip()}#{rounds.strip()}#"
        for group, heat, rounds in rows
        if group.strip()
    ]


def group_problems(lines: list[str], sep: str = "#") -> list[str]:
    """Why a ladder line does not describe a ladder, for the run log."""
    problems: list[str] = []
    for line in lines:
        group_id = get_field(line, 0, sep).strip()
        if not group_id:
            continue
        heat_size = _as_int(get_field(line, 1, sep))
        rounds = _as_int(get_field(line, 2, sep))
        if heat_size not in HEAT_SIZES:
            problems.append(
                f"ERROR: group {group_id} rides {heat_size} per heat; "
                f"only {' and '.join(str(s) for s in HEAT_SIZES)} are supported"
            )
        elif rounds < 1:
            problems.append(f"ERROR: group {group_id} needs at least one round")
    return problems


def group_key(text: str) -> str:
    """A group id with its edges trimmed.

    The ladder file's ids are read trimmed, and the start protocol's are not trimmed
    at all, so everything that matches the two sides goes through this. Without it a
    group field with a stray space is a group that can never be given a ladder.
    """
    return text.strip()


def start_list_groups(start_list: list[StartProtocolElement]) -> list[str]:
    """The groups that qualified riders, in start protocol order, each once."""
    groups: list[str] = []
    for start in start_list:
        name = group_key(start.group_id)
        if name and name not in groups:
            groups.append(name)
    return groups


def missing_ladders(
    groups: list[EliminatorGroup], start_list: list[StartProtocolElement]
) -> list[str]:
    """Groups that qualified riders but have no ladder, in start protocol order.

    An unfilled ladder line is skipped rather than guessed at, and a group skipped
    that way would come out as a heading with nothing under it, so the run stops on
    this instead of writing a protocol that is quietly short of a whole group.
    """
    described = {group.group_id for group in groups}
    return [name for name in start_list_groups(start_list) if name not in described]


def _as_int(value: str) -> int:
    try:
        return int(str(value).strip())
    except TypeError, ValueError:
        return 0


def _one_ladder_per_group(
    groups: list[EliminatorGroup], log: list[str]
) -> list[EliminatorBracket]:
    """One bracket per group id. A second ladder for the same group would stand
    empty while the riders seat themselves in the other, so it is dropped."""
    brackets: list[EliminatorBracket] = []
    seen: set[str] = set()
    for group in groups:
        if group.group_id in seen:
            log.append(
                f"ERROR: group {group.group_id} describes more than one ladder; "
                "only the first is used"
            )
            continue
        seen.add(group.group_id)
        brackets.append(EliminatorBracket(group))
    return brackets


def unusable_starts(
    groups: list[EliminatorGroup],
    group_list: list[GroupStartElement],
    log: list[str] | None = None,
) -> list[str]:
    """Heats with a recorded start that cannot be used, by name.

    The same check the scoring itself makes, run on throwaway ladders so the caller
    can refuse before anything is written: nothing can be scored around a start the
    chronometer never took, and the protocol would come out blank or, worse, with an
    earlier heat rewritten from the next one's marks.
    """
    # Through the same dedupe the scoring uses: a group with two ladder lines gets one
    # bracket there, and building two here would make the second one's heats look like
    # a pair of heats sharing a start and refuse the run for the wrong reason.
    brackets = _one_ladder_per_group(groups, [])
    return _open_windows(
        brackets, _heat_starts(group_list), log if log is not None else []
    )


def _heat_starts(group_list: list[GroupStartElement]) -> dict[str, float]:
    """When each heat started, last line winning.

    The chronometer appends a line per start and never rewrites, so a heat started
    again after a false start has two lines and the later one is the real one -- and
    a heat first saved without a start and then properly started is fine.
    """
    return {
        group_key(gs.group_id): gs.seconds
        for gs in group_list
        if group_key(gs.group_id)
    }


def _open_windows(
    brackets: list[EliminatorBracket], starts: dict[str, float], log: list[str]
) -> list[str]:
    """Give every started heat the span its own marks fall in, and name the heats
    whose recorded start cannot be used.

    The span ends where the next heat starts, whichever ladder that heat belongs to:
    a rider rides several heats, so his bib carries several honest marks, and only
    the span keeps the one that belongs to this heat. Ordering the heats by their
    start time is what makes this work without looking ahead in the ladder, which
    could not be done anyway -- who rides the next heat is decided by this one.
    """
    started: list[tuple[EliminatorBracket, Heat]] = []
    bad: list[str] = []
    for bracket in brackets:
        for heat in bracket.all_heats():
            name = heat_name(bracket, heat)
            seconds = starts.get(name)
            if seconds is None:
                continue
            if seconds <= 0:
                # Not a warning: if that heat was ridden, its marks are still in the
                # file, and with no start of its own to bound them they would fall
                # into the window of the heat before it and rewrite a result that was
                # already right. Nothing is written until the start time is fixed.
                log.append(
                    f"ERROR: {name} was saved with no start time; press Start before "
                    "Save group, then save that heat again"
                )
                bad.append(name)
                continue
            heat.start_seconds = seconds
            started.append((bracket, heat))
    started.sort(key=lambda pair: pair[1].start_seconds)
    by_start: dict[float, list[str]] = {}
    for bracket, heat in started:
        by_start.setdefault(heat.start_seconds, []).append(heat_name(bracket, heat))
    for names in by_start.values():
        if len(names) > 1:
            # The chronometer keeps the start time in its field after Save group, so
            # saving the next heat without pressing Start again gives it the same
            # one. Neither heat then has a span of its own to hold its marks.
            log.append(
                "ERROR: these heats are recorded as starting at the same time, so "
                "neither has a window of its own for finish marks: " + ", ".join(names)
            )
            bad.extend(names)
    # Every recorded start closes a window, including one that names no heat of any
    # ladder. Such a line is a heat that was ridden -- the small final of a meeting
    # that turned them off, a group spelled differently -- and its marks are in the
    # file. Ignoring it as a boundary lets them fall into the heat before it and
    # rewrite a result that was already right.
    boundaries = sorted({when for when in starts.values() if when > 0})
    for _bracket, heat in started:
        after = [when for when in boundaries if when > heat.start_seconds]
        heat.window_end = after[0] if after else _OPEN
    return bad


def build_brackets(
    groups: list[EliminatorGroup],
    start_list: list[StartProtocolElement],
    group_list: list[GroupStartElement],
    marks: list[FinishCompetitorElement],
    log: list[str],
    tolerance: float = _TIE,
) -> list[EliminatorBracket]:
    """Build every ladder, seat the qualifiers and ride the heats through it.

    ``tolerance`` is the gap below which two times count as equal; pass
    :func:`tie_tolerance` of the protocol's own precision.
    """
    brackets = _one_ladder_per_group(groups, log)
    for built in brackets:
        built.tie_tolerance = tolerance
    by_id = {built.group.group_id: built for built in brackets}
    for start in start_list:
        bracket = by_id.get(group_key(start.group_id))
        if bracket is None:
            continue
        place = start.start_place
        if not bracket.place_competitor(start.competitor_id, place, log):
            log.append(
                f"WARNING: {start.competitor_id} has qualification place {place}, "
                f"outside the ladder of group {group_key(start.group_id)}"
            )
    starts = _heat_starts(group_list)
    used: set[int] = set()
    if _open_windows(brackets, starts, log):
        # One unusable start is enough to spoil another heat's result, because its
        # marks have no window of their own and fall into the heat before it. Score
        # nothing rather than something wrong.
        return brackets
    used = _score(brackets, marks, log)
    known = set(heat_names(brackets))
    for name in starts:
        if name not in known:
            log.append(f"WARNING: no heat of any ladder is called {name}")
    for bib in _unclaimed(marks, used):
        log.append(
            f"WARNING: the finish mark for {bib} belongs to no heat that was ridden"
        )
    return brackets


def _unclaimed(marks: list[FinishCompetitorElement], used: set[int]) -> list[str]:
    """Bibs with a mark no heat accounted for, each named once.

    Either the bib is a typo or the mark landed outside every heat's window, and both
    mean a rider is missing from a protocol that otherwise looks complete.
    """
    bibs: list[str] = []
    for mark in marks:
        if id(mark) not in used and mark.competitor_id not in bibs:
            bibs.append(mark.competitor_id)
    return bibs


def _score(
    brackets: list[EliminatorBracket],
    marks: list[FinishCompetitorElement],
    log: list[str],
) -> set[int]:
    """Score what can be scored, over and over until nothing moves.

    Scoring a heat fills the one above it, which may in turn become rideable, and a
    heat high in the ladder may well have been started before a lower one was
    entered, so a single pass down the stages is not enough. Returns the marks that
    were accounted for.
    """
    used: set[int] = set()
    moved = True
    while moved:
        moved = False
        for bracket in brackets:
            for heat in bracket.all_heats():
                if heat.has_results or not bracket.ready(heat):
                    continue
                if heat.was_started:
                    used.update(
                        id(mark) for mark in bracket.ride_timed(heat, marks, log)
                    )
                elif bracket.is_bye(heat):
                    bracket.ride_unraced(heat)
                    if heat.taken:
                        # Worth saying out loud for either final: those are places on
                        # the podium handed out on qualification order, with no race
                        # behind them.
                        last = heat.stage == bracket.group.rounds - 1
                        level = "WARNING: " if last else ""
                        log.append(
                            f"{level}{heat_name(bracket, heat)} was not ridden; its "
                            "riders go through in qualification order"
                        )
                else:
                    # Still to be ridden: leaving it empty is the whole point, so a
                    # protocol refreshed mid-event shows the final as pending rather
                    # than handing out its medals on qualification order.
                    continue
                moved = True
    log.extend(_still_riding(brackets))
    return used


def _still_riding(brackets: list[EliminatorBracket]) -> list[str]:
    """Heats that have started and have no marks in yet: their riders are on the
    course. Said once, after the scoring has settled, because the scoring runs
    several passes and would otherwise repeat itself on each of them.
    """
    return [
        f"{heat_name(bracket, heat)} is being ridden; "
        f"{heat.taken - heat.accounted} of its rider(s) have no crossing yet"
        for bracket in brackets
        for heat in bracket.all_heats()
        if heat.was_started and heat.has_results and not heat.complete
    ]
