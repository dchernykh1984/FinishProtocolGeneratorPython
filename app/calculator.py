"""Protocol calculation logic (calculateProtocol, sorting, etc.)."""

from __future__ import annotations

import time

from app.config import RaceConfig
from app.models import (
    INF,
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    StartProtocolElement,
)


def spiridonov(year_of_birth: str) -> float:
    """Spiridonov age-coefficient formula."""
    try:
        birth_year = float(year_of_birth.strip())
    except ValueError, AttributeError:
        return 1.0
    current_year = float(time.localtime().tm_year)
    age = current_year - birth_year
    return (0.02266 * age * age - 1.25437 * age + 117.37067) / 100.0


def _first_better(  # noqa: C901
    a: FinishProtocolElement,
    b: FinishProtocolElement,
    cfg: RaceConfig,
    n_points: int,
) -> bool:
    """Return True if result *a* beats result *b* (faithful port of C++ logic)."""
    if not a.disqualified and b.disqualified:
        return True
    if a.disqualified and not b.disqualified:
        return False
    if a.finished and not b.finished:
        return True
    if not a.finished and b.finished:
        return False

    if cfg.is_number_of_tries():
        if a.get_n_successful_tries() != b.get_n_successful_tries():
            return a.get_n_successful_tries() > b.get_n_successful_tries()
        return a.get_total_time() < b.get_total_time()

    if a.n_laps_finished != b.n_laps_finished:
        return a.n_laps_finished > b.n_laps_finished

    cp_a = 0
    cp_b = 0
    if a.n_laps_finished + 1 <= a.n_laps:
        for k in range(n_points):
            if a.control_points[a.n_laps_finished].segment_finishes[k] == -1:
                break
            cp_a = k + 1
    if b.n_laps_finished + 1 <= b.n_laps:
        for k in range(n_points):
            if b.control_points[b.n_laps_finished].segment_finishes[k] == -1:
                break
            cp_b = k + 1

    both_dns = (
        a.n_laps_finished == 0 and b.n_laps_finished == 0 and cp_a == 0 and cp_b == 0
    )
    if both_dns and a.start_delay != b.start_delay:
        return a.start_delay < b.start_delay

    if cfg.skip_first_lap_effective():
        if a.cross_line_times[0] == INF and b.cross_line_times[0] != INF:
            return False
        if a.cross_line_times[0] != INF and b.cross_line_times[0] == INF:
            return True

    if both_dns:
        try:
            ia, ib = int(a.competitor_id), int(b.competitor_id)
            if len(a.competitor_id) == len(b.competitor_id):
                return ia < ib
            return len(a.competitor_id) < len(b.competitor_id)
        except ValueError:
            if len(a.competitor_id) == len(b.competitor_id):
                return a.competitor_id < b.competitor_id
            return len(a.competitor_id) < len(b.competitor_id)

    if cp_a != cp_b:
        return cp_a > cp_b

    if cp_a == 0:
        return (
            a.finish_lap_times[a.n_laps_finished - 1]
            < b.finish_lap_times[b.n_laps_finished - 1]
        )

    prev_a = (
        0.0 if a.n_laps_finished == 0 else a.finish_lap_times[a.n_laps_finished - 1]
    )
    prev_b = (
        0.0 if b.n_laps_finished == 0 else b.finish_lap_times[b.n_laps_finished - 1]
    )
    seg_a = a.control_points[a.n_laps_finished].segment_finishes[cp_a - 1]
    seg_b = b.control_points[b.n_laps_finished].segment_finishes[cp_b - 1]
    return (prev_a + seg_a) < (prev_b + seg_b)


def generate_sorted_protocol(
    protocol: list[FinishProtocolElement],
    cfg: RaceConfig,
    n_points: int,
) -> list[FinishProtocolElement]:
    """Selection-sort protocol list (faithful port of C++ generateSortedProtocol)."""
    result: list[FinishProtocolElement] = []
    for _ in range(len(protocol)):
        best: FinishProtocolElement | None = None
        for elem in protocol:
            if not elem.sorted_flag:
                if best is None or _first_better(elem, best, cfg, n_points):
                    best = elem
        if best is not None:
            best.sorted_flag = True
            result.append(best)
    return result


