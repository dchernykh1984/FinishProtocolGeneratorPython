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
* gap_leader_* -- time behind the scope leader ("+2:05"); omitted for the leader.
* gap_prev_*_delta / gap_next_*_delta / gap_leader_*_delta -- how the prev/next/leader
  gap changed over the last lap ("+" grew, "-" shrank); needs 2 laps, else absent.
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


def _gap_value(
    behind: FinishProtocolElement,
    ahead: FinishProtocolElement,
    cfg: RaceConfig,
    lap: int,
) -> float | None:
    """Signed seconds `behind` trails `ahead` at the finish of `lap` (>=0), or None."""
    e_behind = _elapsed_at_lap(behind, cfg, lap)
    e_ahead = _elapsed_at_lap(ahead, cfg, lap)
    if e_behind is None or e_ahead is None:
        return None
    return e_behind - e_ahead


def _gap_and_delta(
    behind: FinishProtocolElement, ahead: FinishProtocolElement, cfg: RaceConfig
) -> tuple[str | None, str | None]:
    """Formatted gap at the last common lap, and how it changed over the last lap.

    The delta is the gap now minus the gap one lap earlier: "+" = the gap grew, "-" = it
    shrank (caught up). It needs at least two common laps, else it is None.
    """
    common = min(_laps_done(behind, cfg), _laps_done(ahead, cfg))
    now = _gap_value(behind, ahead, cfg, common)
    if now is None:
        return None, None
    delta = None
    if common >= 2:
        prev = _gap_value(behind, ahead, cfg, common - 1)
        if prev is not None:
            delta = _format_gap(now - prev)
    return _format_gap(now), delta


def _rank_scope(  # noqa: C901
    elements: list[FinishProtocolElement], cfg: RaceConfig
) -> dict[str, dict[str, str]]:
    """Rank one scope (whole race or one group), sorted best-first.

    Returns competitor_id -> entry. Non-DSQ riders get place (number), qty, and any of
    gap_prev/gap_next (neighbours), gap_leader (scope winner), and gap_prev_delta/
    gap_next_delta/gap_leader_delta (per-lap change of those gaps). DSQ riders get place
    "DSQ" only, excluded from the numbering and gaps. qty counts everyone.
    """
    ranked = [e for e in elements if not e.disqualified]
    qty = str(len(elements))
    out: dict[str, dict[str, str]] = {}
    for i, elem in enumerate(ranked):
        entry = {"place": str(i + 1), "qty": qty}
        if i > 0:
            gap, delta = _gap_and_delta(elem, ranked[i - 1], cfg)
            if gap is not None:
                entry["gap_prev"] = gap
            if delta is not None:
                entry["gap_prev_delta"] = delta
            leader_gap, leader_delta = _gap_and_delta(elem, ranked[0], cfg)
            if leader_gap is not None:
                entry["gap_leader"] = leader_gap
            if leader_delta is not None:
                entry["gap_leader_delta"] = leader_delta
        if i < len(ranked) - 1:
            gap, delta = _gap_and_delta(ranked[i + 1], elem, cfg)
            if gap is not None:
                entry["gap_next"] = gap
            if delta is not None:
                entry["gap_next_delta"] = delta
        out[elem.competitor_id] = entry
    for elem in elements:
        if elem.disqualified:
            out[elem.competitor_id] = {"place": "DSQ", "qty": qty}
    return out


# scope-entry key -> output key template ("{s}" is the scope suffix, "_group" or "_abs")
_GAP_KEY_TEMPLATES = {
    "gap_prev": "gap_prev{s}",
    "gap_next": "gap_next{s}",
    "gap_leader": "gap_leader{s}",
    "gap_prev_delta": "gap_prev{s}_delta",
    "gap_next_delta": "gap_next{s}_delta",
    "gap_leader_delta": "gap_leader{s}_delta",
}


def _emit_scope(entry: dict[str, str], suffix: str, data: dict[str, str]) -> None:
    """Copy one scope's entry into `data` with the `_group` / `_abs` suffix applied."""
    data[f"place{suffix}"] = entry["place"]
    data[f"qty{suffix}"] = entry["qty"]
    for base, template in _GAP_KEY_TEMPLATES.items():
        if base in entry:
            data[template.format(s=suffix)] = entry[base]


def build_live_stats(
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
            _emit_scope(group_scope[cid], "_group", data)
        if cfg.send_absolute_statistics and cid in abs_scope:
            _emit_scope(abs_scope[cid], "_abs", data)
        data["laps"] = f"{_laps_done(elem, cfg)}/{_total_laps(elem, cfg)}"
        stats[cid] = data
    return stats
