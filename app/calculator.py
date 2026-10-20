"""Protocol calculation logic (calculateProtocol, sorting, etc.)."""

from __future__ import annotations

import time

from app.attempt_calculator import calculate_attempts
from app.attempt_rules import parse_attempt_rules
from app.config import RaceConfig
from app.models import (
    INF,
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    StartProtocolElement,
)


def _record_dsq_reason(
    fp: FinishProtocolElement, fe: FinishCompetitorElement, where: str
) -> None:
    """Append a "<where>: <reason>" entry for a DSQ mark that carried a reason.

    Bare ``DSQ`` marks (no reason) still disqualify but add nothing to the list, keeping
    the finish-time column unchanged for the legacy format. Duplicates are collapsed.
    """
    reason = fe.dsq_reason
    if not reason:
        return
    entry = f"{where}: {reason}"
    if entry not in fp.dsq_reasons:
        fp.dsq_reasons.append(entry)


def spiridonov(year_of_birth: str) -> float:
    """Spiridonov age-coefficient formula."""
    try:
        birth_year = float(year_of_birth.strip())
    except ValueError, AttributeError:
        return 1.0
    current_year = float(time.localtime().tm_year)
    age = current_year - birth_year
    return (0.02266 * age * age - 1.25437 * age + 117.37067) / 100.0


