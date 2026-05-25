"""Data models for finish protocol generator."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

INF: float = math.inf


def parse_time_string(s: str) -> float:
    """Parse 'D H:M:S.fff' time string to float seconds since epoch."""
    s = s.strip()
    if not s or s == "0":
        return 0.0
    parts = s.split(" ", 1)
    days = int(parts[0]) if len(parts) > 1 else 0
    rest = parts[1] if len(parts) > 1 else parts[0]
    colon = rest.split(":")
    h = int(colon[0])
    m = int(colon[1])
    sec_str = colon[2] if len(colon) > 2 else "0"
    if "." in sec_str:
        s_int, frac_s = sec_str.split(".", 1)
        secs = int(s_int)
        frac = int(frac_s) / (10 ** len(frac_s))
    else:
        secs = int(sec_str)
        frac = 0.0
    return days * 86400.0 + h * 3600.0 + m * 60.0 + secs + frac


def get_field(line: str, idx: int, sep: str = "#") -> str:
    """Return the idx-th token from a sep-delimited string."""
    parts = line.split(sep)
    return parts[idx] if idx < len(parts) else ""


def to_int(s: str) -> int:
    try:
        return int(s.strip())
    except ValueError, AttributeError:
        return 0


@dataclass
class IntermediateCrosses:
    """Control-point data for one lap."""

    n: int
    segment_crosses: list[float] = field(default_factory=list)
    segment_finishes: list[float] = field(default_factory=list)
    segment_times: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.segment_crosses = [-1.0] * self.n
        self.segment_finishes = [-1.0] * self.n
        self.segment_times = [-1.0] * self.n


@dataclass
class StartProtocolElement:
    competitor_id: str
    name: str
    group_id: str
    n_laps: int
    stages: int
    year_of_birth: str
    team: str
    city: str
    extra_info: str
    start_delay: float
    number: int = 0

    @classmethod
    def from_line(
        cls,
        line: str,
        sep: str = "#",
        skip_first_lap: bool = False,
    ) -> StartProtocolElement:
        f = lambda i: get_field(line, i, sep)  # noqa: E731
        n_laps = to_int(f(3)) or 1
        try:
            number = int(f(0))
        except ValueError:
            number = 0
        return cls(
            competitor_id=f(0),
            name=f(1),
            group_id=f(2),
            n_laps=n_laps,
            stages=to_int(f(4)) or 1,
            year_of_birth=f(5),
            team=f(6),
            city=f(7),
            extra_info=f(8),
            start_delay=parse_time_string(f(9)) if f(9) else 0.0,
            number=number,
        )


@dataclass
class FinishCompetitorElement:
    competitor_id: str
    seconds: float
    action: str
    penalty: float = 0.0

    @classmethod
    def from_line(cls, line: str, sep: str = "#") -> FinishCompetitorElement:
        f = lambda i: get_field(line, i, sep)  # noqa: E731
        action = f(2)
        try:
            penalty = float(f(3))
        except ValueError, IndexError:
            penalty = 0.0
        return cls(
            competitor_id=f(0),
            seconds=parse_time_string(f(1)) if f(1) else 0.0,
            action=action,
            penalty=penalty,
        )


@dataclass
class GroupStartElement:
    group_id: str
    seconds: float
    place: int = 1

    @classmethod
    def from_line(cls, line: str, sep: str = "#") -> GroupStartElement:
        f = lambda i: get_field(line, i, sep)  # noqa: E731
        return cls(
            group_id=f(0),
            seconds=parse_time_string(f(1)) if f(1) else 0.0,
        )


class FinishProtocolElement:
    """Full race result for one competitor (built from a StartProtocolElement)."""

    def __init__(
        self,
        start: StartProtocolElement,
        disable_dnf: bool,
        n_points: int,
    ) -> None:
        self.competitor_id = start.competitor_id
        self.name = start.name
        self.group_id = start.group_id
        self.n_laps = start.n_laps
        self.stages = start.stages
        self.year_of_birth = start.year_of_birth
        self.team = start.team
        self.city = start.city
        self.extra_info = start.extra_info
        self.start_delay = start.start_delay
        self.number = start.number

        self.finished: bool = disable_dnf
        self.disqualified: bool = False
        self.sorted_flag: bool = False
        self.n_laps_finished: int = 0

        # NumberOfTries: extra_info may encode "N:a1,a2,...,ak"
        _m = re.match(r"^(\d+):", str(start.extra_info))
        self.n_tries_for_result: int = int(_m.group(1)) if _m else start.n_laps
        _m2 = re.match(r"^\d+:(.+)$", str(start.extra_info))
        self._attempt_indices: list[int] = (
            [int(x) - 1 for x in _m2.group(1).split(",") if x.strip()] if _m2 else []
        )

        sz = start.n_laps + 2
        self.cross_line_times: list[float] = [0.0] * sz
        self.lap_times: list[float] = [0.0] * sz
        self.finish_lap_times: list[float] = [0.0] * sz
        self.lap_penalty: list[str] = [""] * sz
        self.lap_finish_numbers: list[int] = [-1] * sz
        # n_points+1 slots: segments start->CP1, CP1->CP2, ..., last_CP->finish
        self.control_points: list[IntermediateCrosses] = [
            IntermediateCrosses(n_points + 1) for _ in range(start.n_laps + 1)
        ]

    def is_same_competitor(self, elem: FinishCompetitorElement) -> bool:
        if self.competitor_id == elem.competitor_id:
            return True
        if self.stages != 1:
            for i in range(self.stages):
                if str(self.number + i) == elem.competitor_id:
                    return True
        return False

    def get_total_time(self, _with_penalties: bool = True) -> float:
        if self.n_laps_finished == 0:
            return INF
        if self.n_laps_finished <= self.n_tries_for_result:
            return self.finish_lap_times[self.n_laps_finished - 1]
        # NumberOfTries: pick best N from specific attempt indices or all laps
        if self._attempt_indices:
            times = [
                self.lap_times[i]
                for i in self._attempt_indices
                if 0 <= i < self.n_laps_finished and self.lap_times[i] > 0
            ]
        else:
            times = [t for t in self.lap_times[: self.n_laps_finished] if t > 0]
        return sum(sorted(times)[: self.n_tries_for_result])

    def get_n_successful_tries(self, _with_penalties: bool = True) -> int:
        return min(self.n_laps_finished, self.n_tries_for_result)

    def get_time_diff(
        self, leader: FinishProtocolElement, with_penalties: bool = True
    ) -> float:
        return self.get_total_time(with_penalties) - leader.get_total_time(
            with_penalties
        )
