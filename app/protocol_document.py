"""The structured protocol document (schema 1) the cycling site draws in its own look.

The HTML protocol stays what the writer makes; this is the same race as data: which
tables and columns there are, what each cell says, which columns a phone can do
without. The site knows nothing of laps, attempts or control points -- every choice of
what to show is made here, from the same settings and the same calculations
(app/protocol_rows.py) the HTML writer uses, so the two never disagree.

Schema: tests/fixtures/protocol-document-v1.json, a copy of the site's
protocols/schema/protocol-document-v1.json.
"""

from __future__ import annotations

import hashlib
import html
import re
from importlib import metadata
from typing import Any

from app.config import RaceConfig
from app.models import FinishProtocolElement, GroupStartElement
from app.protocol_rows import (
    format_time,
    group_places,
    is_printed,
    lap_parts,
    lap_ranks,
    laps_to_show,
    place_status,
    prepare_statuses,
    result_parts,
    split_text,
    time_shift_text,
)

SCHEMA_VERSION = 1
GENERATOR = "FinishProtocolGenerator"
#: The site's limit on a group id; longer group names are cut for the id only.
_MAX_GROUP_ID = 100
_TAG = re.compile(r"<[^>]*>")
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _plain(text: str) -> str:
    """A label as text: the HTML some labels carry (line breaks) becomes spaces."""
    text = _BREAK.sub(" ", text or "")
    return " ".join(html.unescape(_TAG.sub("", text)).split())


def _version() -> str:
    try:
        return metadata.version("finish-protocol-generator")
    except metadata.PackageNotFoundError:
        return ""


def _group_id(name: str) -> str:
    """A group's id on the site: its name, or -- for a name longer than the site
    allows -- the name cut short plus a hash of the whole, so two long names never
    become one group and the id stays the same from one run to the next."""
    if len(name) <= _MAX_GROUP_ID:
        return name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]  # noqa: S324 -- an id
    return f"{name[: _MAX_GROUP_ID - len(digest) - 1]}~{digest}"


def _cell(text: str, sub: list[str] | None = None, strong: bool = False) -> Any:
    sub = [line for line in (sub or []) if line]
    if not sub and not strong:
        return text
    cell: dict[str, Any] = {"text": text}
    if sub:
        cell["sub"] = sub
    if strong:
        cell["strong"] = True
    return cell


def _column(column_id: str, label: str, **extra: Any) -> dict[str, Any]:
    column: dict[str, Any] = {"id": column_id, "label": _plain(label)}
    for key, value in extra.items():
        if value:
            column[key] = value
    return column


def _person_columns(cfg: RaceConfig, absolute: bool) -> list[dict[str, Any]]:
    specs: list[tuple[bool, str, str, dict[str, Any]]] = [
        (cfg.show_place, "place", cfg.place_label, {"role": "place"}),
        (cfg.show_id, "bib", cfg.id_label, {"role": "bib"}),
        (cfg.show_name, "name", cfg.name_label, {"role": "name"}),
        (cfg.show_age, "year", cfg.age_label, {"priority": 3}),
        (
            absolute and cfg.show_group,
            "group",
            cfg.group_label,
            {"role": "group", "priority": 2},
        ),
        (cfg.show_team, "team", cfg.team_label, {"role": "team", "priority": 2}),
        (cfg.show_city, "city", cfg.city_label, {"priority": 3}),
    ]
    return [_column(cid, label, **extra) for on, cid, label, extra in specs if on]


def _lap_columns(cfg: RaceConfig, j: int, n_points: int) -> list[dict[str, Any]]:
    """One lap: its time, then its ranks (use_all_buttons), then its splits."""
    lap = f"{cfg.lap_name} {j + 1}"
    finish = [_plain(cfg.lap_additional_info)] if cfg.show_lap_finish else []
    columns = [_column(f"lap{j + 1}", lap, group=lap, sub_label=finish, priority=3)]
    ranks = []
    if cfg.use_all_buttons:
        ranks.append(("rank", cfg.lap_rank_label))
        if cfg.show_lap_finish:
            ranks.append(("finish_rank", cfg.lap_finish_rank_label))
    for suffix, label in ranks:
        columns.append(
            _column(
                f"lap{j + 1}_{suffix}", label, group=lap, toggle="lap_stats", priority=3
            )
        )
    # Splits are switchable only where the HTML has their button; without it they
    # are simply shown.
    toggle = "splits" if cfg.use_buttons else None
    for cp_i in range(n_points + 1 if n_points > 0 else 0):
        columns.append(
            _column(
                f"lap{j + 1}_s{cp_i + 1}",
                f"({cp_i + 1} split)",
                group=lap,
                toggle=toggle,
                priority=3,
            )
        )
    if len(columns) == 1:
        # A lap of one column needs no heading above its own heading.
        columns[0].pop("group", None)
    return columns