def _number_less(a_id: str, b_id: str) -> bool:
    """Ascending competitor-number order used as the lowest-priority tie-breaker.

    Both ids numeric -> compare as integers; otherwise compare as strings. So two
    otherwise-equal competitors always resolve to ascending number order rather than
    the arbitrary registration-file order.
    """
    try:
        return int(a_id) < int(b_id)
    except ValueError:
        return a_id < b_id


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
        if a.attempt_rules:
            for rule in a.attempt_rules:
                a_count, a_time = a.attempt_score(rule)
                b_count, b_time = b.attempt_score(rule)
                if a_count != b_count:
                    return a_count > b_count
                if a_time != b_time:
                    return a_time < b_time if rule.sort == "asc" else a_time > b_time
            return _number_less(a.competitor_id, b.competitor_id)
        if a.get_n_successful_tries() != b.get_n_successful_tries():
            return a.get_n_successful_tries() > b.get_n_successful_tries()
        if a.get_total_time() != b.get_total_time():
            return a.get_total_time() < b.get_total_time()
        return _number_less(a.competitor_id, b.competitor_id)

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

    if cfg.skip_first_lap_effective():
        if a.cross_line_times[0] == INF and b.cross_line_times[0] != INF:
            return False
        if a.cross_line_times[0] != INF and b.cross_line_times[0] == INF:
            return True
    elif both_dns:
        # DNF vs DNS must take priority over start_delay and number ordering.
        # cross_line_times[0] == 0 means group was never found (DNS).
        a_started = a.cross_line_times[0] != 0
        b_started = b.cross_line_times[0] != 0
        if a_started and not b_started:
            return True
        if not a_started and b_started:
            return False

    if both_dns and a.start_delay != b.start_delay:
        return a.start_delay < b.start_delay

    if both_dns:
        return _number_less(a.competitor_id, b.competitor_id)

    if cp_a != cp_b:
        return cp_a > cp_b

    if cp_a == 0:
        fin_a = a.finish_lap_times[a.n_laps_finished - 1]
        fin_b = b.finish_lap_times[b.n_laps_finished - 1]
        if fin_a != fin_b:
            return fin_a < fin_b
        return _number_less(a.competitor_id, b.competitor_id)

    prev_a = (
        0.0 if a.n_laps_finished == 0 else a.finish_lap_times[a.n_laps_finished - 1]
    )
    prev_b = (
        0.0 if b.n_laps_finished == 0 else b.finish_lap_times[b.n_laps_finished - 1]
    )
    seg_a = a.control_points[a.n_laps_finished].segment_finishes[cp_a - 1]
    seg_b = b.control_points[b.n_laps_finished].segment_finishes[cp_b - 1]
    total_a = prev_a + seg_a
    total_b = prev_b + seg_b
    if total_a != total_b:
        return total_a < total_b
    return _number_less(a.competitor_id, b.competitor_id)


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
    n_points = len(remote_points) - (
        1 if cfg.is_number_of_tries() and remote_points else 0
    )
    result: list[FinishProtocolElement] = []
    rules = (
        parse_attempt_rules(cfg.attempt_rules_json) if cfg.is_number_of_tries() else ()
    )
    if cfg.is_number_of_tries() and cfg.n_remote_points != len(remote_points):
        raise ValueError(
            "Number of Tries requires every configured control-point stream."
        )

    if cfg.use_spiridonov_coefficients() and n_points > 0:
        log.append(
            "WARNING: Spiridonov with control points: split times will be incorrect"
        )

    for start in start_list:
        fp = FinishProtocolElement(start, cfg.disable_dnf, n_points)
        fp.attempt_rules = rules
        if rules:
            fp.n_tries_for_result = rules[0].attempts

        if cfg.is_number_of_tries() and not rules and not fp._attempts_string_valid:
            log.append(
                f"ERROR: {fp.competitor_id} invalid NumberOfTries format: "
                f"{fp.extra_info!r}"
            )
            fp.n_tries_for_result = 0

        # --- set crossLineTimes[0] (start time) ---
        if cfg.skip_first_lap_effective():
            fp.cross_line_times[0] = INF
            for fe in finish_list:
                if (
                    fp.is_same_competitor(fe)
                    and not fe.is_dsq
                    and fe.seconds < fp.cross_line_times[0]
                ):
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
        _finish_count = 0
        for fe in finish_list:
            if fp.is_same_competitor(fe):
                if fe.is_dsq:
                    fp.disqualified = not cfg.disable_dsq
                    _record_dsq_reason(fp, fe, "finish")
                if fe.action == "finish" and not cfg.is_number_of_tries():
                    _finish_count += 1
                    if _finish_count > 1:
                        log.append(
                            f"WARNING: {fp.competitor_id} has multiple finish marks"
                        )
                    fp.finished = True

        # A control point can also disqualify (its device uploads DSQ marks to that
        # point's stream); collect those with a "CP <n>" location for the reason list.
        for pt_idx, pts in enumerate(remote_points):
            for rem in pts:
                if rem.is_dsq and fp.is_same_competitor(rem):
                    fp.disqualified = not cfg.disable_dsq
                    _record_dsq_reason(fp, rem, f"CP {pt_idx + 1}")

        if cfg.is_number_of_tries():
            calculate_attempts(fp, finish_list, remote_points, cfg, log)
            result.append(fp)
            continue

        # Log finish events that occur before this competitor's start time
        if 0.0 < fp.cross_line_times[0] < INF:
            for fe in finish_list:
                if (
                    fp.is_same_competitor(fe)
                    and not fe.is_dsq
                    and fe.seconds < fp.cross_line_times[0]
                ):
                    log.append(
                        f"WARNING: {fp.competitor_id} crossing at {fe.seconds:.3f}s "
                        f"before start {fp.cross_line_times[0]:.3f}s"
                    )

        # --- find all line crossings ---
        prev_cross = fp.cross_line_times[0]
        for lap in range(1, fp.n_laps + 1):
            next_cross = INF
            for fe in finish_list:
                if fe.is_dsq or not fp.is_same_competitor(fe):
                    continue
                if not prev_cross < fe.seconds < next_cross:
                    continue
                if (
                    cfg.minimal_time_for_lap > 0
                    and prev_cross > fe.seconds - cfg.minimal_time_for_lap
                ):
                    log.append(
                        f"ERROR: {fp.competitor_id} lap faster than minimal time"
                    )
                    continue
                if (
                    cfg.time_limit > 0
                    and fp.cross_line_times[0] < fe.seconds - cfg.time_limit
                ):
                    log.append(f"ERROR: {fp.competitor_id} crossed after time limit")
                    continue
                next_cross = fe.seconds
                fp.cross_line_times[lap] = fe.seconds
                if fp.stages != 1:
                    try:
                        fp.lap_finish_numbers[lap - 1] = int(fe.competitor_id)
                    except ValueError:
                        pass
            if next_cross == INF:
                if not fp.finished:
                    log.append(f"WARNING: lap {lap} not found for {fp.competitor_id}")
                break
            fp.n_laps_finished += 1
            for pts in remote_points:
                for rem in pts:
                    if rem.is_dsq:
                        continue
                    if (
                        rem.competitor_id == fp.competitor_id
                        and prev_cross <= rem.seconds < next_cross
                    ):
                        fp.cross_line_times[fp.n_laps_finished] += rem.penalty
                        fp.lap_penalty[fp.n_laps_finished - 1] += (
                            f"<BR>{rem.action}:{int(rem.penalty)}sec"
                        )
            if cfg.time_limit > 0:
                index = fp.n_laps_finished
                fp.cross_line_times[index] = min(
                    fp.cross_line_times[index],
                    fp.cross_line_times[index - 1] + cfg.time_limit,
                )
            prev_cross = next_cross

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
                    if rem.is_dsq:
                        continue
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

    for fp in protocol:
        crossings = sum(
            1 for fe in finish_list if fp.is_same_competitor(fe) and not fe.is_dsq
        )
        if cfg.is_number_of_tries():
            expected = fp.n_laps if remote_points else fp.n_laps * 2
        else:
            expected = fp.n_laps + (1 if cfg.skip_first_lap_effective() else 0)
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
                fp.lap_times[i] for i in range(fp.n_laps) if fp.lap_completed(i)
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