def calculate_protocol(  # noqa: C901
    start_list: list[StartProtocolElement],
    group_list: list[GroupStartElement],
    finish_list: list[FinishCompetitorElement],
    remote_points: list[list[FinishCompetitorElement]],
    start_check_list: list[FinishCompetitorElement],
    cfg: RaceConfig,
    log: list[str],
) -> list[FinishProtocolElement]:
    """
    Build FinishProtocolElement list from raw input data.
    Faithful port of C++ calculateProtocol().
    """
    n_points = len(remote_points)
    result: list[FinishProtocolElement] = []

    for start in start_list:
        fp = FinishProtocolElement(start, cfg.disable_dnf, n_points)

        # --- set crossLineTimes[0] (start time) ---
        if cfg.skip_first_lap_effective():
            fp.cross_line_times[0] = INF
            for fe in finish_list:
                if fp.is_same_competitor(fe) and fe.seconds < fp.cross_line_times[0]:
                    fp.cross_line_times[0] = fe.seconds
        else:
            found = False
            for gs in group_list:
                if fp.group_id == gs.group_id:
                    fp.cross_line_times[0] = gs.seconds + fp.start_delay
                    found = True
                    break
            if not found:
                log.append(f"ERROR: group start time not found for {fp.competitor_id}")

        # --- start check list ---
        if cfg.use_start_check_list and start_check_list:
            passed = False
            for ck in start_check_list:
                if fp.is_same_competitor(ck):
                    if (
                        fp.cross_line_times[0] - cfg.start_registration_period
                        < ck.seconds
                    ):
                        passed = True
                    else:
                        log.append(
                            f"ERROR: {fp.competitor_id} passed registration too early"
                        )
            if not passed:
                log.append(f"ERROR: {fp.competitor_id} did not pass start registration")
                fp.disqualified = True

        # --- DSQ and finish marks ---
        for fe in finish_list:
            if fp.is_same_competitor(fe):
                if fe.action == "DSQ":
                    fp.disqualified = not cfg.disable_dsq
                if fe.action == "finish":
                    fp.finished = True

        # --- find all line crossings ---
        n_to_find = fp.n_laps * 2 if cfg.is_number_of_tries() else fp.n_laps + 1
        prev_cross = fp.cross_line_times[0]
        prev_lap_start = fp.cross_line_times[0]
        is_try_finish = True

        for lap in range(1, n_to_find):
            next_cross = INF
            next_crossed = False

            for fe in finish_list:
                if fe.action == "DSQ":
                    continue
                if not fp.is_same_competitor(fe):
                    continue
                if fe.seconds <= prev_cross:
                    continue
                if fe.seconds >= next_cross:
                    continue
                # minimal time check
                if (
                    cfg.minimal_time_for_lap > 0
                    and (is_try_finish or not cfg.is_number_of_tries())
                    and prev_cross > fe.seconds - cfg.minimal_time_for_lap
                ):
                    log.append(
                        f"ERROR: {fp.competitor_id} lap faster than minimal time"
                    )
                    continue
                # time limit check
                if (
                    not cfg.is_number_of_tries()
                    and cfg.time_limit > 0
                    and fp.cross_line_times[0] < fe.seconds - cfg.time_limit
                ):
                    log.append(f"ERROR: {fp.competitor_id} crossed after time limit")
                    continue
                next_cross = fe.seconds
                next_crossed = True
                if cfg.is_number_of_tries():
                    if is_try_finish:
                        idx = fp.n_laps_finished + 1
                        if idx < len(fp.cross_line_times):
                            fp.cross_line_times[idx] = (
                                fp.cross_line_times[fp.n_laps_finished]
                                + next_cross
                                - prev_cross
                            )
                else:
                    if lap < len(fp.cross_line_times):
                        fp.cross_line_times[lap] = fe.seconds
                    if fp.stages != 1:
                        try:
                            fp.lap_finish_numbers[lap - 1] = int(fe.competitor_id)
                        except ValueError:
                            pass

            if next_crossed:
                if not cfg.is_number_of_tries() or is_try_finish:
                    fp.n_laps_finished += 1
                    prev_lap_start = prev_cross

                if not cfg.is_number_of_tries() or not is_try_finish:
                    # apply penalties from remote points
                    for _pt_idx, pts in enumerate(remote_points):
                        for rem in pts:
                            if (
                                rem.competitor_id == fp.competitor_id
                                and rem.seconds >= prev_lap_start
                                and rem.seconds < next_cross
                            ):
                                idx = fp.n_laps_finished
                                if idx < len(fp.cross_line_times):
                                    fp.cross_line_times[idx] += rem.penalty
                                if fp.n_laps_finished > 0:
                                    lap_idx = fp.n_laps_finished - 1
                                    if lap_idx < len(fp.lap_penalty):
                                        fp.lap_penalty[lap_idx] += (
                                            f"<BR>{rem.action}:{int(rem.penalty)}sec"
                                        )
                    # time limit clamp
                    if cfg.time_limit > 0 and fp.n_laps_finished > 0:
                        idx = fp.n_laps_finished
                        prev_idx = fp.n_laps_finished - 1
                        limit = fp.cross_line_times[prev_idx] + cfg.time_limit
                        if (
                            idx < len(fp.cross_line_times)
                            and prev_idx >= 0
                            and fp.cross_line_times[idx] > limit
                        ):
                            fp.cross_line_times[idx] = limit

                is_try_finish = not is_try_finish
                prev_cross = next_cross
            else:
                if not fp.finished:
                    log.append(f"WARNING: lap {lap} not found for {fp.competitor_id}")
                break

        # --- penalties for isNumberOfTries last block ---
        if cfg.is_number_of_tries():
            for pts in remote_points:
                for rem in pts:
                    if (
                        rem.competitor_id == fp.competitor_id
                        and rem.seconds >= prev_lap_start
                    ):
                        idx = fp.n_laps_finished
                        if idx < len(fp.cross_line_times):
                            fp.cross_line_times[idx] += rem.penalty
            if cfg.time_limit > 0 and fp.n_laps_finished > 0:
                idx = fp.n_laps_finished
                prev_idx = fp.n_laps_finished - 1
                limit = fp.cross_line_times[prev_idx] + cfg.time_limit
                if idx < len(fp.cross_line_times) and fp.cross_line_times[idx] > limit:
                    fp.cross_line_times[idx] = limit

        # --- Spiridonov ---
        if cfg.use_spiridonov_coefficients():
            coeff = spiridonov(fp.year_of_birth)
            for i in range(fp.n_laps_finished + 1):
                if i < len(fp.cross_line_times):
                    fp.cross_line_times[i] /= coeff
            fp.extra_info = f"{coeff:.4f}"

        # --- compute lapTimes and finishLapTimes ---
        for lc in range(fp.n_laps_finished):
            fp.lap_times[lc] = fp.cross_line_times[lc + 1] - fp.cross_line_times[lc]
            fp.finish_lap_times[lc] = (
                fp.cross_line_times[lc + 1] - fp.cross_line_times[0]
            )

        # --- mark finished if all laps done ---
        if fp.n_laps_finished == fp.n_laps:
            fp.finished = True

        # --- control points (intermediate) ---
        for lc in range(min(fp.n_laps_finished + 1, fp.n_laps)):
            next_lap_t = (
                INF if lc == fp.n_laps_finished else fp.cross_line_times[lc + 1]
            )
            n_cp = len(remote_points)
            for cp_i, pts in enumerate(remote_points):
                prev_seg = (
                    fp.cross_line_times[lc]
                    if cp_i == 0
                    else (
                        fp.control_points[lc].segment_crosses[cp_i - 1]
                        if fp.control_points[lc].segment_crosses[cp_i - 1] != -1
                        else fp.cross_line_times[lc]
                    )
                )
                for rem in pts:
                    t = rem.seconds
                    if (
                        fp.is_same_competitor(rem)
                        and t > fp.cross_line_times[lc]
                        and t < next_lap_t
                        and fp.control_points[lc].segment_crosses[cp_i] == -1
                    ):
                        fp.control_points[lc].segment_crosses[cp_i] = t
                        fp.control_points[lc].segment_finishes[cp_i] = (
                            t - fp.cross_line_times[lc]
                        )
                        prev_found = cp_i == 0 or (
                            fp.control_points[lc].segment_crosses[cp_i - 1] != -1
                        )
                        fp.control_points[lc].segment_times[cp_i] = (
                            t - prev_seg if prev_found else -2.0
                        )
            # Last segment: last CP -> lap finish (only for completed laps)
            if n_cp > 0 and lc < fp.n_laps_finished:
                last_cross = fp.control_points[lc].segment_crosses[n_cp - 1]
                if last_cross != -1:
                    finish_t = fp.cross_line_times[lc + 1]
                    fp.control_points[lc].segment_crosses[n_cp] = finish_t
                    fp.control_points[lc].segment_times[n_cp] = finish_t - last_cross

        result.append(fp)
    return result


