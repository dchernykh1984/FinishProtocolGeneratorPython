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
#: Two marks closer together than this are the same hundredth to the chronometer.
_TIE = 0.0005
#: What the chronometers write for a line crossing. They also write "nextStage", and
#: a penalty record carries its own action, and neither is a rider finishing a heat.
_CROSSINGS = ("finish", "nextLap")
#: Places that get a medal in the big final, so a tie between them is not a detail.
_PODIUM = 3


@dataclass(frozen=True)
class EliminatorGroup:
    """One ladder: which group it is for, and its shape."""

    group_id: str
    heat_size: int
    rounds: int

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
    #: Whether the rider in each seat was classified; False reads as DNF.
    finished: list[bool] = field(default_factory=list)
    #: Time ridden per seat, -1 where there is none.
    times: list[float] = field(default_factory=list)
    #: Whether the rider in each seat was disqualified in this heat.
    disqualified: list[bool] = field(default_factory=list)
    has_results: bool = False
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
        places and gains their mirror images about ``2^depth * n + 1``, which is the
        usual bracket pairing (first against last).
        """
        size = self.group.heat_size
        self.stages[-1][0].seeds = tuple(range(1, size + 1))
        for stage in range(self.group.rounds - 1, 0, -1):
            depth = self.group.rounds - stage
            mirror = _FEEDERS**depth * size + 1
            for parent in self.stages[stage]:
                for side in range(_FEEDERS):
                    child = self.stages[stage - 1][parent.number * _FEEDERS + side]
                    child.seeds = _child_seeds(parent.seeds, side, size, mirror)

    # -- lookup ---------------------------------------------------------------

    def heat(self, stage: int, number: int) -> Heat:
        """The heat at ``stage``/``number``; number 1 of the last stage is the small
        final, which is where the C++ version kept it too."""
        if stage == self.group.rounds - 1 and number == 1:
            return self.small_final
        return self.stages[stage][number]

    def heats_in_stage(self, stage: int) -> list[Heat]:
        """Every heat of a stage, the small final included."""
        heats = list(self.stages[stage])
        if stage == self.group.rounds - 1:
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

        A one-round ladder is a single final: there is no round below it to drop
        anybody out of, so its small final can never hold a rider.
        """
        return self.group.rounds > 1

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
        """Whether the heats that feed this one have been ridden."""
        if heat.stage == 0:
            return True
        if heat.is_small_final:
            return all(f.has_results for f in self._feeders(self.stages[-1][0]))
        return all(feeder.has_results for feeder in self._feeders(heat))

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
        self._record(heat, order, len(order), {}, set(), ridden=False)

    def ride_timed(
        self, heat: Heat, marks: list[FinishCompetitorElement], log: list[str]
    ) -> list[FinishCompetitorElement]:
        """Score a heat from the marks that fall inside its own start window, and
        say which marks it used, so a mark no heat claimed can be reported."""
        times, dsq, used = _heat_marks(heat, marks)
        order = sorted(times, key=lambda bib: times[bib])
        log.extend(self._tie_problems(heat, order, times))
        if not order and not dsq and heat.taken:
            log.append(
                f"ERROR: {heat_name(self, heat)} was started but has no finish marks"
            )
        self._record(heat, order, len(order), times, dsq, ridden=True)
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
        for tied in _tied_runs(order, times):
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
    ) -> None:
        """Write a finishing order into a heat and move its riders onward.

        A result may list only the riders who went through; the seats left over keep
        the heat's other riders, marked as not advancing, which is how they come out
        as DNF in the protocol. A disqualified rider is never one of them, whatever
        the clock said, so he sits past the classified seats like a rider who never
        finished.
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
        if heat.stage + 2 == self.group.rounds:
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
    parent_seeds: tuple[int, ...], side: int, size: int, mirror: int
) -> tuple[int, ...]:
    """The places feeding one side of a parent heat."""
    if size == 2:
        kept = parent_seeds[side]
        return (kept, mirror - kept)
    first, second = parent_seeds[side], parent_seeds[3 - side]
    return (first, second, mirror - second, mirror - first)


def _fill_free_seats(heat: Heat, bibs: list[str]) -> None:
    for bib in bibs:
        for seat, taken in enumerate(heat.numbers):
            if not taken:
                heat.numbers[seat] = bib
                break


def _heat_marks(
    heat: Heat, marks: list[FinishCompetitorElement]
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
        crossings = [mark.seconds for mark in seen if mark.action in _CROSSINGS]
        if any(mark.is_dsq for mark in seen):
            dsq.add(bib)
        elif crossings:
            times[bib] = min(crossings) - heat.start_seconds
    return times, dsq, used


def _tied_runs(order: list[str], times: dict[str, float]) -> list[list[int]]:
    """Positions in the finishing order that share a time, as runs of two or more."""
    runs: list[list[int]] = []
    current: list[int] = []
    for index in range(len(order)):
        same = index > 0 and abs(times[order[index]] - times[order[index - 1]]) < _TIE
        if same:
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
            heats = [
                heat
                for heat in bracket.heats_in_stage(stage)
                if bracket.has_small_final or not heat.is_small_final
            ]
            heats.sort(key=lambda heat: not heat.is_small_final)
            names.extend(heat_name(bracket, heat) for heat in heats)
    return names


def parse_eliminator_groups(lines: list[str], sep: str = "#") -> list[EliminatorGroup]:
    """Read the ladders out of the ladder file, skipping lines that describe none."""
    groups: list[EliminatorGroup] = []
    for line in lines:
        group_id = get_field(line, 0, sep).strip()
        if not group_id:
            continue
        heat_size = _as_int(get_field(line, 1, sep))
        rounds = _as_int(get_field(line, 2, sep))
        if heat_size not in HEAT_SIZES or rounds < 1:
            continue
        groups.append(EliminatorGroup(group_id, heat_size, rounds))
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
    groups: list[EliminatorGroup], group_list: list[GroupStartElement]
) -> list[str]:
    """Heats with a recorded start that cannot be used, by name.

    Only midnight of day zero, which is what the chronometer writes when Save group
    comes before Start. Nothing can be scored around it, so the caller refuses the
    whole run rather than writing a protocol in which an earlier heat was rewritten.
    """
    named = set(heat_names([EliminatorBracket(group) for group in groups]))
    return [
        gs.group_id for gs in group_list if gs.group_id in named and gs.seconds <= 0
    ]


def _heat_starts(group_list: list[GroupStartElement]) -> dict[str, float]:
    """When each heat started, last line winning.

    The chronometer appends a line per start and never rewrites, so a heat started
    again after a false start has two lines and the later one is the real one.
    """
    return {gs.group_id: gs.seconds for gs in group_list if gs.group_id}


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
    started: list[Heat] = []
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
                    "Save group, or remove its line from the heat start file"
                )
                bad.append(name)
                continue
            heat.start_seconds = seconds
            started.append(heat)
    started.sort(key=lambda heat: heat.start_seconds)
    for index, heat in enumerate(started):
        following = started[index + 1 :]
        heat.window_end = following[0].start_seconds if following else float("inf")
        if heat.window_end == heat.start_seconds:
            log.append(
                "WARNING: two heats are recorded as starting at the same time; "
                "one of them has no window of its own for finish marks"
            )
    return bad


def build_brackets(
    groups: list[EliminatorGroup],
    start_list: list[StartProtocolElement],
    group_list: list[GroupStartElement],
    marks: list[FinishCompetitorElement],
    log: list[str],
) -> list[EliminatorBracket]:
    """Build every ladder, seat the qualifiers and ride the heats through it."""
    brackets = _one_ladder_per_group(groups, log)
    by_id = {bracket.group.group_id: bracket for bracket in brackets}
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
                    used.update(id(m) for m in bracket.ride_timed(heat, marks, log))
                elif bracket.is_bye(heat):
                    bracket.ride_unraced(heat)
                    if heat.taken:
                        # Worth saying out loud for the final: those are medals
                        # handed out on qualification order, with no race behind it.
                        level = "WARNING: " if bracket.is_big_final(heat) else ""
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
    return used
