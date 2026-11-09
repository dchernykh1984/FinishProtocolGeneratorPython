"""Read every PDF of the event back and check each field against the race data.

    uv run --with pdfplumber==0.11.7 python \
        .claude/skills/federation-protocol/scripts/verify.py \
        DATA.json EVENT.json OUT_DIR

Independent of render.py on purpose: the places are worked out again here from the
ladder and the qualification, by a second implementation of the rules, and the PDF
is read back as text -- so a wrong rule, a lost row or a cell that wrapped onto two
lines ("DN" / "Q") all show up. Exits 1 when anything differs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber

SEMIS = ("1/2 final 1", "1/2 final 2")


def norm(cell: str | None) -> str:
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def expected_places(group: str, data: dict[str, Any]) -> list[tuple[str, str]]:
    """(place, bib) per row: the rules of SKILL.md, worked out from scratch."""
    q = data["qualification"][group]
    heats = data["ladders"].get(group, {})
    final, small = heats.get("Final", []), heats.get("Small final", [])
    semis = [h for t in SEMIS for h in heats.get(t, [])]

    def done(heat: list[dict]) -> list[str]:
        return [
            h["bib"]
            for h in sorted(
                (h for h in heat if h["place"].isdigit()), key=lambda h: int(h["place"])
            )
        ]

    held = any(h["status"] != "dns" for h in small)
    through = done(final) + (
        done(small) if held else sorted((h["bib"] for h in small), key=q.index)
    )
    rows = [(i, b) for i, b in enumerate(through, 1)]
    raced = final + (small if held else []) + semis
    out_of_heat = [
        h["bib"]
        for h in raced
        if h["status"] in ("dnf", "dns") and h["bib"] not in through
    ]
    rows += [(len(semis or final), b) for b in sorted(set(out_of_heat), key=q.index)]
    rows.sort(key=lambda pb: pb[0])
    result = [(str(p), b) for p, b in rows]
    in_ladder = {h["bib"] for hs in heats.values() for h in hs}
    n = max((p for p, _b in rows), default=0)
    riders = data["riders"]
    for b in q:
        if b not in in_ladder and not riders[b]["qual_status"]:
            n += 1
            result.append((str(n), b))
    for status in ("DNF", "DNS"):
        result += [
            (status, b)
            for b in q
            if b not in in_ladder and riders[b]["qual_status"] == status
        ]
    disqualified = {
        h["bib"] for hs in heats.values() for h in hs if h["status"] == "dsq"
    }
    disqualified |= {
        b for b in q if b not in in_ladder and riders[b]["qual_status"] == "DSQ"
    }
    result += [("DSQ", b) for b in sorted(disqualified, key=q.index)]
    return result


def read_pdf(path: Path) -> tuple[str, list[list[str]]]:
    rows: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        for page in pdf.pages:
            for table in page.extract_tables():
                rows += [[norm(c) for c in row] for row in table]
    return text, rows


def split_sections(
    rows: list[list[str]], problems: list[str]
) -> list[list[tuple[str, list[list[str]]]]]:
    """The final places, then the qualification: (heading, rows) per group."""
    sections: list[list[tuple[str, list[list[str]]]]] = [[], []]
    part = 0
    seen: set[str] = set()
    for row in rows:
        if len(row) != 6:
            problems.append(f"row with {len(row)} cells: {row}")
        elif not row[0] and not row[1] and row[2]:
            if row[2] in seen and part == 0:
                part, seen = 1, set()
            seen.add(row[2])
            sections[part].append((row[2], []))
        elif sections[part]:
            sections[part][-1][1].append(row)
    return sections


def fixed(text: str, event: dict[str, Any]) -> str:
    for wrong, right in event.get("corrections", {}).items():
        text = text.replace(wrong, right)
    return text


def check_finals(
    groups: list[tuple[str, list[list[str]]]],
    data: dict[str, Any],
    event: dict[str, Any],
) -> list[str]:
    problems = []
    for group, got in groups:
        # Whatever the rules say, every rider of the group is on the list exactly
        # once. A rule both implementations get wrong the same way cannot hide that.
        listed = sorted(r[1] for r in got)
        if listed != sorted(data["qualification"][group]):
            missing = sorted(set(data["qualification"][group]) - set(listed))
            twice = sorted({b for b in listed if listed.count(b) > 1})
            problems.append(f"final places {group}: missing {missing}, twice {twice}")
        want = expected_places(group, data)
        if [(r[0], r[1]) for r in got] != want:
            problems.append(
                f"final places {group}: {[(r[0], r[1]) for r in got]} != {want}"
            )
        for r in got:
            e = data["riders"][r[1]]
            shown = [
                fixed(e[k], event) if k != "birth" else e[k]
                for k in ("name", "birth", "team", "coach")
            ]
            if r[2:] != shown:
                problems.append(f"final places #{r[1]}: {r[2:]} != {shown}")
    return problems


def check_qualification(
    groups: list[tuple[str, list[list[str]]]],
    data: dict[str, Any],
    event: dict[str, Any],
) -> list[str]:
    problems = []
    riders = data["riders"]
    for group, got in groups:
        order = data["qualification"][group]
        want = [
            (str(riders[b]["qual_place"] or riders[b]["qual_status"]), b) for b in order
        ]
        if [(r[0], r[1]) for r in got] != want:
            problems.append(
                f"qualification {group}: {[(r[0], r[1]) for r in got]} != {want}"
            )
        for r in got:
            e = riders[r[1]]
            shown = [
                fixed(e["name"], event),
                e["birth"],
                e.get("time", ""),
                fixed(e["coach"], event),
            ]
            if r[2:] != shown:
                problems.append(f"qualification #{r[1]}: {r[2:]} != {shown}")
    return problems


def check_part(
    part: dict[str, Any], out_dir: Path, data: dict[str, Any], event: dict[str, Any]
) -> list[str]:
    text, rows = read_pdf(out_dir / part["file"])
    words = [part["title"], *event["letterhead"], *event["labels"].values()]
    words += [event[k] for k in ("date", "city", "judge", "secretary")]
    problems = [f"missing text: {w!r}" for w in words if norm(w) not in norm(text)]
    titles = event.get("group_titles", {})
    heads = [titles.get(g, g) for g in part["groups"]]
    finals, quals = split_sections(rows, problems)
    got_heads = ([h for h, _r in finals], [h for h, _r in quals])
    if got_heads != (heads, heads):
        return [*problems, f"groups {got_heads} != {heads} in both sections"]
    pairs = list(zip(part["groups"], [r for _h, r in finals], strict=True))
    qpairs = list(zip(part["groups"], [r for _h, r in quals], strict=True))
    return (
        problems
        + check_finals(pairs, data, event)
        + check_qualification(qpairs, data, event)
    )


def main(data_path: str, event_path: str, out_dir: str) -> int:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    failed = False
    for part in event["parts"]:
        problems = check_part(part, Path(out_dir), data, event)
        print(
            f"{part['file']}: "
            + ("OK" if not problems else f"{len(problems)} problem(s)")
        )
        for p in problems:
            print("  -", p)
        failed |= bool(problems)
    covered = [g for part in event["parts"] for g in part["groups"]]
    left = sorted(set(data["qualification"]) - set(covered))
    if left or len(covered) != len(set(covered)):
        twice = len(covered) - len(set(covered))
        print(f"groups printed in no part: {left}; printed twice: {twice}")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