def check_start_protocol(  # noqa: C901
    protocol: list[FinishProtocolElement],
    finish_list: list[FinishCompetitorElement],
    start_list: list[StartProtocolElement],
    remote_points: list[list[FinishCompetitorElement]],
    cfg: RaceConfig,
    log: list[str],
) -> None:
    """Validate protocol and log warnings/errors."""
    for fe in finish_list:
        found = any(fp.is_same_competitor(fe) for fp in protocol)
        if not found:
            log.append(
                f"ERROR: competitor {fe.competitor_id} in results but not in start protocol"  # noqa: E501
            )

    ids = [sp.competitor_id for sp in start_list]
    for i, a in enumerate(ids):
        for b in ids[:i]:
            if a == b:
                log.append(f"ERROR: duplicate competitor ID {a} in start protocol")

    for j, pts in enumerate(remote_points):
        for rem in pts:
            found = any(fp.is_same_competitor(rem) for fp in protocol)
            if not found:
                log.append(
                    f"ERROR: competitor {rem.competitor_id} at control point {j + 1} "
                    "not in start protocol"
                )

    skip = cfg.skip_first_lap_effective()
    for fp in protocol:
        crossings = sum(1 for fe in finish_list if fp.is_same_competitor(fe))
        expected = fp.n_laps * (2 if cfg.is_number_of_tries() else 1) + (
            1 if skip else 0
        )
        if crossings > expected:
            log.append(
                f"ERROR: {fp.competitor_id} has {crossings} crossings, expected {expected}"  # noqa: E501
            )

    if cfg.check_laps_difference and cfg.laps_difference_pct > 0:
        threshold = cfg.laps_difference_pct / 100.0
        for fp in protocol:
            if fp.n_laps_finished < 2:
                continue
            lap_times = [
                fp.cross_line_times[i + 1] - fp.cross_line_times[i]
                for i in range(fp.n_laps_finished)
            ]
            avg = sum(lap_times) / len(lap_times)
            if avg <= 0:
                continue
            for i, lt in enumerate(lap_times):
                if lt > avg * (1.0 + threshold) or lt < avg / (1.0 + threshold):
                    log.append(
                        f"ERROR: {fp.competitor_id} lap {i + 1} time {lt:.1f}s "
                        f"deviates more than {cfg.laps_difference_pct}% from "
                        f"average {avg:.1f}s"
                    )