def _closing_columns(cfg: RaceConfig) -> list[dict[str, Any]]:
    columns = []
    if cfg.show_finish_time:
        sub = []
        if cfg.show_time_difference:
            sub.append(_plain(cfg.time_difference_label))
        if cfg.show_n_finished_laps:
            sub.append(_plain(cfg.n_finished_laps_label))
        columns.append(
            _column("result", cfg.finish_time_label, role="result", sub_label=sub)
        )
    if cfg.show_additional_info:
        columns.append(_column("extra", cfg.additional_info_label, priority=3))
    if cfg.show_time_shift:
        columns.append(_column("start", cfg.time_shift_label, priority=3))
    return columns


def _columns(
    cfg: RaceConfig, n_laps: int, multi_lap: bool, n_points: int, absolute: bool
) -> list[dict[str, Any]]:
    """The table's columns, in the order the HTML writer prints them."""
    columns = _person_columns(cfg, absolute)
    if cfg.show_lap_times and multi_lap:
        for j in range(n_laps):
            columns.extend(_lap_columns(cfg, j, n_points))
    return columns + _closing_columns(cfg)


def _rank_text(gap: float, place: int, cfg: RaceConfig) -> Any:
    return _cell(
        f"{format_time(gap, cfg.n_signs_after_point)} ({place})", strong=place == 1
    )


def _row(
    fp: FinishProtocolElement,
    place: int,
    leader: FinishProtocolElement | None,
    peers: list[FinishProtocolElement],
    cfg: RaceConfig,
    columns: list[dict[str, Any]],
    n_laps: int,
    n_points: int,
    group_place: int | None,
) -> dict[str, Any]:
    ids = {c["id"] for c in columns}
    text, status = place_status(fp, place, cfg)
    cells: dict[str, Any] = {}
    values: dict[str, Any] = {
        "place": text,
        "bib": _cell(
            fp.competitor_id, [str(fp.number + i) for i in range(1, fp.stages)]
        ),
        "name": fp.name,
        "year": fp.year_of_birth,
        "group": _cell(fp.group_id, [f"({group_place})"] if group_place else []),
        "team": fp.team,
        "city": fp.city,
        "extra": fp.extra_info,
        "start": time_shift_text(fp, cfg),
    }
    for lc in range(n_laps):
        parts = lap_parts(fp, lc, cfg)
        values[f"lap{lc + 1}"] = _cell(
            parts.text,
            [*parts.penalties, parts.finish_number, parts.finish_time],
            parts.strong,
        )
        ranks = lap_ranks(fp, lc, peers)
        if ranks is not None:
            values[f"lap{lc + 1}_rank"] = _rank_text(
                ranks.gap_lap, ranks.place_lap, cfg
            )
            values[f"lap{lc + 1}_finish_rank"] = _rank_text(
                ranks.gap_finish, ranks.place_finish, cfg
            )
        for cp_i in range(n_points + 1 if n_points > 0 else 0):
            values[f"lap{lc + 1}_s{cp_i + 1}"] = split_text(fp, lc, cp_i, cfg)
    result = result_parts(fp, leader, cfg)
    values["result"] = _cell(result.time, [result.gap, result.count])
    for column_id, value in values.items():
        if column_id in ids and value not in ("", None):
            cells[column_id] = value
    row: dict[str, Any] = {"cells": cells}
    if status != "ok":
        row["status"] = status
    if fp.disqualified and fp.dsq_reasons:
        # In the HTML the reasons fill the result cell; the site shows a note under the
        # row instead, always visible.
        row["note"] = "\n".join(fp.dsq_reasons)
    return row


