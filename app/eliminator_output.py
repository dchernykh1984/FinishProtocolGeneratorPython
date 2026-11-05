"""What an Eliminator Finals ladder looks like, as HTML and as site data.

The HTML keeps the shape the C++ generator drew: one table per group holding the
whole ladder, each heat a little table of its own, the rounds spreading left to
right with row spans so a heat sits beside the two it was fed by.

The site is sent the same ladder as ordinary tables -- one per heat, titled with its
round -- because the document schema has no notion of a bracket and the site draws
what it is given. Nothing on the site has to change to show these.
"""

from __future__ import annotations

import html
from typing import Any, TextIO

from app.config import RaceConfig
from app.eliminator import EliminatorBracket, Heat
from app.html_writer import _write_footer, _write_header
from app.models import GroupStartElement, StartProtocolElement
from app.paths import app_path
from app.protocol_document import _cell, _column, _document, _group_id, _plain


def _rider_index(
    start_list: list[StartProtocolElement],
) -> dict[str, StartProtocolElement]:
    return {start.competitor_id: start for start in start_list}


def heat_title(bracket: EliminatorBracket, heat: Heat) -> str:
    """ "1/4 final 2", "Final" or "Small final", as the C++ version titled them."""
    remaining = 2 ** (bracket.group.rounds - heat.stage - 1)
    if remaining != 1:
        return f"1/{remaining} final {heat.number + 1}"
    return "Small final" if heat.is_small_final else "Final"


def _person_fields(cfg: RaceConfig) -> list[tuple[str, str, str]]:
    """The optional columns of a heat table: (id, label, rider attribute)."""
    wanted = [
        (cfg.show_id, "bib", cfg.id_label, "competitor_id"),
        (cfg.show_name, "name", cfg.name_label, "name"),
        (cfg.show_age, "year", cfg.age_label, "year_of_birth"),
        (cfg.show_team, "team", cfg.team_label, "team"),
        (cfg.show_city, "city", cfg.city_label, "city"),
        (cfg.show_additional_info, "extra", cfg.additional_info_label, "extra_info"),
    ]
    return [(key, label, attr) for shown, key, label, attr in wanted if shown]


