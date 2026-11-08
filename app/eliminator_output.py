"""What an Eliminator Finals ladder looks like, as HTML and as site data.

The HTML keeps the shape the C++ generator drew: one table per group holding the
whole ladder, each heat a little table of its own, the rounds spreading left to
right with row spans so a heat sits beside the two it was fed by.

The site is sent the same ladder as a section of type "ladder": the stages in the
order they are ridden, each holding a table per heat -- an empty one too, so the
ladder keeps its shape. The site sets the stages side by side on a wide screen and
lists them, the final first, on a phone (issue #454 on the site).
"""

from __future__ import annotations

import html
from typing import Any, TextIO

from app.config import RaceConfig
from app.eliminator import (
    EliminatorBracket,
    Heat,
    heat_names,
    heat_title,
    ladder_lines,
)
from app.html_writer import _write_footer, _write_header
from app.models import GroupStartElement, StartProtocolElement
from app.paths import app_path
from app.protocol_document import (
    _PRIORITY,
    _cell,
    _column,
    _document,
    _group_id,
    _person_columns,
    _plain,
)
from app.protocol_rows import format_time


def _rider_index(
    start_list: list[StartProtocolElement],
) -> dict[str, StartProtocolElement]:
    return {start.competitor_id: start for start in start_list}


def _heat_heading(bracket: EliminatorBracket, heat: Heat, cfg: RaceConfig) -> str:
    """The heat's title, saying so when its riders went through unraced.

    Without it the protocol would present places nobody rode for as a result, which
    is the one thing a finals protocol must not do.
    """
    title = heat_title(bracket, heat)
    if heat.has_results and not heat.ridden and heat.taken:
        return f"{title} ({cfg.not_ridden_label})"
    return title


def _person_fields(cfg: RaceConfig) -> list[tuple[str, str, str]]:
    """The optional columns of a heat table: (id, label, rider attribute).

    The qualification place is one of them rather than a column of its own: it comes
    off the rider's start line like his team or his year, out of the field the
    seeding export wrote there, and the heat tables are the only tables that have
    it -- in a timed protocol the place is the result, not a thing a rider brought
    with him.
    """
    wanted = [
        (cfg.show_id, "bib", cfg.id_label, "competitor_id"),
        (cfg.show_name, "name", cfg.name_label, "name"),
        (cfg.show_age, "year", cfg.age_label, "year_of_birth"),
        (cfg.show_team, "team", cfg.team_label, "team"),
        (cfg.show_city, "city", cfg.city_label, "city"),
        (cfg.show_additional_info, "extra", cfg.additional_info_label, "extra_info"),
        (
            cfg.show_qualification_place,
            "qual",
            cfg.qualification_place_label,
            "start_place",
        ),
    ]
    return [(key, label, attr) for shown, key, label, attr in wanted if shown]


def _result_parts(heat: Heat, seat: int, cfg: RaceConfig) -> tuple[str, str]:
    """The time this seat rode and the gap to the heat winner, as two cells would
    hold them: the HTML writes them in one, the site puts the gap on a sub-line
    under it, which is how the timed protocol's result column already works.

    A heat is its own race, so the gap is measured inside it: against the field of a
    whole group the number would mean nothing.
    """
    if heat.times[seat] < 0:
        return "", ""
    text = format_time(heat.times[seat], cfg.n_signs_after_point)
    if not cfg.show_time_difference:
        return text, ""
    best = min((time for time in heat.times if time >= 0), default=-1.0)
    gap = heat.times[seat] - best
    if gap <= 0:
        return text, ""
    return text, f"(+{format_time(gap, cfg.n_signs_after_point)})"


