"""HTML protocol output (port of C++ writeGroupProtocol / writeAbsoluteProtocol)."""

from __future__ import annotations

import html
from io import StringIO
from typing import TextIO

from app.config import RaceConfig
from app.models import FinishProtocolElement, GroupStartElement
from app.paths import app_path
from app.protocol_rows import format_time as _format_time
from app.protocol_rows import (
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

# ---------------------------------------------------------------------------
# time formatting
# ---------------------------------------------------------------------------


def _dsq_reasons_html(fp: FinishProtocolElement) -> str:
    """Render a disqualified competitor's DSQ reasons as "<where>: <reason>" lines.

    Each reason is HTML-escaped (it is free referee text) and the entries are joined
    with ``<BR>`` so they stack inside the finish-time cell.
    """
    return "<BR>".join(html.escape(entry) for entry in fp.dsq_reasons)


# ---------------------------------------------------------------------------
# header / footer
# ---------------------------------------------------------------------------


def _write_header(
    f: TextIO, cfg: RaceConfig, n_competitors: int, n_points: int
) -> None:
    f.write("<head>")
    f.write("<title>Protocol")
    if cfg.race_name:
        f.write(f" {cfg.race_name}")
    f.write("</title>")
    f.write('<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n')

    # JS for collapsible columns
    if (cfg.use_buttons and n_points > 0 and cfg.show_lap_times) or (
        cfg.use_all_buttons and cfg.show_lap_times
    ):
        f.write(
            f"<script>\ndoShow = 0;\n"
            f"function showhideall(table, col, isFirst) {{\n"
            f"  if(isFirst != 0) {{\n"
            f"    if(document.getElementById(table + '_' + col + '_' + 0) != null) {{\n"
            f"    if(document.getElementById(table + '_' + col + '_' + 0).style.display == 'none') {{\n"  # noqa: E501
            f"      doShow = 1;\n"
            f"    }} else {{\n"
            f"      doShow = 0;\n"
            f"    }}\n}}\n  }}\n"
            f"  if(doShow != 0) {{ show(table, col); }} else {{ hide(table, col); }}\n}}\n"  # noqa: E501
            f"function showhide(table, col) {{\n"
            f"  if(document.getElementById(table + '_' + col + '_' + 0).style.display == 'none') {{\n"  # noqa: E501
            f"    show(table, col);\n  }} else {{ hide(table, col); }}\n}}\n"
            f"function show(table, col) {{\n"
            f"  for(i=0;i<{n_competitors + 1};i++) {{\n"
            f"    if(document.getElementById(table + '_' + col + '_' + i) != null)\n"
            f"      document.getElementById(table + '_' + col + '_' + i).style.display = 'table-cell';\n"  # noqa: E501
            f"  }}\n}}\n"
            f"function hide(table, col) {{\n"
            f"  for(i=0;i<{n_competitors + 1};i++) {{\n"
            f"    if(document.getElementById(table + '_' + col + '_' + i) != null)\n"
            f"      document.getElementById(table + '_' + col + '_' + i).style.display = 'none';\n"  # noqa: E501
            f"  }}\n}}\n</script>\n"
        )

    if cfg.styles.common_style_text:
        f.write(f"<style>\n{cfg.styles.common_style_text}\n</style>")
    f.write("</head>\n")

    if cfg.sponsor:
        f.write(f"<CENTER>{cfg.sponsor}</CENTER>")
    s = cfg.styles.top_text_style
    if cfg.race_name:
        f.write(f"{s}<B><CENTER>{cfg.race_name}</CENTER></B></FONT><BR>")
    if cfg.race_date and cfg.race_place:
        f.write(
            f"{s}<B><CENTER>{cfg.race_date}, {cfg.race_place}</CENTER></B></FONT><BR>"
        )
    if cfg.track_conditions:
        f.write(
            f"{s}<B><CENTER>{cfg.track_conditions_label}: {cfg.track_conditions}</CENTER></B></FONT><BR>"  # noqa: E501
        )
    if cfg.weather:
        f.write(
            f"{s}<B><CENTER>{cfg.weather_label}: {cfg.weather}</CENTER></B></FONT><BR>"
        )


def _write_footer(f: TextIO, cfg: RaceConfig) -> None:
    if cfg.organizer:
        f.write(
            f'<FONT SIZE="3" COLOR=""><B><p align="right">{cfg.organizer_label}: {cfg.organizer}</p></B></FONT>\n'  # noqa: E501
        )
    if cfg.main_referee:
        f.write(
            f'<FONT SIZE="3" COLOR=""><B><p align="right">{cfg.referee_label}: {cfg.main_referee}</p></B></FONT>'  # noqa: E501
        )
    if cfg.additional_referee:
        f.write(
            f'<FONT SIZE="3" COLOR=""><B><p align="right">{cfg.secretary_label}: {cfg.additional_referee}</p></B></FONT>'  # noqa: E501
        )
    f.write('<p align="left">\n')
    f.write("</p>\n")
    if cfg.bottom_text:
        f.write(cfg.bottom_text)


def _place_label(
    fp: FinishProtocolElement, place: int, rows: int, cfg: RaceConfig
) -> str:
    text, _status = place_status(fp, place, cfg)
    return f"<td ALIGN=center ROWSPAN={rows}>{text}</td>\n"


def _lap_cell(fp: FinishProtocolElement, lc: int, cfg: RaceConfig, cols: int) -> str:
    parts = lap_parts(fp, lc, cfg)
    out = f"<td ALIGN=center COLSPAN={cols}>"
    if parts.state != "done":
        return f"{out}{parts.text}</td>\n"
    if cfg.is_number_of_tries():
        out += f"<B>{parts.text}</B>" if parts.strong else parts.text
        out += f"<NOBR>{fp.lap_penalty[lc]}</NOBR>"
    else:
        out += parts.text
    out += parts.finish_number
    if parts.finish_time:
        out += f"<BR>{cfg.styles.additional_text_style}{parts.finish_time}</FONT>"
    return out + "</td>\n"


def _result_cell(
    fp: FinishProtocolElement,
    leader: FinishProtocolElement | None,
    cfg: RaceConfig,
    rows: int,
) -> str:
    out = f"<td ALIGN=center ROWSPAN={rows}>"
    parts = result_parts(fp, leader, cfg)
    if parts.time:
        out += parts.time
        if parts.gap:
            out += f"<BR>{cfg.styles.additional_text_style}{parts.gap}</FONT>"
        if parts.count:
            out += f'<BR><FONT SIZE="3">{parts.count}</FONT>'
    elif fp.disqualified and fp.dsq_reasons:
        out += _dsq_reasons_html(fp)
    return out + "</td>\n"


def _lap_ranks_cell(
    fp: FinishProtocolElement,
    j: int,
    peers: list[FinishProtocolElement],
    cfg: RaceConfig,
    cols: int,
    cell_id: str,
) -> str:
    st = cfg.styles
    ranks = lap_ranks(fp, j, peers)
    if ranks is None:
        return f"<td COLSPAN={cols} ROWSPAN=1 {cell_id} ALIGN=center></td>\n"
    b_open = "<B>" if ranks.place_lap == 1 else ""
    b_close = "</B>" if ranks.place_lap == 1 else ""
    out = f'<td COLSPAN={cols} ROWSPAN=1 {cell_id} ALIGN=center><FONT SIZE="1">{b_open}'
    out += _format_time(ranks.gap_lap, cfg.n_signs_after_point)
    out += f"&nbsp({ranks.place_lap}){b_close}"
    if cfg.show_lap_finish:
        bf_open = "<B>" if ranks.place_finish == 1 else ""
        bf_close = "</B>" if ranks.place_finish == 1 else ""
        out += f"<BR>{bf_open}{st.additional_info_style}"
        out += _format_time(ranks.gap_finish, cfg.n_signs_after_point)
        out += f"&nbsp({ranks.place_finish})</FONT>{bf_close}"
    return out + "</FONT></td>\n"


def _id_cell(fp: FinishProtocolElement, rows: int) -> str:
    out = f"<td ALIGN=center ROWSPAN={rows}><NOBR>{fp.competitor_id}"
    if fp.stages != 1:
        for i in range(1, fp.stages):
            out += f"<BR>{fp.number + i}"
    out += "</NOBR></td>\n"
    return out


def _draw_button(
    buf: StringIO,
    button_name: str,
    text_before: str,
    text_after: str,
    n_groups: int,
    n_cols: int,
) -> None:
    buf.write('<button type="submit" name="Submit" onclick="')
    first = True
    for g in range(n_groups):
        for cp in range(n_cols):
            if not first:
                buf.write(",")
            buf.write(f"showhideall({g}, '{text_before}{cp}{text_after}', 1)")
            first = False
    buf.write(f'" ><FONT SIZE="2"><B><I>{button_name}</I></B></FONT></button>')


# ---------------------------------------------------------------------------
# group protocol
# ---------------------------------------------------------------------------


def write_group_protocol(  # noqa: C901
    path: str,
    sorted_protocol: list[FinishProtocolElement],
    group_list: list[GroupStartElement],
    cfg: RaceConfig,
    n_points: int = 0,
) -> None:
    st = cfg.styles
    cols = n_points + 1
    prepare_statuses(sorted_protocol, cfg)

    buf = StringIO()
    n_fp = len(sorted_protocol)
    _write_header(buf, cfg, n_fp, n_points)

    all_max_laps = 0
    if cfg.hide_empty_columns:
        for fp in sorted_protocol:
            all_max_laps = max(all_max_laps, fp.visible_laps())
    else:
        for fp in sorted_protocol:
            all_max_laps = max(all_max_laps, fp.n_laps)

    buf.write("<CENTER>")
    if cfg.use_buttons and n_points > 0 and cfg.show_lap_times:
        _draw_button(
            buf,
            cfg.use_buttons_label,
            "Lap ",
            " splits",
            len(group_list),
            (n_points + 1) * all_max_laps,
        )
    if cfg.use_all_buttons and cfg.show_lap_times:
        if cfg.use_buttons and n_points > 0:
            buf.write("&nbsp;&nbsp;")
        _draw_button(
            buf,
            cfg.use_all_buttons_label,
            "Additional ",
            " Laps",
            len(group_list),
            all_max_laps,
        )
    buf.write("</CENTER>")

    for group_idx, gs in enumerate(group_list):
        group_id = gs.group_id

        n_laps_group, multi_lap = laps_to_show(sorted_protocol, group_id, cfg, n_points)
        rows = 1 + (
            (
                (1 if n_points > 0 and cfg.show_lap_times else 0)
                + (1 if cfg.use_all_buttons and cfg.show_lap_times else 0)
            )
            if multi_lap
            else 0
        )

        gns = st.group_name_style
        ts = st.table_style
        buf.write(
            f"<BR>{gns}<B><CENTER><U>{cfg.group_label} {group_id}</U></CENTER></B></FONT>"  # noqa: E501
            f'<BR><table style="{ts}"'
        )
        if cfg.stretch:
            buf.write(" width=100%")
        buf.write(" border=0>")
        buf.write(f'<tr style="{st.top_line_style}">')

        if cfg.show_place:
            buf.write(
                f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.place_label}</B></td>\n"
            )
        if cfg.show_id:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.id_label}</B></td>\n")
        if cfg.show_name:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.name_label}</B></td>\n")
        if cfg.show_age:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.age_label}</B></td>\n")
        if cfg.show_team:
            buf.write(
                f"<td ALIGN=center ROWSPAN={rows}><B><NOBR>{cfg.team_label}</NOBR></B></td>\n"  # noqa: E501
            )
        if cfg.show_city:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.city_label}</B></td>\n")
        if cfg.show_lap_times and multi_lap:
            for j in range(n_laps_group):
                buf.write(f"<td ALIGN=center COLSPAN={cols}>")
                buf.write(f"<B>{cfg.lap_name} {j + 1}")
                if cfg.show_lap_finish:
                    buf.write(
                        f"<BR>{st.additional_text_top_style}"
                        f"{cfg.lap_additional_info}</FONT>"
                    )
                buf.write("</B></td>\n")
        if cfg.show_finish_time:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>")
            buf.write(f"<B><NOBR>{cfg.finish_time_label}<BR>")
            if cfg.show_time_difference:
                buf.write(
                    f"{st.additional_text_top_style}"
                    f"{cfg.time_difference_label}</FONT></NOBR><BR>"
                )
            if cfg.show_n_finished_laps:
                buf.write(f'<FONT SIZE="3">{cfg.n_finished_laps_label}</FONT>')
            buf.write("</B></td>\n")
        if cfg.show_additional_info:
            buf.write(
                f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.additional_info_label}</B></td>\n"  # noqa: E501
            )
        if cfg.show_time_shift:
            buf.write(
                f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.time_shift_label}</B></td>\n"
            )
        buf.write("</tr>\n")

        # use_all_buttons sub-header row
        if cfg.use_all_buttons and cfg.show_lap_times and multi_lap:
            buf.write(f'<tr style="{st.top_line_style}">')
            for j in range(n_laps_group):
                buf.write(
                    f'<td COLSPAN={cols} ROWSPAN=1 id="{group_idx}_Additional {j} Laps_0"'  # noqa: E501
                    f" ALIGN=center>"
                    f'<FONT SIZE="1"><B>{cfg.lap_rank_label}'
                )
                if cfg.show_lap_finish:
                    buf.write(
                        f"<BR>{st.additional_info_top_style}"
                        f"{cfg.lap_finish_rank_label}</FONT>"
                    )
                buf.write("</FONT></B></FONT></td>\n")
            buf.write("</tr>\n")

        # CP sub-header row (one cell per control point per lap)
        if n_points > 0 and cfg.show_lap_times and multi_lap:
            buf.write(f'<tr style="{st.top_line_style}">')
            for j in range(n_laps_group):
                for cp_i in range(n_points + 1):
                    idx = cp_i + j * (n_points + 1)
                    buf.write(
                        f'<td ROWSPAN=1 id="{group_idx}_Lap {idx} splits_0"'
                        f" ALIGN=center>"
                        f'<FONT SIZE="1"><B><NOBR>({cp_i + 1} split)</NOBR></B></FONT></td>\n'  # noqa: E501
                    )
            buf.write("</tr>\n")

        leader: FinishProtocolElement | None = None
        place_ctr = 0
        members = [fp for fp in sorted_protocol if fp.group_id == group_id]

        for fp in sorted_protocol:
            if fp.group_id != group_id:
                continue
            if not is_printed(fp, cfg):
                continue

            place_ctr += 1
            row_style = st.odd_line_style if place_ctr % 2 == 0 else st.even_line_style
            buf.write(f'<tr style="{row_style}">')

            if cfg.show_place:
                buf.write(_place_label(fp, place_ctr, rows, cfg))
            if cfg.show_id:
                buf.write(_id_cell(fp, rows))
            if cfg.show_name:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.name}</td>\n")
            if cfg.show_age:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.year_of_birth}</td>\n")
            if cfg.show_team:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.team}</td>\n")
            if cfg.show_city:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.city}</td>\n")

            if cfg.show_lap_times and multi_lap:
                for lc in range(n_laps_group):
                    buf.write(_lap_cell(fp, lc, cfg, cols))

            if cfg.show_finish_time:
                if fp.finished and not fp.disqualified and leader is None:
                    leader = fp
                buf.write(_result_cell(fp, leader, cfg, rows))

            if cfg.show_additional_info:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.extra_info}</td>\n")
            if cfg.show_time_shift:
                buf.write(
                    f"<td ALIGN=center ROWSPAN={rows}>{time_shift_text(fp, cfg)}</td>\n"
                )

            buf.write("</tr>\n")

            # use_all_buttons data sub-row
            if cfg.use_all_buttons and cfg.show_lap_times and multi_lap:
                buf.write(f'<tr style="{row_style}">')
                for j in range(n_laps_group):
                    cell_id = f'id="{group_idx}_Additional {j} Laps_{place_ctr}"'
                    buf.write(_lap_ranks_cell(fp, j, members, cfg, cols, cell_id))
                buf.write("</tr>\n")

            # CP segment sub-row (n_points+1 segments per lap)
            if cfg.show_lap_times and multi_lap and n_points > 0:
                buf.write(f'<tr style="{row_style}">')
                for lc in range(n_laps_group):
                    for cp_i in range(n_points + 1):
                        cp_idx = lc * (n_points + 1) + cp_i
                        cell_id = f'id="{group_idx}_Lap {cp_idx} splits_{place_ctr}"'
                        text = split_text(fp, lc, cp_i, cfg)
                        buf.write(f"<td {cell_id} ALIGN=center>{text}</td>\n")
                buf.write("</tr>\n")

        buf.write("</table>\n")

    _write_footer(buf, cfg)

    with app_path(path).open("w", encoding="utf-8") as out:
        out.write(buf.getvalue() + "\n")

    if cfg.generate_text_protocol_effective():
        txt_path = path + ".txt"
        _write_text_group_protocol(txt_path, sorted_protocol, group_list, cfg)


