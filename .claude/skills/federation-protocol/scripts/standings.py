"""Final places of one group: the finals ladder first, then the qualification.

The federation's rules for an Eliminator Finals event, compared with UCI 4.2.12 (the
XCE final classification) in SKILL.md:

1. Whoever finished is numbered straight on: the final's finishers in their order,
   then the small final's. A small final that was not held places its riders by
   qualification instead -- nobody failed to start a heat that never ran.
2. A rider who did not finish or did not start a heat of the finals (semi-final,
   final or small final) takes the last place a finalist can take -- 8 in a ladder
   of 8 -- shared with every other such rider, in qualification order.
3. Riders who did not make the finals follow straight after the last place a
   finalist took (a disqualified finalist frees his), in qualification order.
4. Riders without a qualification result follow as DNF, then DNS.
5. Disqualified riders come last, as DSQ.

Heat titles are the generator's own: "1/2 final 1", "1/2 final 2", "Final",
"Small final".
"""

from __future__ import annotations

from typing import Any

SEMIS = ("1/2 final 1", "1/2 final 2")
KNOWN = {*SEMIS, "Final", "Small final"}
Row = dict[str, str]


def _finished(heat: list[Row]) -> list[str]:
    ranked = sorted(
        (r for r in heat if r["place"].isdigit()), key=lambda r: int(r["place"])
    )
    return [r["bib"] for r in ranked]


def _no_small_final(final: list[Row], semis: list[Row]) -> list[Row]:
    """The riders a small final would have held, when the meeting rides none: the
    semi-finalists who finished and did not go through. A small final not held goes
    by qualification, so they are set as riders of one that did not start."""
    in_final = {r["bib"] for r in final}
    return [
        {**r, "place": "DNS", "status": "dns"}
        for r in semis
        if r["status"] == "ok" and r["bib"] not in in_final
    ]


def _held(heat: list[Row]) -> bool:
    """Held means started: a heat that never ran shows DNS for everyone, one that ran
    and that nobody finished shows DNF -- and those riders take the last place."""
    return any(r["status"] != "dns" for r in heat)


def _in_order(heat: list[Row], qorder: list[str]) -> list[str]:
    """A heat's riders best first: its finishers if it was held, everyone by
    qualification if it never ran -- nobody failed to start a heat that never ran."""
    if _held(heat):
        return _finished(heat)
    return sorted((r["bib"] for r in heat), key=qorder.index)


def _finalists(heats: dict[str, list[Row]], qorder: list[str]) -> list[tuple[int, str]]:
    """(place, bib) for every finalist who was not disqualified, best first."""
    final = heats.get("Final", [])
    semis = [r for title in SEMIS for r in heats.get(title, [])]
    small = heats.get("Small final") or _no_small_final(final, semis)
    through = _in_order(final, qorder) + _in_order(small, qorder)
    places = list(enumerate(through, start=1))
    last = len(semis or final)  # the last place a finalist can take
    raced = [r for heat in (final, small) if _held(heat) for r in heat] + semis
    unfinished = [
        r["bib"]
        for r in raced
        if r["status"] in ("dnf", "dns") and r["bib"] not in through
    ]
    ordered = sorted(dict.fromkeys(unfinished), key=qorder.index)
    places += [(last, bib) for bib in ordered]
    return sorted(places, key=lambda pb: pb[0])  # stable: shared places keep order


def group_standings(group: str, data: dict[str, Any]) -> list[Row]:
    """[{bib, place}] in protocol order; place is a number, DNF, DNS or DSQ."""
    riders = data["riders"]
    qorder: list[str] = data["qualification"][group]
    heats: dict[str, list[Row]] = data["ladders"].get(group, {})
    deeper = sorted(set(heats) - KNOWN)
    if deeper:
        # Whoever went out before the semi-finals has no rule to place him by; a
        # guess would put somebody's name on the wrong line of an official paper.
        raise ValueError(
            f"{group}: heats {deeper} come before the semi-finals, and the rules do "
            "not place their riders yet -- ask the organizer"
        )
    ladder = {r["bib"] for rows in heats.values() for r in rows}
    outside = [bib for bib in qorder if bib not in ladder]
    in_heats = {
        r["bib"] for rows in heats.values() for r in rows if r["status"] == "dsq"
    }
    # Disqualified in the qualification is disqualified all the same: last, as DSQ.
    in_qual = {bib for bib in outside if riders[bib]["qual_status"] == "DSQ"}
    dsq = sorted(in_heats | in_qual, key=qorder.index)
    placed = _finalists(heats, qorder)
    lost = ladder - {bib for _place, bib in placed} - in_heats
    if lost:
        raise ValueError(f"{group}: finalists with no place: {sorted(lost)}")

    out = [{"bib": bib, "place": str(place)} for place, bib in placed]
    after = max((place for place, _bib in placed), default=0)
    timed = [bib for bib in outside if not riders[bib]["qual_status"]]
    out += [{"bib": bib, "place": str(after + i)} for i, bib in enumerate(timed, 1)]
    for status in ("DNF", "DNS"):
        out += [
            {"bib": bib, "place": status}
            for bib in outside
            if riders[bib]["qual_status"] == status
        ]
    out += [{"bib": bib, "place": "DSQ"} for bib in dsq]
    return out