def _seat_values(
    bracket: EliminatorBracket,
    heat: Heat,
    seat: int,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> tuple[str, list[str], tuple[str, str], list[str]]:
    """The place cell, the rider cells, the result (time, gap) and the reasons a
    disqualification carried, of one seat.

    A disqualified rider is never given a time, so the reasons have his result cell
    to themselves -- which is where the timed protocols print them too.
    """
    bib = heat.numbers[seat]
    place = bracket.finishing_places(heat)[seat]
    if heat.disqualified[seat]:
        place_text = "DSQ"
    elif place is not None:
        place_text = str(place)
    elif bib and heat.was_started:
        # A heat that has gone off says DNF against a rider until his time comes in,
        # which is what every other race type says about a rider whose group has
        # started and whose finish has not been seen. Waiting for the heat to be
        # over instead left the cell blank, and a heat is only over once a later one
        # starts -- so a rider who pulled out of the last heat of the day read as
        # nothing at all, on a protocol that was otherwise finished.
        place_text = "DNF"
    else:
        place_text = ""
    rider = riders.get(bib)
    values = []
    for _key, _label, attr in _person_fields(cfg):
        if rider is not None:
            value = getattr(rider, attr, "")
            # A qualification place of nothing is a rider the seeding export left
            # unplaced, and a zero in the column would read as a place of its own.
            values.append("" if attr == "start_place" and not value else str(value))
        else:
            # A seat whose bib is not in the start protocol still shows the bib.
            values.append(bib if attr == "competitor_id" else "")
    return (
        place_text,
        values,
        _result_parts(heat, seat, cfg),
        heat.dsq_reasons.get(bib, []) if heat.disqualified[seat] else [],
    )


# -- HTML ---------------------------------------------------------------------


def _reasons_html(reasons: list[str]) -> str:
    """A disqualified rider's reasons, stacked inside one cell.

    Escaped: it is free referee text, typed into the chronometer mid-meeting.
    """
    return "<BR>".join(html.escape(reason) for reason in reasons)


def _write_heat(
    f: TextIO,
    bracket: EliminatorBracket,
    heat: Heat,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> None:
    st = cfg.styles
    title = html.escape(_heat_heading(bracket, heat, cfg))
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
    if cfg.show_finish_time:
        f.write(f"<td ALIGN=center><B>{html.escape(cfg.finish_time_label)}</B></td>\n")
    f.write("</tr>\n")
    for seat in range(len(heat.numbers)):
        place_text, values, result, reasons = _seat_values(
            bracket, heat, seat, riders, cfg
        )
        row_style = st.even_line_style if seat % 2 == 0 else st.odd_line_style
        f.write(f'<tr style="{row_style}">')
        if cfg.show_place:
            f.write(f"<td ALIGN=center>{html.escape(place_text)}</td>\n")
        for value in values:
            f.write(f"<td ALIGN=center>{html.escape(value)}</td>\n")
        if cfg.show_finish_time:
            text = " ".join(part for part in result if part)
            cell = html.escape(text) if text else _reasons_html(reasons)
            f.write(f"<td ALIGN=center>{cell}</td>\n")
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
            if heat.is_small_final and not bracket.has_small_final:
                # No small final ridden: its cell in the last column stays empty
                # rather than drawing a table nobody can be in.
                continue
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


# -- files the chronometer and the next run read ------------------------------


def write_ladder_file(path: str, rows: list[tuple[str, str, str]]) -> None:
    """Save the ladders back where the next run and the referee both read them."""
    with app_path(path).open("w", encoding="utf-8") as f:
        f.write("".join(line + "\n" for line in ladder_lines(rows)))


def write_heat_list(path: str, brackets: list[EliminatorBracket]) -> None:
    """The heat names, one per line, to paste above ``configFiles`` in the
    chronometer's group list.

    Generated rather than typed: the chronometer matches a heat by its name, and one
    character out means a heat whose start nothing reads.
    """
    with app_path(path).open("w", encoding="utf-8") as f:
        f.write("".join(name + "\n" for name in heat_names(brackets)))


# -- site document ------------------------------------------------------------

#: A heat is decided by the order its riders cross the line, so on a narrow screen
#: its time gives way after the minor columns, before the number; place and name,
#: priority 1, always stay.
_RESULT_PRIORITY = 4
#: The qualification place is what seated the rider, so it holds a narrow screen
#: longer than his team or his city but gives way before his time.
_QUAL_PRIORITY = 5


def _heat_row(
    bracket: EliminatorBracket,
    heat: Heat,
    seat: int,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> dict[str, Any]:
    """One seat as a site row: its cells keyed by column id, as the site's schema
    has them, and an empty cell left out, as the timed protocol leaves it."""
    place_text, values, result, reasons = _seat_values(bracket, heat, seat, riders, cfg)
    keys = [key for key, _label, _attr in _person_fields(cfg)]
    cells: dict[str, Any] = dict(zip(keys, values, strict=True))
    if cfg.show_place:
        cells["place"] = place_text
    if cfg.show_finish_time:
        time_text, gap_text = result
        cells["result"] = _cell(time_text, [gap_text])
    row: dict[str, Any] = {
        "cells": {key: value for key, value in cells.items() if value}
    }
    if place_text == "DNF":
        row["status"] = "dnf"
    elif place_text == "DSQ":
        row["status"] = "dsq"
    if reasons:
        # In the HTML the reasons fill the result cell; the site shows a note under
        # the row instead, always visible. Same as the timed protocol's document.
        row["note"] = "\n".join(reasons)
    return row


def _heat_section(
    bracket: EliminatorBracket,
    heat: Heat,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> dict[str, Any]:
    # The timed protocol's own columns, so the site lays a heat out as it does every
    # other table: the number stays in view beside the name, the minor columns give
    # way first on a narrow screen.
    columns = _person_columns(cfg, absolute=False)
    if cfg.show_additional_info:
        extra = _column("extra", cfg.additional_info_label, priority=_PRIORITY["extra"])
        columns.append(extra)
    if cfg.show_qualification_place:
        columns.append(
            _column("qual", cfg.qualification_place_label, priority=_QUAL_PRIORITY)
        )
    if cfg.show_finish_time:
        sub = [_plain(cfg.time_difference_label)] if cfg.show_time_difference else []
        columns.append(
            _column(
                "result",
                cfg.finish_time_label,
                role="result",
                sub_label=sub,
                priority=_RESULT_PRIORITY,
            )
        )
    rows = [
        _heat_row(bracket, heat, seat, riders, cfg)
        for seat in range(len(heat.numbers))
        if heat.numbers[seat]
    ]
    return {
        "type": "table",
        "title": _plain(_heat_heading(bracket, heat, cfg)),
        "columns": columns,
        "rows": rows,
    }


def _stage_title(bracket: EliminatorBracket, stage: int) -> str:
    """ "1/4 final" or "Final": the round, named as heat_title numbers its heats."""
    remaining = 2 ** (bracket.group.rounds - stage - 1)
    return f"1/{remaining} final" if remaining != 1 else "Final"


def _ladder_section(
    bracket: EliminatorBracket,
    riders: dict[str, StartProtocolElement],
    cfg: RaceConfig,
) -> dict[str, Any]:
    """One group's ladder: its stages in the order they are ridden, each with every
    heat it can hold -- one nobody is seated in yet too, so the site keeps the shape."""
    stages = [
        {
            "title": _plain(_stage_title(bracket, stage)),
            "sections": [
                _heat_section(bracket, heat, riders, cfg)
                for heat in bracket.heats_in_stage(stage)
            ],
        }
        for stage in range(bracket.group.rounds)
    ]
    section: dict[str, Any] = {
        "type": "ladder",
        "title": _plain(f"{cfg.group_label} {bracket.group.group_id}"),
        "sections": stages,
    }
    if _group_id(bracket.group.group_id):
        section["group"] = _group_id(bracket.group.group_id)
    return section


def build_finals_document(
    brackets: list[EliminatorBracket],
    start_list: list[StartProtocolElement],
    cfg: RaceConfig,
) -> dict[str, Any]:
    """The ladders as site data: one section of type "ladder" per group."""
    riders = _rider_index(start_list)
    groups = [
        GroupStartElement(group_id=bracket.group.group_id, seconds=0.0)
        for bracket in brackets
    ]
    ladders = [_ladder_section(bracket, riders, cfg) for bracket in brackets]
    return _document(cfg, groups, [], ladders)
