"""Match independent attempt windows without renumbering incomplete attempts."""

from __future__ import annotations

import html

from app.config import RaceConfig
from app.models import INF, FinishCompetitorElement, FinishProtocolElement


def _marks(
    fp: FinishProtocolElement, stream: list[FinishCompetitorElement]
) -> list[FinishCompetitorElement]:
    # Duplicate timestamps cannot define separate starts or positive-duration splits.
    by_time: dict[float, FinishCompetitorElement] = {}
    for mark in stream:
        if fp.is_same_competitor(mark) and not mark.is_dsq:
            by_time.setdefault(mark.seconds, mark)
    return sorted(by_time.values(), key=lambda mark: mark.seconds)


def calculate_attempts(
    fp: FinishProtocolElement,
    finish_list: list[FinishCompetitorElement],
    remote_points: list[list[FinishCompetitorElement]],
    cfg: RaceConfig,
    log: list[str],
) -> None:
    marks = _marks(fp, finish_list)
    streams = [_marks(fp, stream) for stream in remote_points]
    starts = marks if streams else marks[::2]
    fp.attempt_mode = True
    fp.attempts_seen = min(len(starts), fp.n_laps)
    fp.cross_line_times[0] = starts[0].seconds if starts else INF
    cumulative = 0.0
    for index, start in enumerate(starts[: fp.n_laps]):
        end = starts[index + 1].seconds if index + 1 < len(starts) else INF
        fp.attempt_starts[index] = start.seconds
        fp.attempt_closed[index] = end < INF
        candidates = streams[-1] if streams else marks[2 * index + 1 : 2 * index + 2]
        finish = _find_finish(start.seconds, end, candidates, cfg, fp, index, log)
        if finish is not None:
            elapsed = finish.seconds - start.seconds
            elapsed += _penalties(
                fp, index, start.seconds, finish.seconds, remote_points
            )
            if cfg.time_limit > 0:
                elapsed = min(elapsed, cfg.time_limit)
            fp.lap_times[index] = elapsed
            fp.attempt_finishes[index] = finish.seconds
            fp.attempt_closed[index] = True
            fp.n_laps_finished += 1
            cumulative += elapsed
            if finish.action == "finish":
                fp.finished = True
        else:
            log.append(f"WARNING: {fp.competitor_id} attempt {index + 1} not finished")
        fp.finish_lap_times[index] = cumulative
        fp.cross_line_times[index + 1] = fp.cross_line_times[0] + cumulative
        if streams:
            _splits(fp, index, start.seconds, end, finish, streams[:-1])
    if fp.attempt_rules:
        fp.finished = cfg.disable_dnf or (
            fp.get_n_successful_tries() == fp.attempt_rules[0].attempts
        )
    elif fp.n_laps_finished == fp.n_laps:
        fp.finished = True


def _penalties(
    fp: FinishProtocolElement,
    index: int,
    start: float,
    finish: float,
    streams: list[list[FinishCompetitorElement]],
) -> float:
    # Timing duplicates are collapsed for matching, but judge decisions stay intact.
    penalties = [
        mark
        for stream in streams
        for mark in stream
        if not mark.is_dsq
        and fp.is_same_competitor(mark)
        and start <= mark.seconds <= finish
        and mark.penalty != 0
    ]
    fp.lap_penalty[index] = "".join(
        f"<BR>{html.escape(mark.action)}:{mark.penalty:g}sec" for mark in penalties
    )
    return sum(mark.penalty for mark in penalties)


def _find_finish(
    start: float,
    end: float,
    candidates: list[FinishCompetitorElement],
    cfg: RaceConfig,
    fp: FinishProtocolElement,
    index: int,
    log: list[str],
) -> FinishCompetitorElement | None:
    for mark in candidates:
        if not start < mark.seconds < end:
            continue
        if mark.seconds - start < cfg.minimal_time_for_lap:
            log.append(
                f"ERROR: {fp.competitor_id} attempt {index + 1} "
                "faster than minimal time"
            )
            continue
        return mark
    return None


def _splits(
    fp: FinishProtocolElement,
    index: int,
    start: float,
    end: float,
    finish: FinishCompetitorElement | None,
    streams: list[list[FinishCompetitorElement]],
) -> None:
    cp = fp.control_points[index]
    bound = finish.seconds if finish is not None else end
    previous = start
    for point, stream in enumerate(streams):
        mark = next((m for m in stream if previous < m.seconds < bound), None)
        if mark is None:
            continue
        cp.segment_crosses[point] = mark.seconds
        cp.segment_finishes[point] = mark.seconds - start
        previous_found = point == 0 or cp.segment_crosses[point - 1] != -1
        cp.segment_times[point] = mark.seconds - previous if previous_found else -2.0
        previous = mark.seconds
    if finish is not None and streams:
        point = len(streams)
        cp.segment_crosses[point] = finish.seconds
        cp.segment_finishes[point] = finish.seconds - start
        cp.segment_times[point] = (
            finish.seconds - previous if cp.segment_crosses[point - 1] != -1 else -2.0
        )
