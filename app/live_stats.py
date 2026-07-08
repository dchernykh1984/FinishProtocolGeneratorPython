"""Build the per-competitor live-standings snapshot pushed to the site (Garmin field).

Each competitor gets an opaque string->string dict; the site stores it verbatim and the
watch maps known keys to fields (unknown/missing keys are ignored). To stay robust, each
value comes from lap-finish crossings only (the same ordering the printed protocol uses)
-- never from the intermediate control points, which controllers sometimes miss.

Keys (any subset, gated by the two config toggles):

* place_group / place_abs -- current position as a number, or "DSQ".
* qty_group / qty_abs -- bib-holders in the group / whole race (incl. DSQ/DNS/DNF).
* gap_prev_* / gap_next_* -- time to the neighbour one place ahead / behind, measured at
  the last lap-finish both completed ("+1:23"); omitted when it cannot be computed.
* laps -- "<done>/<total>" (e.g. "3/7").
"""

from __future__ import annotations

from collections import defaultdict

from app.config import RaceConfig
from app.models import INF, FinishProtocolElement


def _laps_done(fp: FinishProtocolElement, cfg: RaceConfig) -> int:
    return (
        fp.get_n_successful_tries() if cfg.is_number_of_tries() else fp.n_laps_finished
    )


def _total_laps(fp: FinishProtocolElement, cfg: RaceConfig) -> int:
    return fp.n_tries_for_result if cfg.is_number_of_tries() else fp.n_laps


def _elapsed_at_lap(
    fp: FinishProtocolElement, cfg: RaceConfig, laps_count: int
) -> float | None:
    """Elapsed time from this rider's start to the finish of lap laps_count, or None."""
    if laps_count <= 0:
        return None
    if cfg.is_number_of_tries():
        # Only defined at the rider's own successful-tries count (their total time).
        if laps_count == fp.get_n_successful_tries():
            total = fp.get_total_time()
            return total if total < INF else None
        return None
    if laps_count <= fp.n_laps_finished and (laps_count - 1) < len(fp.finish_lap_times):
        elapsed = fp.finish_lap_times[laps_count - 1]
        return elapsed if elapsed > 0 else None
    return None


def _format_gap(seconds: float) -> str:
    sign = "+" if seconds >= 0 else "-"
    total = round(abs(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{sign}{hours}:{minutes:02d}:{secs:02d}"
    return f"{sign}{minutes}:{secs:02d}"


def _gap(
    behind: FinishProtocolElement, ahead: FinishProtocolElement, cfg: RaceConfig
) -> str | None:
    """Time `behind` trails `ahead` at the last lap both finished (>=0), or None."""
    common = min(_laps_done(behind, cfg), _laps_done(ahead, cfg))
    e_behind = _elapsed_at_lap(behind, cfg, common)
    e_ahead = _elapsed_at_lap(ahead, cfg, common)
    if e_behind is None or e_ahead is None:
        return None
    return _format_gap(e_behind - e_ahead)


def _rank_scope(
    elements: list[FinishProtocolElement], cfg: RaceConfig
) -> dict[str, dict[str, str]]:
    """Rank one scope (whole race or one group), sorted best-first.

    Returns competitor_id -> {place, qty, gap_prev?, gap_next?}. DSQ riders get
    place "DSQ", excluded from the numbering and neighbour gaps; qty counts everyone.
    """
    ranked = [e for e in elements if not e.disqualified]
    qty = str(len(elements))
    out: dict[str, dict[str, str]] = {}
    for i, elem in enumerate(ranked):
        entry = {"place": str(i + 1), "qty": qty}
        if i > 0:
            gap = _gap(elem, ranked[i - 1], cfg)
            if gap is not None:
                entry["gap_prev"] = gap
        if i < len(ranked) - 1:
            gap = _gap(ranked[i + 1], elem, cfg)
            if gap is not None:
                entry["gap_next"] = gap
        out[elem.competitor_id] = entry
    for elem in elements:
        if elem.disqualified:
            out[elem.competitor_id] = {"place": "DSQ", "qty": qty}
    return out


def build_live_stats(  # noqa: C901
    sorted_proto: list[FinishProtocolElement], cfg: RaceConfig
) -> dict[str, dict[str, str]]:
    """Build bib -> {key: value} for the enabled scopes; empty when both toggles off."""
    if not (cfg.send_group_statistics or cfg.send_absolute_statistics):
        return {}

    abs_scope = _rank_scope(sorted_proto, cfg) if cfg.send_absolute_statistics else {}

    group_scope: dict[str, dict[str, str]] = {}
    if cfg.send_group_statistics:
        groups: dict[str, list[FinishProtocolElement]] = defaultdict(list)
        for elem in sorted_proto:
            groups[elem.group_id].append(elem)
        for members in groups.values():
            group_scope.update(_rank_scope(members, cfg))

    stats: dict[str, dict[str, str]] = {}
    for elem in sorted_proto:
        cid = elem.competitor_id
        data: dict[str, str] = {}
        if cfg.send_group_statistics and cid in group_scope:
            grp = group_scope[cid]
            data["place_group"] = grp["place"]
            data["qty_group"] = grp["qty"]
            if "gap_prev" in grp:
                data["gap_prev_group"] = grp["gap_prev"]
            if "gap_next" in grp:
                data["gap_next_group"] = grp["gap_next"]
        if cfg.send_absolute_statistics and cid in abs_scope:
            ab = abs_scope[cid]
            data["place_abs"] = ab["place"]
            data["qty_abs"] = ab["qty"]
            if "gap_prev" in ab:
                data["gap_prev_abs"] = ab["gap_prev"]
            if "gap_next" in ab:
                data["gap_next_abs"] = ab["gap_next"]
        data["laps"] = f"{_laps_done(elem, cfg)}/{_total_laps(elem, cfg)}"
        stats[cid] = data
    return stats
