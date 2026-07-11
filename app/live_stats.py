"""Build the per-competitor live-standings snapshot pushed to the site (Garmin field).

Each competitor gets an opaque string->string dict; the site stores it verbatim and the
watch maps known keys to fields (unknown/missing keys are ignored). Every value -- the
place included -- comes from lap-finish crossings only: a control-point timekeeper who
misses a mark must never move a place or a gap. Deliberate judge decisions made at a
control point still count, since they do not need a crossing to be seen: a time penalty
is already folded into the lap-finish times, and a DSQ mark disqualifies the rider.

Keys (any subset, gated by the two config toggles):

* place_group / place_abs -- current position as a number, or "DSQ".
* qty_group / qty_abs -- bib-holders in the group / whole race (incl. DSQ/DNS/DNF).
* gap_prev_* / gap_next_* -- time to the neighbour one place ahead / behind, measured at
  the last lap-finish both completed. Signed from the reader's point of view: a rider
  ahead of them is positive ("+1:23"), a rider behind them negative ("-1:23"). Omitted
  when it cannot be computed.
* gap_leader_* -- time behind the scope leader ("+2:05"); omitted for the leader.
* gap_prev_*_delta / gap_next_*_delta / gap_leader_*_delta -- how the prev/next/leader
  gap changed over the last lap ("+" grew, "-" shrank); needs 2 laps, else absent.

Gaps render as "M:SS" (or "H:MM:SS" past an hour), with the same number of decimal
seconds as the generator's "Digits after decimal" setting: 0 -> "+0:36", 1 -> "+0:36.1".
* laps -- "<done>/<total>" (e.g. "3/7").
"""

from __future__ import annotations

from collections import defaultdict
from functools import cmp_to_key

from app.calculator import _first_better
from app.config import RaceConfig
from app.models import INF, FinishProtocolElement


def _rank_finish_only(
    protocol: list[FinishProtocolElement], cfg: RaceConfig
) -> list[FinishProtocolElement]:
    """Order competitors best-first from lap-finish data only, never control points.

    Reuses the protocol's own comparator with n_points=0: that makes its control-point
    tiebreak unreachable (both riders score 0 passed points), so the order falls back to
    completed laps and lap-finish times. A missed control-point mark therefore cannot
    move a rider's place. Judge decisions at a control point still count -- they are
    already baked into what the comparator reads: a time penalty was added to the
    lap-finish times, and a DSQ mark set `disqualified` (sorted last, shown as "DSQ").

    Sorts a copy, so the printed protocol's own ordering is untouched.
    """

    def _cmp(a: FinishProtocolElement, b: FinishProtocolElement) -> int:
        if _first_better(a, b, cfg, 0):
            return -1
        if _first_better(b, a, cfg, 0):
            return 1
        return 0

    return sorted(protocol, key=cmp_to_key(_cmp))


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


def _format_gap(seconds: float, n_signs: int) -> str:
    """Signed "M:SS" / "H:MM:SS", with `n_signs` decimals of seconds like the protocol.

    `n_signs` mirrors the generator's "Digits after decimal" setting (capped at 4, as in
    the protocol): a gap prints as "+0:36" when it is 0 and "+0:36.1" when it is 1.
    """
    sign = "+" if seconds >= 0 else "-"
    n_signs = min(max(n_signs, 0), 4)
    factor = 10**n_signs
    total = round(abs(seconds) * factor)
    frac = total % factor
    whole = total // factor
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    body = f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
    if n_signs > 0:
        body += f".{str(frac).zfill(n_signs)}"
    return f"{sign}{body}"


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
    behind: FinishProtocolElement,
    ahead: FinishProtocolElement,
    cfg: RaceConfig,
    sign: int = 1,
) -> tuple[str | None, str | None]:
    """Formatted gap at the last common lap, and how it changed over the last lap.

    `sign` orients the reported gap from the reader's point of view: a rider ahead of
    them reads "+1:23", a rider behind them "-1:23". The delta keeps its own meaning
    regardless of `sign` -- it is the gap now minus the gap one lap earlier, so "+" =
    the gap grew, "-" = it shrank (caught up). It needs at least two common laps, else
    it is None.
    """
    n_signs = cfg.n_signs_after_point
    common = min(_laps_done(behind, cfg), _laps_done(ahead, cfg))
    now = _gap_value(behind, ahead, cfg, common)
    if now is None:
        return None, None
    delta = None
    if common >= 2:
        prev = _gap_value(behind, ahead, cfg, common - 1)
        if prev is not None:
            delta = _format_gap(now - prev, n_signs)
    return _format_gap(sign * now, n_signs), delta


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
            # The next rider trails this one, so report their gap as negative.
            gap, delta = _gap_and_delta(ranked[i + 1], elem, cfg, sign=-1)
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
    protocol: list[FinishProtocolElement], cfg: RaceConfig
) -> dict[str, dict[str, str]]:
    """Build bib -> {key: value} for the enabled scopes; empty when both toggles off.

    Takes the calculated (unsorted) protocol and ranks it here from lap-finish data
    only, so a missed control-point mark cannot change a place. Each group's order is
    that same ranking filtered to the group.
    """
    if not (cfg.send_group_statistics or cfg.send_absolute_statistics):
        return {}

    ranked = _rank_finish_only(protocol, cfg)
    abs_scope = _rank_scope(ranked, cfg) if cfg.send_absolute_statistics else {}

    group_scope: dict[str, dict[str, str]] = {}
    if cfg.send_group_statistics:
        groups: dict[str, list[FinishProtocolElement]] = defaultdict(list)
        for elem in ranked:
            groups[elem.group_id].append(elem)
        for members in groups.values():
            group_scope.update(_rank_scope(members, cfg))

    stats: dict[str, dict[str, str]] = {}
    for elem in ranked:
        cid = elem.competitor_id
        data: dict[str, str] = {}
        if cfg.send_group_statistics and cid in group_scope:
            _emit_scope(group_scope[cid], "_group", data)
        if cfg.send_absolute_statistics and cid in abs_scope:
            _emit_scope(abs_scope[cid], "_abs", data)
        data["laps"] = f"{_laps_done(elem, cfg)}/{_total_laps(elem, cfg)}"
        stats[cid] = data
    return stats