def _write_text_group_protocol(
    path: str,
    sorted_protocol: list[FinishProtocolElement],
    group_list: list[GroupStartElement],
    cfg: RaceConfig,
) -> None:
    lines: list[str] = []
    for gs in group_list:
        group_id = gs.group_id
        place_ctr = 0
        for fp in sorted_protocol:
            if fp.group_id != group_id:
                continue
            if not fp.finished or fp.disqualified:
                continue
            place_ctr += 1
            lines.append(
                f"{fp.competitor_id}#{fp.name}#{fp.group_id}#{fp.n_laps}"
                f"#{fp.stages}#{fp.year_of_birth}#{fp.team}#{fp.city}"
                f"#{fp.extra_info}#{place_ctr}#"
            )
    with app_path(path).open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# absolute protocol
# ---------------------------------------------------------------------------


def write_absolute_protocol(  # noqa: C901
    path: str,
    sorted_protocol: list[FinishProtocolElement],
    group_list: list[GroupStartElement],
    cfg: RaceConfig,
    n_points: int = 0,
) -> None:
    st = cfg.styles
    cols = n_points + 1
    prepare_statuses(sorted_protocol, cfg)
    places = group_places(sorted_protocol, group_list, cfg)

    buf = StringIO()
    n_fp = len(sorted_protocol)
    _write_header(buf, cfg, n_fp, n_points)

    max_laps, multi_lap = laps_to_show(sorted_protocol, None, cfg, n_points)

    buf.write("<CENTER>")
    if cfg.use_buttons and n_points > 0 and cfg.show_lap_times:
        _draw_button(
            buf,
            cfg.use_buttons_label,
            "Lap ",
            " splits",
            1,
            (n_points + 1) * max_laps,
        )
    if cfg.use_all_buttons and cfg.show_lap_times:
        if cfg.use_buttons and n_points > 0 and cfg.show_lap_times:
            buf.write("&nbsp;&nbsp;")
        _draw_button(
            buf,
            cfg.use_all_buttons_label,
            "Additional ",
            " Laps",
            1,
            max_laps,
        )
    buf.write("</CENTER>")

    rows = 1 + (
        (
            (1 if n_points > 0 and cfg.show_lap_times else 0)
            + (1 if cfg.use_all_buttons and cfg.show_lap_times else 0)
        )
        if multi_lap
        else 0
    )

    gns = st.group_name_style
    ts = st.table_style
    buf.write(
        f"<BR>{gns}<B><CENTER><U>{cfg.overall_results_label}</U></CENTER></B></FONT>"
        f'<BR><table style="{ts}"'
    )
    if cfg.stretch:
        buf.write(" width=100%")
    buf.write(" border=0>")
    buf.write(f'<tr style="{st.top_line_style}">')

    if cfg.show_place:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.place_label}</B></td>\n")
    if cfg.show_id:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.id_label}</B></td>\n")
    if cfg.show_name:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.name_label}</B></td>\n")
    if cfg.show_age:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.age_label}</B></td>\n")
    if cfg.show_group:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.group_label}</B></td>\n")
    if cfg.show_team:
        buf.write(
            f"<td ALIGN=center ROWSPAN={rows}><B><NOBR>{cfg.team_label}</NOBR></B></td>\n"  # noqa: E501
        )
    if cfg.show_city:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.city_label}</B></td>\n")
    if cfg.show_lap_times and multi_lap:
        for j in range(max_laps):
            buf.write(f"<td ALIGN=center COLSPAN={cols}>")
            buf.write(f"<B>{cfg.lap_name} {j + 1}")
            if cfg.show_lap_finish:
                buf.write(
                    f"<BR>{st.additional_text_top_style}{cfg.lap_additional_info}</FONT>"
                )
            buf.write("</B></td>\n")
    if cfg.show_finish_time:
        buf.write(f"<td ALIGN=center ROWSPAN={rows}>")
        buf.write(f"<B>{cfg.finish_time_label}<BR>")
        if cfg.show_time_difference:
            buf.write(
                f"{st.additional_text_top_style}{cfg.time_difference_label}</FONT></B>"
            )
        if cfg.show_n_finished_laps:
            prefix = "<BR>" if cfg.show_time_difference else ""
            buf.write(f'{prefix}<FONT SIZE="3">{cfg.n_finished_laps_label}</FONT>')
        buf.write("</B></td>\n")
    if cfg.show_additional_info:
        buf.write(
            f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.additional_info_label}</B></td>\n"
        )
    if cfg.show_time_shift:
        buf.write(
            f"<td ALIGN=center ROWSPAN={rows}><B>{cfg.time_shift_label}</B></td>\n"
        )
    buf.write("</tr>\n")

    # use_all_buttons sub-header row
    if cfg.use_all_buttons and cfg.show_lap_times and multi_lap:
        buf.write(f'<tr style="{st.top_line_style}">')
        for j in range(max_laps):
            buf.write(
                f'<td COLSPAN={cols} id="0_Additional {j} Laps_0" ALIGN=center>'
                f'<FONT SIZE="1"><B>{cfg.lap_rank_label}'
            )
            if cfg.show_lap_finish:
                buf.write(
                    f"<BR>{st.additional_info_top_style}"
                    f"{cfg.lap_finish_rank_label}</FONT>"
                )
            buf.write("</FONT></B></FONT></td>\n")
        buf.write("</tr>\n")

    # CP sub-header row
    if n_points > 0 and cfg.show_lap_times and multi_lap:
        buf.write(f'<tr style="{st.top_line_style}">')
        for j in range(max_laps):
            for cp_i in range(n_points + 1):
                idx = cp_i + j * (n_points + 1)
                buf.write(
                    f'<td id="0_Lap {idx} splits_0" ALIGN=center>'
                    f'<FONT SIZE="1"><B><NOBR>({cp_i + 1} split)</NOBR></B></FONT></td>\n'  # noqa: E501
                )
        buf.write("</tr>\n")

    abs_leader: FinishProtocolElement | None = None
    abs_place = 0

    for fp in sorted_protocol:
        if not is_printed(fp, cfg):
            continue
        abs_place += 1
        row_style = st.odd_line_style if abs_place % 2 == 0 else st.even_line_style
        buf.write(f'<tr style="{row_style}">')

        if cfg.show_place:
            buf.write(_place_label(fp, abs_place, rows, cfg))
        if cfg.show_id:
            buf.write(_id_cell(fp, rows))
        if cfg.show_name:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.name}</td>\n")
        if cfg.show_age:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.year_of_birth}</td>\n")
        if cfg.show_group:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><NOBR>{fp.group_id}")
            if id(fp) in places:
                buf.write(f"({places[id(fp)]})")
            buf.write("</NOBR></td>\n")
        if cfg.show_team:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><NOBR>{fp.team}</NOBR></td>\n")
        if cfg.show_city:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.city}</td>\n")

        if cfg.show_lap_times and multi_lap:
            for lc in range(max_laps):
                buf.write(_lap_cell(fp, lc, cfg, cols))

        if cfg.show_finish_time:
            if fp.finished and not fp.disqualified and abs_leader is None:
                abs_leader = fp
            buf.write(_result_cell(fp, abs_leader, cfg, rows))

        if cfg.show_additional_info:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.extra_info}</td>\n")
        if cfg.show_time_shift:
            buf.write(
                f"<td ALIGN=center ROWSPAN={rows}>{time_shift_text(fp, cfg)}</td>\n"
            )
        buf.write("</tr>\n")

        # use_all_buttons data sub-row
        if cfg.use_all_buttons and cfg.show_lap_times and multi_lap:
            buf.write(f'<tr style="{row_style}">')
            for j in range(max_laps):
                cell_id = f'id="0_Additional {j} Laps_{abs_place}"'
                buf.write(_lap_ranks_cell(fp, j, sorted_protocol, cfg, cols, cell_id))
            buf.write("</tr>\n")

        # CP segment sub-row
        if cfg.show_lap_times and multi_lap and n_points > 0:
            buf.write(f'<tr style="{row_style}">')
            for lc in range(max_laps):
                for cp_i in range(n_points + 1):
                    cp_idx = lc * (n_points + 1) + cp_i
                    cell_id = f'id="0_Lap {cp_idx} splits_{abs_place}"'
                    text = split_text(fp, lc, cp_i, cfg)
                    buf.write(f"<td {cell_id} ALIGN=center>{text}</td>\n")
            buf.write("</tr>\n")

    buf.write("</table>\n")
    _write_footer(buf, cfg)

    with app_path(path).open("w", encoding="utf-8") as out:
        out.write(buf.getvalue() + "\n")
