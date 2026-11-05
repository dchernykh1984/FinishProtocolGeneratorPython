"""Knockout brackets for Eliminator Finals.

A port of the C++ generator's ``GroupEliminator`` / ``FinalRound``. The bracket is
fully determined by two numbers -- how many ride each heat and how many rounds deep
the ladder goes -- so it is built here as plain lists of heats per stage instead of
the original tree of pointers, which computes the same seats in far less code.

In this mode the three input files mean something else than in a timed race, exactly
as they did in the C++ version:

* ``groups.txt``  -- ``group id # riders per heat # rounds #``, one ladder per group.
* ``start.txt``   -- field 9 holds the qualification place, not a start delay. That
  is the field the Eliminator Qualification text export writes.
* ``results.txt`` -- one line per heat, the bibs in finishing order (or only those
  who went through). No timing marks are read at all: a heat result is an order.

Stage 0 is the first round ridden and stage ``rounds - 1`` is the final; the small
final shares that last stage, as heat number 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import StartProtocolElement, get_field

#: The C++ version accepted only these, and threw on anything else. Kept: the seeding
#: formula below pairs a rider against one opponent, so a heat splits exactly in two.
HEAT_SIZES = (2, 4)
#: Each heat is fed by two heats of the previous stage. The C++ code carried this as a
#: configurable "elimination coefficient" but only ever passed 2.0.
_FEEDERS = 2


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
    has_results: bool = False
    is_small_final: bool = False

    @property
    def taken(self) -> int:
        """How many seats actually hold a rider."""
        return sum(1 for number in self.numbers if number)


class EliminatorBracket:
    """The heats of one group, and the rules that move riders between them."""

    def __init__(self, group: EliminatorGroup) -> None:
        self.group = group
        size = group.heat_size
        # stages[0] is the first round ridden; the last stage holds the final.
        self.stages: list[list[Heat]] = []
        for stage in range(group.rounds):
            count = _FEEDERS ** (group.rounds - 1 - stage)
            self.stages.append(
                [
                    Heat(
                        stage=stage,
                        number=number,
                        numbers=[""] * size,
                        finished=[False] * size,
                    )
                    for number in range(count)
                ]
            )
        self.small_final = Heat(
            stage=group.rounds - 1,
            number=1,
            seeds=tuple(range(size + 1, 2 * size + 1)),
            numbers=[""] * size,
            finished=[False] * size,
            is_small_final=True,
        )
        self._seed()

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
                return True
        return False

    def advance_byes(self) -> None:
        """Complete heats that cannot eliminate anyone.

        A heat with no more riders than it would send on is not worth riding, so its
        riders go through unraced. The C++ version did the same before reading any
        result, which is what keeps a ladder with empty seats moving.
        """
        for stage in range(self.group.rounds):
            for heat in self.heats_in_stage(stage):
                # Only once the heats below have been ridden: an empty seat upstream
                # is not a bye, it is a seat still waiting to be filled.
                if heat.has_results or not self._ready(heat):
                    continue
                if heat.taken * _FEEDERS > len(heat.numbers):
                    continue
                order = [number for number in heat.numbers if number]
                self._record(heat, order, classified_count=len(order))

    def apply_result(self, order: list[str]) -> Heat | None:
        """Apply one heat result -- bibs in finishing order -- to the heat it belongs
        to, and return that heat. ``None`` when no heat is waiting for it."""
        if not order:
            return None
        for stage in range(self.group.rounds):
            for heat in self.heats_in_stage(stage):
                if heat.has_results or not self._ready(heat):
                    continue
                if all(bib in heat.numbers for bib in order):
                    self._record(heat, order, classified_count=len(order))
                    return heat
        return None

    def _ready(self, heat: Heat) -> bool:
        """Whether the heats that feed this one have been ridden."""
        if heat.stage == 0:
            return True
        if heat.is_small_final:
            return all(f.has_results for f in self._feeders(self.stages[-1][0]))
        return all(feeder.has_results for feeder in self._feeders(heat))

    def _record(self, heat: Heat, order: list[str], classified_count: int) -> None:
        """Write a finishing order into a heat and move its riders onward.

        A result may list only the riders who went through; the seats left over keep
        the heat's other riders, marked as not advancing, which is how they come out
        as DNF in the protocol.
        """
        rest = [number for number in heat.numbers if number and number not in order]
        filled = order + rest
        size = len(heat.numbers)
        heat.numbers = (filled + [""] * size)[:size]
        heat.finished = [
            i < classified_count and bool(heat.numbers[i]) for i in range(size)
        ]
        heat.has_results = True
        if heat.is_small_final:
            return
        going_on = [
            heat.numbers[i]
            for i in range(size // _FEEDERS)
            if heat.finished[i] and heat.numbers[i]
        ]
        parent = self._parent(heat)
        if parent is not None:
            _fill_free_seats(parent, going_on)
        if heat.stage + 2 == self.group.rounds:
            dropped = [
                heat.numbers[i]
                for i in range(size // _FEEDERS, size)
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
            big_final = self.stages[-1][0]
            if big_final.has_results:
                offset = sum(1 for taken in big_final.finished if taken)
            else:
                # The small final is usually ridden first. Counting the big final's
                # finishers would be zero then, and its riders would be shown as
                # first to fourth alongside the medals.
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


def parse_eliminator_groups(lines: list[str], sep: str = "#") -> list[EliminatorGroup]:
    """Read the ladders out of groups.txt, skipping lines that do not describe one."""
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


def group_problems(lines: list[str], sep: str = "#") -> list[str]:
    """Why a groups.txt line does not describe a ladder, for the run log."""
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


def _as_int(value: str) -> int:
    try:
        return int(str(value).strip())
    except TypeError, ValueError:
        return 0


def read_heat_results(lines: list[str], sep: str = "#") -> list[list[str]]:
    """results.txt in this mode: one line per heat, bibs in finishing order."""
    results: list[list[str]] = []
    for line in lines:
        bibs = [part.strip() for part in line.split(sep) if part.strip()]
        if bibs:
            results.append(bibs)
    return results


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


def build_brackets(
    groups: list[EliminatorGroup],
    start_list: list[StartProtocolElement],
    results: list[list[str]],
    log: list[str],
) -> list[EliminatorBracket]:
    """Build every ladder, seat the qualifiers and ride the results through it."""
    brackets = _one_ladder_per_group(groups, log)
    by_id = {bracket.group.group_id: bracket for bracket in brackets}
    for start in start_list:
        bracket = by_id.get(start.group_id)
        if bracket is None:
            continue
        place = start.start_place
        if not bracket.place_competitor(start.competitor_id, place, log):
            log.append(
                f"WARNING: {start.competitor_id} has qualification place {place}, "
                f"outside the ladder of group {start.group_id}"
            )
    for bracket in brackets:
        bracket.advance_byes()
    for order in results:
        if len(set(order)) != len(order):
            # One bib twice would place the same rider in two seats and push another
            # out of the heat entirely.
            log.append(
                "ERROR: heat result repeats a number and was ignored: "
                + ", ".join(order)
            )
            continue
        if not any(bracket.apply_result(order) for bracket in brackets):
            log.append("WARNING: no heat is waiting for the result " + ", ".join(order))
        for bracket in brackets:
            bracket.advance_byes()
    return brackets
