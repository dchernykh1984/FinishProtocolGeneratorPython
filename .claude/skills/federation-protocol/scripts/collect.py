"""Gather what the federation protocol prints, from the two generator runs.

    uv run python .claude/skills/federation-protocol/scripts/collect.py \
        QUALIFICATION_DIR FINALS_DIR OUT.json

Each DIR is the folder a run of the generator works in -- the one holding its
fpg_info.txt and the group protocol it wrote: the qualification (a Custom Start time
trial) and the Eliminator Finals. The published HTML protocols give everything the
federation protocol shows;
the qualification marks are scored again with the generator's own calculator only for
the hundredths its time format needs, and the run stops if that scoring does not
reproduce every published time.

Reads only. The configs are read in memory and never copied or printed: they carry
the site's upload token.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from app.calculator import calculate_protocol, generate_sorted_protocol  # noqa: E402
from app.config import RaceConfig  # noqa: E402
from app.file_io import (  # noqa: E402
    load_config_file,
    read_finish_times,
    read_group_times,
    read_start_protocol,
)
from app.models import GroupStartElement  # noqa: E402
from app.protocol_rows import format_time, result_seconds  # noqa: E402

STATUSES = ("DNS", "DNF", "DSQ")
HEAT_TITLE = re.compile(r'<FONT SIZE="3" COLOR="#000000"><B><CENTER>([^<]*)</CENTER>')
GROUP_TITLE = re.compile(r"<U>([^<]*)</U>")
ROW = re.compile(r"<tr\b.*?</tr>", re.S | re.I)


def cells(row: str) -> list[str]:
    out = []
    for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I):
        text = re.sub(r"<[^>]+>", " ", cell).replace("&nbsp", " ")
        out.append(re.sub(r"\s+", " ", html.unescape(text)).strip())
    return out


def label(cfg: dict[str, str], key: str) -> str:
    """A setting from fpg_info.txt, or the generator's own default when the file has
    no line for it -- which is what the published protocol then shows."""
    return cfg.get(key) or str(getattr(RaceConfig(), key))


def columns(header: list[str], cfg: dict[str, str], *keys: str) -> dict[str, int]:
    """Column index by setting name, matched against the header row's labels."""
    found = {}
    for key in keys:
        name = label(cfg, key)
        hits = [i for i, text in enumerate(header) if text.startswith(name)]
        if not hits:
            sys.exit(f"the published protocol has no {name!r} column ({key})")
        found[key] = hits[0]
    return found


def group_of(heading: str, label: str) -> str:
    text = html.unescape(heading).strip()
    return text[len(label) :].strip() if text.startswith(label + " ") else text


def qualification(finish: Path, cfg: dict[str, str]) -> dict[str, list[dict]]:
    """Group -> rows of the published qualification protocol, in its order."""
    page = (finish / label(cfg, "group_protocol_file")).read_text(encoding="utf-8")
    tokens = re.finditer(rf"{GROUP_TITLE.pattern}|(?P<row>{ROW.pattern})", page, re.S)
    keys = (
        "place_label",
        "id_label",
        "name_label",
        "team_label",
        "additional_info_label",
        "finish_time_label",
    )
    groups: dict[str, list[dict]] = {}
    group, col, width = "", {}, 0
    for m in tokens:
        if m.group("row") is None:
            group = group_of(m.group(1), label(cfg, "group_label"))
            groups.setdefault(group, [])
            continue
        c = cells(m.group("row"))
        if c and c[0] == label(cfg, "place_label"):
            col, width = columns(c, cfg, *keys), len(c)
            continue
        if not col or len(c) != width or not c[col["id_label"]]:
            continue
        groups[group].append(
            {
                "place": c[col["place_label"]],
                "bib": c[col["id_label"]],
                "name": c[col["name_label"]],
                "team": c[col["team_label"]],
                "birth": c[col["additional_info_label"]],
                "time": c[col["finish_time_label"]].split(" (")[0],
            }
        )
    return {g: rows for g, rows in groups.items() if rows}