def _seat_values(
    bracket: EliminatorBracket,
    heat: Heat,
    seat: int,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> tuple[str, list[str]]:
    """The place cell and the rider cells of one seat."""
    bib = heat.numbers[seat]
    place = bracket.finishing_places(heat)[seat]
    if place is not None:
        place_text = str(place)
    elif bib and heat.has_results:
        # Only a heat that has been ridden can leave somebody unclassified. The C++
        # version wrote DNF against every seeded rider from the moment the ladder was
        # drawn, which reads as though the whole field had abandoned.
        place_text = "DNF"
    else:
        place_text = ""
    rider = riders.get(bib)
    values = []
    for _key, _label, attr in _person_fields(cfg):
        if rider is not None:
            values.append(str(getattr(rider, attr, "")))
        else:
            # A seat whose bib is not in the start protocol still shows the bib.
            values.append(bib if attr == "competitor_id" else "")
    return place_text, values


# -- HTML ---------------------------------------------------------------------


def _write_heat(
    f: TextIO,
    bracket: EliminatorBracket,
    heat: Heat,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> None:
    st = cfg.styles
    title = html.escape(heat_title(bracket, heat))
    f.write(f'<FONT SIZE="3" COLOR="#000000"><B><CENTER>{title}</CENTER></B></FONT>')
    f.write(f'<table style="{st.table_style}"')
    if cfg.stretch:
        f.write(" width=100%")
    f.write(" border=0>")
    f.write(f'<tr style="{st.top_line_style}">')
    if cfg.show_place:
        f.write(f"<td ALIGN=center><B>{html.escape(cfg.place_label)}</B></td>\n")
    for _key, label, _attr in _person_fields(cfg):
        f.write(f"<td ALIGN=center><B>{html.escape(label)}</B></td>\n")
    f.write("</tr>\n")
    for seat in range(len(heat.numbers)):
        place_text, values = _seat_values(bracket, heat, seat, riders, cfg)
        row_style = st.even_line_style if seat % 2 == 0 else st.odd_line_style
        f.write(f'<tr style="{row_style}">')
        if cfg.show_place:
            f.write(f"<td ALIGN=center>{html.escape(place_text)}</td>\n")
        for value in values:
            f.write(f"<td ALIGN=center>{html.escape(value)}</td>\n")
        f.write("</tr>\n")
    f.write("</table>\n")


def _write_ladder(
    f: TextIO,
    bracket: EliminatorBracket,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> None:
    rounds = bracket.group.rounds
    first_stage_heats = 2 ** (rounds - 1)
    f.write('<table style="background-color: rgb(255, 255, 255);"')
    if cfg.stretch:
        f.write(" width=100%")
    f.write(" border=0>")
    for row in range(first_stage_heats):
        f.write('<tr style="text-align: center;">')
        for stage in range(rounds):
            # The last column repeats the final's span so the small final can share it.
            span_stage = min(stage, rounds - 2) if rounds > 1 else 0
            span = 2**span_stage
            if (first_stage_heats - row) % span:
                continue
            number = row // span
            heat = bracket.heat(stage, number)
            align = "center"
            if rounds > 1 and stage == span_stage + 1:
                align = "bottom" if number == 0 else "top"
            f.write(f'<td valign="{align}" ROWSPAN={span}>')
            _write_heat(f, bracket, heat, riders, cfg)
            f.write("</td>")
        f.write("</tr>\n")
    f.write("</table>\n")


def write_finals_protocol(
    path: str,
    brackets: list[EliminatorBracket],
    start_list: list[StartProtocolElement],
    cfg: RaceConfig,
) -> None:
    """Write every group's ladder into the group protocol file."""
    riders = _rider_index(start_list)
    with app_path(path).open("w", encoding="utf-8") as f:
        _write_header(f, cfg, len(start_list), 0)
        for bracket in brackets:
            group_id = html.escape(bracket.group.group_id)
            label = html.escape(cfg.group_label)
            f.write(
                f"<BR>{cfg.styles.group_name_style}<B><CENTER><U>"
                f"{label} {group_id}</U></CENTER></B></FONT><BR>\n"
            )
            _write_ladder(f, bracket, riders, cfg)
        _write_footer(f, cfg)


# -- site document ------------------------------------------------------------


def _heat_section(
    bracket: EliminatorBracket,
    heat: Heat,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    if cfg.show_place:
        columns.append(_column("place", cfg.place_label, role="place", priority=1))
    for key, label, _attr in _person_fields(cfg):
        role = "name" if key == "name" else None
        columns.append(_column(key, label, role=role, priority=1 if role else 3))
    rows = []
    for seat in range(len(heat.numbers)):
        place_text, values = _seat_values(bracket, heat, seat, riders, cfg)
        if not heat.numbers[seat]:
            continue
        cells = ([_cell(place_text)] if cfg.show_place else []) + [
            _cell(value) for value in values
        ]
        row: dict[str, Any] = {"cells": cells}
        if place_text == "DNF":
            row["status"] = "dnf"
        rows.append(row)
    section: dict[str, Any] = {
        "type": "table",
        "title": _plain(f"{cfg.group_label} {bracket.group.group_id}"),
        "columns": columns,
        "rows": rows,
    }
    section["title"] = _plain(
        f"{cfg.group_label} {bracket.group.group_id} - {heat_title(bracket, heat)}"
    )
    if _group_id(bracket.group.group_id):
        section["group"] = _group_id(bracket.group.group_id)
    return section


def build_finals_document(
    brackets: list[EliminatorBracket],
    start_list: list[StartProtocolElement],
    cfg: RaceConfig,
) -> dict[str, Any]:
    """The ladders as site data: one table per heat, latest round first.

    Rounds run final-first so a phone shows the decisive heat without scrolling; the
    HTML keeps the left-to-right ladder, which needs the width of a screen.
    """
    riders = _rider_index(start_list)
    sections: list[dict[str, Any]] = []
    groups: list[GroupStartElement] = []
    for bracket in brackets:
        groups.append(GroupStartElement(group_id=bracket.group.group_id, seconds=0.0))
        for stage in reversed(range(bracket.group.rounds)):
            for heat in bracket.heats_in_stage(stage):
                if heat.taken:
                    sections.append(_heat_section(bracket, heat, riders, cfg))
    return _document(cfg, groups, [], sections)
