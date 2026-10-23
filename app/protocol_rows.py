"""What a protocol says about each competitor, worked out once for every view of it.

The HTML writer, the structured document sent to the website and the live statistics all
show the same race. Everything they share -- who is printed, the place or status, the
result and its gap, a lap or attempt cell, a split, the lap ranks, the place within a
group -- is computed here, without changing the competitors, so each consumer gets the
same answer however many of them run and in whatever order.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field

from app.config import RaceConfig
from app.models import INF, FinishProtocolElement, GroupStartElement


def format_time(t: float, n_signs: int, write_date: bool = False) -> str:
    """Format a float seconds value the same way as C++ writeTimeByDouble."""
    if t > 356.0 * 24 * 3600 and not write_date:
        return "UNKNOWN"
    neg = t < 0
    if neg:
        t = -t

    n_signs = min(n_signs, 4)
    factor = 10**n_signs
    t_rounded = round(t * factor)
    frac = int(t_rounded % factor)
    t_int = int(t_rounded // factor)
    seconds = t_int % 60
    t_int //= 60
    minutes = t_int % 60
    t_int //= 60
    hours = t_int % 24
    t_int //= 24
    days = t_int

    out = "-" if neg else ""
    if days != 0:
        if write_date:
            year, month, day = 1970, 1, days + 1
            while True:
                dim = calendar.monthrange(year, month)[1]
                if day <= dim:
                    break
                day -= dim
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            out += f"{year}-{month:02d}-{day:02d} "
        else:
            out += f"{days} {'day' if days == 1 else 'days'} "
    out += f"{hours:02d}:{minutes:02d}:"
    if n_signs > 0:
        frac_str = str(frac).zfill(n_signs)
        out += f"{seconds:02d}.{frac_str}"
    else:
        out += f"{seconds:02d}"
    return out


def prepare_statuses(protocol: list[FinishProtocolElement], cfg: RaceConfig) -> None:
    """Settle who finished before anything shows the protocol.

    A competitor whose start was never seen has not finished, unless DNF is disabled.
    This is the one change made to the competitors, done here once for every consumer:
    the writers, the document and the live statistics then read the same statuses. It
    is idempotent, so each of them may call it.
    """
    if cfg.disable_dnf:
        return
    for fp in protocol:
        if not fp.has_started():
            fp.finished = False


def is_printed(fp: FinishProtocolElement, cfg: RaceConfig) -> bool:
    """Whether the competitor appears in the protocol at all (the print_* settings)."""
    return bool(
        (fp.finished or cfg.print_dnf)
        and (
            fp.n_laps_finished != 0
            or cfg.print_dns
            or (cfg.print_dnf and fp.has_started())
        )
        and (not fp.disqualified or cfg.print_dsq)
    )


def place_status(
    fp: FinishProtocolElement, place: int, cfg: RaceConfig
) -> tuple[str, str]:
    """(what the place column says, the competitor's status: ok, dnf, dns or dsq)."""
    if fp.disqualified:
        return "DSQ", "dsq"
    if not fp.finished:
        if fp.has_started() or (
            cfg.skip_first_lap_effective() and fp.cross_line_times[0] != INF
        ):
            return "DNF", "dnf"
        return "DNS", "dns"
    return str(place), "ok"


def group_places(
    protocol: list[FinishProtocolElement],
    group_list: list[GroupStartElement],
    cfg: RaceConfig,
) -> dict[int, int]:
    """Each printed finisher's place within their group, in protocol order (by id())."""
    counters = {g.group_id: g.place for g in reversed(group_list)}
    places: dict[int, int] = {}
    for fp in protocol:
        if not is_printed(fp, cfg) or fp.group_id not in counters:
            continue
        if not fp.disqualified and fp.finished:
            places[id(fp)] = counters[fp.group_id]
            counters[fp.group_id] += 1
    return places


@dataclass
class ResultParts:
    """The result column: the time, its gap to the leader, the laps or attempts."""

    time: str = ""
    gap: str = ""
    count: str = ""


def result_parts(
    fp: FinishProtocolElement,
    leader: FinishProtocolElement | None,
    cfg: RaceConfig,
) -> ResultParts:
    """The result of a finisher measured against the leader of their table."""
    parts = ResultParts()
    if not (fp.finished and not fp.disqualified) or leader is None:
        return parts
    tries = cfg.is_number_of_tries()
    if tries:
        last_t = fp.get_total_time()
        last_leader_t = leader.get_total_time()
    else:
        n = fp.n_laps_finished
        last_t = fp.finish_lap_times[n - 1] if n > 0 else 0.0
        last_leader_t = (
            leader.finish_lap_times[n - 1] if 0 < n <= leader.n_laps_finished else 0.0
        )
    if last_t <= 0:
        return parts
    parts.time = format_time(last_t, cfg.n_signs_after_point)
    if cfg.show_time_difference:
        diff = fp.get_time_diff(leader) if tries else last_t - last_leader_t
        sign = "+" if diff > 0 else ""
        parts.gap = f"({sign}{format_time(diff, cfg.n_signs_after_point)})"
    if cfg.show_n_finished_laps:
        shown = fp.get_n_successful_tries() if tries else fp.n_laps_finished
        parts.count = f"({shown})"
    return parts


@dataclass
class LapParts:
    """One lap or attempt cell: what it says and what goes with it."""

    state: str = "empty"  # done | running | empty
    text: str = ""
    strong: bool = False
    penalties: list[str] = field(default_factory=list)
    finish_number: str = ""
    finish_time: str = ""


def lap_parts(fp: FinishProtocolElement, lc: int, cfg: RaceConfig) -> LapParts:
    """A lap (or, in Number of Tries, an attempt) as the protocol shows it."""
    if fp.lap_completed(lc):
        parts = LapParts(state="done")
        parts.text = format_time(fp.lap_times[lc], cfg.n_signs_after_point)
        if cfg.is_number_of_tries():
            parts.strong = lc in fp.counted_attempts()
            parts.penalties = list(fp.lap_penalty_texts[lc])
        if fp.stages != 1 and fp.lap_finish_numbers[lc] != -1:
            parts.finish_number = f"({fp.lap_finish_numbers[lc]})"
        if cfg.show_lap_finish:
            parts.finish_time = (
                f"({format_time(fp.finish_lap_times[lc], cfg.n_signs_after_point)})"
            )
        return parts
    if fp.lap_started(lc):
        crossed = lc < len(fp.control_points) and any(
            v != -1 for v in fp.control_points[lc].segment_crosses
        )
        if fp.attempt_mode and fp.attempt_closed[lc]:
            return LapParts(state="running", text="DNF")
        return LapParts(state="running", text="UNKNOWN" if crossed else "")
    return LapParts()


def split_text(fp: FinishProtocolElement, lc: int, cp_i: int, cfg: RaceConfig) -> str:
    """One control-point segment of a lap: its time, ERR, UNKNOWN or nothing."""
    in_progress = fp.lap_started(lc) and not fp.lap_completed(lc)
    if not ((fp.lap_completed(lc) or in_progress) and lc < len(fp.control_points)):
        return ""
    crosses = fp.control_points[lc]
    if crosses.segment_crosses[cp_i] != -1:
        value = crosses.segment_times[cp_i]
        return "ERR" if value == -2.0 else format_time(value, cfg.n_signs_after_point)
    if fp.lap_completed(lc) or any(v != -1 for v in crosses.segment_crosses):
        return "UNKNOWN"
    return ""


@dataclass
class LapRanks:
    gap_lap: float
    place_lap: int
    gap_finish: float
    place_finish: int


def lap_ranks(
    fp: FinishProtocolElement, j: int, peers: list[FinishProtocolElement]
) -> LapRanks | None:
    """How a completed lap compares with the same lap of the others in the table."""
    if not fp.lap_completed(j):
        return None
    best_lap = fp.lap_times[j]
    place_lap = 1
    best_finish = fp.finish_lap_times[j]
    place_finish = 1
    for other in peers:
        if not other.lap_completed(j):
            continue
        if other.lap_times[j] < fp.lap_times[j]:
            place_lap += 1
            best_lap = min(best_lap, other.lap_times[j])
        if other.finish_lap_times[j] < fp.finish_lap_times[j]:
            place_finish += 1
            best_finish = min(best_finish, other.finish_lap_times[j])
    return LapRanks(
        fp.lap_times[j] - best_lap,
        place_lap,
        fp.finish_lap_times[j] - best_finish,
        place_finish,
    )


def time_shift_text(fp: FinishProtocolElement, cfg: RaceConfig) -> str:
    """The start column: the first crossing (with its date) or the start delay."""
    if cfg.skip_first_lap_effective():
        if fp.cross_line_times[0] == INF:
            return "NOT STARTED"
        return format_time(
            fp.cross_line_times[0], cfg.n_signs_after_point, write_date=True
        )
    return format_time(fp.start_delay, cfg.n_signs_after_point)


def laps_to_show(
    protocol: list[FinishProtocolElement],
    group_id: str | None,
    cfg: RaceConfig,
    n_points: int,
) -> tuple[int, bool]:
    """(how many lap columns a table has, whether it shows laps at all).

    ``group_id`` None is the absolute table, with every competitor.
    """
    members = [fp for fp in protocol if group_id is None or fp.group_id == group_id]
    columns = configured = 0
    if cfg.hide_empty_columns:
        for fp in members:
            columns = max(columns, fp.visible_laps())
            configured = max(configured, fp.n_laps)
            if group_id is not None and n_points > 0 and fp.n_laps_finished < fp.n_laps:
                lp = fp.n_laps_finished
                if lp < len(fp.control_points) and any(
                    v != -1 for v in fp.control_points[lp].segment_crosses
                ):
                    columns = max(columns, lp + 1)
    elif group_id is None:
        columns = configured = max((fp.n_laps for fp in members), default=0)
    else:
        first = next((fp for fp in members if fp.n_laps > 0), None)
        columns = configured = first.n_laps if first else 0
    multi_lap = (
        configured > 1
        or not cfg.show_finish_time
        or (n_points > 0 and cfg.show_lap_times)
    )
    return columns, multi_lap