def _table(
    members: list[FinishProtocolElement],
    all_protocol: list[FinishProtocolElement],
    group_id: str | None,
    cfg: RaceConfig,
    n_points: int,
    places: dict[int, int],
) -> dict[str, Any]:
    n_laps, multi_lap = laps_to_show(all_protocol, group_id, cfg, n_points)
    absolute = group_id is None
    columns = _columns(cfg, n_laps, multi_lap, n_points, absolute)
    shown_laps = n_laps if cfg.show_lap_times and multi_lap else 0
    rows = []
    leader: FinishProtocolElement | None = None
    place = 0
    for fp in members:
        if not is_printed(fp, cfg):
            continue
        place += 1
        if fp.finished and not fp.disqualified and leader is None:
            leader = fp
        row = _row(
            fp,
            place,
            leader,
            members,
            cfg,
            columns,
            shown_laps,
            n_points,
            places.get(id(fp)),
        )
        if absolute and fp.group_id:
            # A rider without a group has no group to filter by (the site wants none).
            row["group"] = _group_id(fp.group_id)
        rows.append(row)
    return {"type": "table", "columns": columns, "rows": rows}


def _items(cfg: RaceConfig, header: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def field(key: str, label: str, value: str) -> None:
        if value:
            items.append(
                {"type": "field", "key": key, "label": _plain(label), "value": value}
            )

    if header:
        if cfg.sponsor:
            items.append({"type": "html", "html": cfg.sponsor})
        if cfg.race_date and cfg.race_place:
            items.append({"type": "text", "text": f"{cfg.race_date}, {cfg.race_place}"})
        field("track", cfg.track_conditions_label, cfg.track_conditions)
        field("weather", cfg.weather_label, cfg.weather)
    else:
        field("organizer", cfg.organizer_label, cfg.organizer)
        field("referee", cfg.referee_label, cfg.main_referee)
        field("secretary", cfg.secretary_label, cfg.additional_referee)
        if cfg.bottom_text:
            items.append({"type": "html", "html": cfg.bottom_text})
    return items


def _document(
    cfg: RaceConfig,
    groups: list[GroupStartElement],
    protocol: list[FinishProtocolElement],
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    registry: list[dict[str, str]] = []
    seen: set[str] = set()
    for group_id in [g.group_id for g in groups] + [fp.group_id for fp in protocol]:
        key = _group_id(group_id)
        if key and key not in seen:
            seen.add(key)
            registry.append({"id": key, "label": group_id})
    toggles = []
    if (
        cfg.use_buttons
        and cfg.show_lap_times
        and any(c.get("toggle") == "splits" for s in sections for c in s["columns"])
    ):
        toggles.append(
            {"id": "splits", "label": _plain(cfg.use_buttons_label), "default": True}
        )
    if (
        cfg.use_all_buttons
        and cfg.show_lap_times
        and any(c.get("toggle") == "lap_stats" for s in sections for c in s["columns"])
    ):
        toggles.append(
            {
                "id": "lap_stats",
                "label": _plain(cfg.use_all_buttons_label),
                "default": True,
            }
        )
    document: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "generator": {"name": GENERATOR, "version": _version()},
        "header": _items(cfg, header=True),
        "groups": registry,
        "toggles": toggles,
        "sections": sections,
        "footer": _items(cfg, header=False),
    }
    if cfg.race_name:
        document["title"] = cfg.race_name
    if cfg.protocol_language:
        document["lang"] = cfg.protocol_language
    return document


def build_group_document(
    sorted_protocol: list[FinishProtocolElement],
    group_list: list[GroupStartElement],
    cfg: RaceConfig,
    n_points: int = 0,
) -> dict[str, Any]:
    """The group protocol as a document: one table per group, as the HTML has."""
    prepare_statuses(sorted_protocol, cfg)
    sections = []
    for gs in group_list:
        members = [fp for fp in sorted_protocol if fp.group_id == gs.group_id]
        table = _table(members, sorted_protocol, gs.group_id, cfg, n_points, {})
        table["title"] = _plain(f"{cfg.group_label} {gs.group_id}")
        if _group_id(gs.group_id):
            table["group"] = _group_id(gs.group_id)
        sections.append(table)
    return _document(cfg, group_list, sorted_protocol, sections)


def build_absolute_document(
    sorted_protocol: list[FinishProtocolElement],
    group_list: list[GroupStartElement],
    cfg: RaceConfig,
    n_points: int = 0,
) -> dict[str, Any]:
    """The absolute protocol as a document: one table, each row tagged with a group."""
    prepare_statuses(sorted_protocol, cfg)
    places = group_places(sorted_protocol, group_list, cfg)
    table = _table(sorted_protocol, sorted_protocol, None, cfg, n_points, places)
    table["title"] = _plain(cfg.overall_results_label)
    return _document(cfg, group_list, sorted_protocol, [table])