def ladders(finish: Path, cfg: dict[str, str]) -> dict[str, dict[str, list[dict]]]:
    """Group -> heat -> rows, each heat's table cut from its title to its end: the
    ladder nests heat tables inside layout rows, so rows cannot be matched page-wide."""
    page = (finish / label(cfg, "group_protocol_file")).read_text(encoding="utf-8")
    heads = [
        (m.start(), group_of(m.group(1), label(cfg, "group_label")))
        for m in GROUP_TITLE.finditer(page)
    ]
    out: dict[str, dict[str, list[dict]]] = {name: {} for _pos, name in heads}
    for m in HEAT_TITLE.finditer(page):
        owner = [name for pos, name in heads if pos < m.start()][-1]
        title = re.sub(r"\s*\(.*\)$", "", html.unescape(m.group(1))).strip()
        table = page[m.end() : page.index("</table>", m.end())]
        rows, col = [], {}
        for row in ROW.findall(table):
            c = cells(row)
            if c and c[0] == label(cfg, "place_label"):
                col = columns(c, cfg, "place_label", "id_label")
            elif col and len(c) > col["id_label"] and c[col["id_label"]]:
                place, bib = c[col["place_label"]], c[col["id_label"]]
                status = place.lower() if place in STATUSES else "ok"
                rows.append({"bib": bib, "place": place, "status": status})
        out[owner][title] = rows
    return out


def exact_results(finish: Path, cfg: dict[str, str]) -> dict[str, float]:
    """Each qualifier's result in seconds, scored as the generator scores it."""
    race = RaceConfig(
        race_type=cfg["race_type"],
        minimal_time_for_lap=int(cfg.get("minimal_time_for_lap") or 0),
        time_limit=int(cfg.get("time_limit") or 0),
        n_signs_after_point=int(cfg.get("n_signs_after_point") or 1),
    )
    start = read_start_protocol(
        str(finish / label(cfg, "start_protocol_file")), race.skip_first_lap_effective()
    )
    groups = read_group_times(str(finish / label(cfg, "group_time_file")))
    known = {g.group_id for g in groups}
    for s in start:
        if s.group_id not in known:
            known.add(s.group_id)
            groups.append(GroupStartElement(group_id=s.group_id, seconds=0.0))
    marks = read_finish_times(str(finish / label(cfg, "finish_time_file")))
    protocol = calculate_protocol(start, groups, marks, [], [], race, [])
    return {
        fp.competitor_id: result_seconds(fp, race)
        for fp in generate_sorted_protocol(protocol, race, 0)
        if fp.finished and not fp.disqualified
    }


def old_style(seconds: float) -> str:
    """The federation's "1:09:87" -- minutes, seconds, hundredths -- rounded as the
    generator rounds (a half to the even digit, on the recorded millisecond)."""
    hours, minutes, rest = format_time(seconds, 2).split(":")
    secs, hundredths = rest.split(".")
    return f"{int(hours) * 60 + int(minutes)}:{secs}:{hundredths}"


def collect(qfinish: Path, ffinish: Path) -> dict[str, Any]:
    qcfg = load_config_file(str(qfinish / "fpg_info.txt"))
    fcfg = load_config_file(str(ffinish / "fpg_info.txt"))
    signs = int(qcfg.get("n_signs_after_point") or 1)
    exact = exact_results(qfinish, qcfg)
    riders: dict[str, dict] = {}
    order: dict[str, list[str]] = {}
    wrong = []
    for group, rows in qualification(qfinish, qcfg).items():
        order[group] = [r["bib"] for r in rows]
        for r in rows:
            team, _sep, coach = r["team"].partition(" - ")
            year, month, day = r["birth"].split("-")
            entry = {
                "bib": r["bib"],
                "name": r["name"],
                "group": group,
                "team": team.strip(),
                "coach": coach.strip(),
                "birth": f"{day}.{month}.{year}",
                "qual_place": int(r["place"]) if r["place"].isdigit() else None,
                "qual_status": r["place"] if r["place"] in STATUSES else "",
                "published_time": r["time"],
            }
            if entry["qual_place"] is not None:
                seconds = exact[r["bib"]]
                entry["time"] = old_style(seconds)
                if format_time(seconds, signs) != r["time"]:
                    wrong.append(
                        f"#{r['bib']}: {format_time(seconds, signs)} vs {r['time']}"
                    )
            riders[r["bib"]] = entry
    if wrong:
        sys.exit(
            "re-scored times differ from the published protocol:\n" + "\n".join(wrong)
        )
    return {"riders": riders, "qualification": order, "ladders": ladders(ffinish, fcfg)}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    data = collect(Path(sys.argv[1]), Path(sys.argv[2]))
    Path(sys.argv[3]).write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    count, groups = len(data["riders"]), len(data["qualification"])
    print(f"{count} riders, {groups} groups -> {sys.argv[3]}")
