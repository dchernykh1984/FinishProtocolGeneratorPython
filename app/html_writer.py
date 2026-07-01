"""HTML protocol output (port of C++ writeGroupProtocol / writeAbsoluteProtocol)."""

from __future__ import annotations

import calendar
from io import StringIO
from pathlib import Path
from typing import TextIO

from app.config import RaceConfig
from app.models import INF, FinishProtocolElement, GroupStartElement

# ---------------------------------------------------------------------------
# time formatting
# ---------------------------------------------------------------------------


def _format_time(t: float, n_signs: int, write_date: bool = False) -> str:
    """Format a float seconds value the same way as C++ writeTimeByDouble."""
    if t > 356.0 * 24 * 3600 and not write_date:
        return "UNKNOWN"
    neg = t < 0
    if neg:
        t = -t

    n_signs = min(n_signs, 4)
    factor = 10**n_signs
    t_rounded = round(t * factor)
    frac = int(t_rounded % factor)
    t_int = int(t_rounded // factor)
    seconds = t_int % 60
    t_int //= 60
    minutes = t_int % 60
    t_int //= 60
    hours = t_int % 24
    t_int //= 24
    days = t_int

    out = "-" if neg else ""
    if days != 0:
        if write_date:
            year, month, day = 1970, 1, days + 1
            while True:
                dim = calendar.monthrange(year, month)[1]
                if day <= dim:
                    break
                day -= dim
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            out += f"{year}-{month:02d}-{day:02d} "
        else:
            out += f"{days} {'day' if days == 1 else 'days'} "
    out += f"{hours:02d}:{minutes:02d}:"
    if n_signs > 0:
        frac_str = str(frac).zfill(n_signs)
        out += f"{seconds:02d}.{frac_str}"
    else:
        out += f"{seconds:02d}"
    return out


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
    if (
        cfg.use_buttons
        and n_points > 0
        and not cfg.is_number_of_tries()
        and cfg.show_lap_times
    ) or (cfg.use_all_buttons and cfg.show_lap_times):
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
    if fp.disqualified:
        return f"<td ALIGN=center ROWSPAN={rows}>DSQ</td>\n"
    if not fp.finished:
        group_started = fp.cross_line_times[0] != 0 and fp.cross_line_times[0] != INF
        if group_started or (
            cfg.skip_first_lap_effective() and fp.cross_line_times[0] != INF
        ):
            return f"<td ALIGN=center ROWSPAN={rows}>DNF</td>\n"
        return f"<td ALIGN=center ROWSPAN={rows}>DNS</td>\n"
    return f"<td ALIGN=center ROWSPAN={rows}>{place}</td>\n"


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

    buf = StringIO()
    n_fp = len(sorted_protocol)
    _write_header(buf, cfg, n_fp, n_points)

    all_max_laps = 0
    if cfg.hide_empty_columns:
        for fp in sorted_protocol:
            all_max_laps = max(all_max_laps, fp.n_laps_finished)
    else:
        for fp in sorted_protocol:
            all_max_laps = max(all_max_laps, fp.n_laps)

    buf.write("<CENTER>")
    if (
        cfg.use_buttons
        and n_points > 0
        and not cfg.is_number_of_tries()
        and cfg.show_lap_times
    ):
        _draw_button(
            buf,
            cfg.use_buttons_label,
            "Lap ",
            " splits",
            len(group_list),
            (n_points + 1) * all_max_laps,
        )
    if cfg.use_all_buttons and cfg.show_lap_times:
        if cfg.use_buttons and n_points > 0 and not cfg.is_number_of_tries():
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

        # n_laps_group: columns to render; n_laps_configured: total laps (for multi_lap)
        n_laps_group = 0
        n_laps_configured = 0
        if cfg.hide_empty_columns:
            for fp in sorted_protocol:
                if fp.group_id == group_id:
                    if fp.n_laps_finished > n_laps_group:
                        n_laps_group = fp.n_laps_finished
                    if fp.n_laps > n_laps_configured:
                        n_laps_configured = fp.n_laps
                    if n_points > 0 and fp.n_laps_finished < fp.n_laps:
                        lp = fp.n_laps_finished
                        if lp < len(fp.control_points) and any(
                            v != -1 for v in fp.control_points[lp].segment_crosses
                        ):
                            n_laps_group = max(n_laps_group, lp + 1)
        else:
            for fp in sorted_protocol:
                if fp.group_id == group_id and fp.n_laps > n_laps_group:
                    n_laps_group = fp.n_laps
                    n_laps_configured = fp.n_laps
                    break

        multi_lap = (
            n_laps_configured > 1
            or not cfg.show_finish_time
            or (n_points > 0 and cfg.show_lap_times and not cfg.is_number_of_tries())
        )
        rows = 1 + (
            (
                (
                    1
                    if n_points > 0
                    and not cfg.is_number_of_tries()
                    and cfg.show_lap_times
                    else 0
                )
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
        if (
            n_points > 0
            and not cfg.is_number_of_tries()
            and cfg.show_lap_times
            and multi_lap
        ):
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

        for fp in sorted_protocol:
            if fp.group_id != group_id:
                continue
            if not cfg.disable_dnf and (
                fp.cross_line_times[0] == 0 or fp.cross_line_times[0] == INF
            ):
                fp.finished = False
            group_started = (
                fp.cross_line_times[0] != 0 and fp.cross_line_times[0] != INF
            )
            if not (
                (fp.finished or cfg.print_dnf)
                and (
                    fp.n_laps_finished != 0
                    or cfg.print_dns
                    or (cfg.print_dnf and group_started)
                )
                and (not fp.disqualified or cfg.print_dsq)
            ):
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
                    if fp.n_laps_finished > lc:
                        if cfg.is_number_of_tries():
                            buf.write(f"<td ALIGN=center COLSPAN={cols}>")
                            buf.write(
                                _format_time(fp.lap_times[lc], cfg.n_signs_after_point)
                            )
                            buf.write(f"<NOBR>{fp.lap_penalty[lc]}</NOBR>")
                        else:
                            buf.write(f"<td ALIGN=center COLSPAN={cols}>")
                            buf.write(
                                _format_time(fp.lap_times[lc], cfg.n_signs_after_point)
                            )
                        if fp.stages != 1 and fp.lap_finish_numbers[lc] != -1:
                            buf.write(f"({fp.lap_finish_numbers[lc]})")
                        if cfg.show_lap_finish:
                            buf.write(
                                f"<BR>{st.additional_text_style}("
                                f"{_format_time(fp.finish_lap_times[lc], cfg.n_signs_after_point)}"  # noqa: E501
                                f")</FONT>"
                            )
                        buf.write("</td>\n")
                    elif lc == fp.n_laps_finished and lc < fp.n_laps:
                        lp_crossed = lc < len(fp.control_points) and any(
                            v != -1 for v in fp.control_points[lc].segment_crosses
                        )
                        cell = "UNKNOWN" if lp_crossed else ""
                        buf.write(f"<td ALIGN=center COLSPAN={cols}>{cell}</td>\n")
                    else:
                        buf.write(f"<td ALIGN=center COLSPAN={cols}></td>\n")

            if cfg.show_finish_time:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>")
                if fp.finished and not fp.disqualified:
                    if leader is None:
                        leader = fp
                    if cfg.is_number_of_tries():
                        last_t = fp.get_total_time()
                        last_leader_t = leader.get_total_time()
                    else:
                        last_t = fp.finish_lap_times[fp.n_laps_finished - 1]
                        last_leader_t = (
                            leader.finish_lap_times[fp.n_laps_finished - 1]
                            if fp.n_laps_finished <= leader.n_laps_finished
                            else 0.0
                        )
                    if last_t > 0:
                        buf.write(_format_time(last_t, cfg.n_signs_after_point))
                        if cfg.show_time_difference and leader is not None:
                            diff = last_t - last_leader_t
                            sign = "+" if diff > 0 else ""
                            buf.write(
                                f"<BR>{st.additional_text_style}({sign}"
                                f"{_format_time(diff, cfg.n_signs_after_point)})</FONT>"
                            )
                        if cfg.show_n_finished_laps:
                            n_laps_shown = (
                                fp.get_n_successful_tries()
                                if cfg.is_number_of_tries()
                                else fp.n_laps_finished
                            )
                            buf.write(f'<BR><FONT SIZE="3">({n_laps_shown})</FONT>')
                buf.write("</td>\n")

            if cfg.show_additional_info:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.extra_info}</td>\n")
            if cfg.show_time_shift:
                buf.write(f"<td ALIGN=center ROWSPAN={rows}>")
                if cfg.skip_first_lap_effective():
                    if fp.cross_line_times[0] == INF:
                        buf.write("NOT STARTED")
                    else:
                        buf.write(
                            _format_time(
                                fp.cross_line_times[0],
                                cfg.n_signs_after_point,
                                write_date=True,
                            )
                        )
                else:
                    buf.write(_format_time(fp.start_delay, cfg.n_signs_after_point))
                buf.write("</td>\n")

            buf.write("</tr>\n")

            # use_all_buttons data sub-row
            if cfg.use_all_buttons and cfg.show_lap_times and multi_lap:
                buf.write(f'<tr style="{row_style}">')
                for j in range(n_laps_group):
                    cell_id = f'id="{group_idx}_Additional {j} Laps_{place_ctr}"'
                    if fp.n_laps_finished > j:
                        best_lap = fp.lap_times[j]
                        place_lap = 1
                        best_finish = fp.finish_lap_times[j]
                        place_finish = 1
                        for other in sorted_protocol:
                            if other.group_id != group_id or other.n_laps_finished <= j:
                                continue
                            if other.lap_times[j] < fp.lap_times[j]:
                                place_lap += 1
                                best_lap = min(best_lap, other.lap_times[j])
                            if other.finish_lap_times[j] < fp.finish_lap_times[j]:
                                place_finish += 1
                                best_finish = min(
                                    best_finish, other.finish_lap_times[j]
                                )
                        b_open = "<B>" if place_lap == 1 else ""
                        b_close = "</B>" if place_lap == 1 else ""
                        buf.write(
                            f"<td COLSPAN={cols} ROWSPAN=1 {cell_id} ALIGN=center>"
                            f'<FONT SIZE="1">{b_open}'
                        )
                        buf.write(
                            _format_time(
                                fp.lap_times[j] - best_lap, cfg.n_signs_after_point
                            )
                        )
                        buf.write(f"&nbsp({place_lap}){b_close}")
                        if cfg.show_lap_finish:
                            bf_open = "<B>" if place_finish == 1 else ""
                            bf_close = "</B>" if place_finish == 1 else ""
                            buf.write(f"<BR>{bf_open}{st.additional_info_style}")
                            buf.write(
                                _format_time(
                                    fp.finish_lap_times[j] - best_finish,
                                    cfg.n_signs_after_point,
                                )
                            )
                            buf.write(f"&nbsp({place_finish})</FONT>{bf_close}")
                        buf.write("</FONT></td>\n")
                    else:
                        buf.write(
                            f"<td COLSPAN={cols} ROWSPAN=1 {cell_id} ALIGN=center></td>\n"  # noqa: E501
                        )
                buf.write("</tr>\n")

            # CP segment sub-row (n_points+1 segments per lap)
            if (
                cfg.show_lap_times
                and multi_lap
                and n_points > 0
                and not cfg.is_number_of_tries()
            ):
                buf.write(f'<tr style="{row_style}">')
                for lc in range(n_laps_group):
                    in_progress = lc == fp.n_laps_finished and lc < fp.n_laps
                    for cp_i in range(n_points + 1):
                        cp_idx = lc * (n_points + 1) + cp_i
                        cell_id = f'id="{group_idx}_Lap {cp_idx} splits_{place_ctr}"'
                        buf.write(f"<td {cell_id} ALIGN=center>")
                        if (lc < fp.n_laps_finished or in_progress) and lc < len(
                            fp.control_points
                        ):
                            sc_val = fp.control_points[lc].segment_crosses[cp_i]
                            st_val = fp.control_points[lc].segment_times[cp_i]
                            if sc_val != -1:
                                if st_val == -2.0:
                                    buf.write("ERR")
                                else:
                                    buf.write(
                                        _format_time(st_val, cfg.n_signs_after_point)
                                    )
                            elif lc < fp.n_laps_finished or any(
                                v != -1 for v in fp.control_points[lc].segment_crosses
                            ):
                                buf.write("UNKNOWN")
                        buf.write("</td>\n")
                buf.write("</tr>\n")

        buf.write("</table>\n")

    _write_footer(buf, cfg)

    with Path(path).open("w", encoding="utf-8") as out:
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
    with Path(path).open("w", encoding="utf-8") as f:
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

    buf = StringIO()
    n_fp = len(sorted_protocol)
    _write_header(buf, cfg, n_fp, n_points)

    max_laps = 0  # columns to render
    max_laps_configured = 0  # total laps in race -- drives multi_lap
    if cfg.hide_empty_columns:
        for fp in sorted_protocol:
            max_laps = max(max_laps, fp.n_laps_finished)
            max_laps_configured = max(max_laps_configured, fp.n_laps)
    else:
        for fp in sorted_protocol:
            max_laps = max(max_laps, fp.n_laps)
        max_laps_configured = max_laps

    buf.write("<CENTER>")
    if (
        cfg.use_buttons
        and n_points > 0
        and not cfg.is_number_of_tries()
        and cfg.show_lap_times
    ):
        _draw_button(
            buf,
            cfg.use_buttons_label,
            "Lap ",
            " splits",
            1,
            (n_points + 1) * max_laps,
        )
    if cfg.use_all_buttons and cfg.show_lap_times:
        if (
            cfg.use_buttons
            and n_points > 0
            and not cfg.is_number_of_tries()
            and cfg.show_lap_times
        ):
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

    multi_lap = (
        max_laps_configured > 1
        or not cfg.show_finish_time
        or (n_points > 0 and cfg.show_lap_times and not cfg.is_number_of_tries())
    )
    rows = 1 + (
        (
            (
                1
                if n_points > 0 and not cfg.is_number_of_tries() and cfg.show_lap_times
                else 0
            )
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
    if (
        n_points > 0
        and not cfg.is_number_of_tries()
        and cfg.show_lap_times
        and multi_lap
    ):
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
        if not cfg.disable_dnf and (
            fp.cross_line_times[0] == 0 or fp.cross_line_times[0] == INF
        ):
            fp.finished = False
        group_started = fp.cross_line_times[0] != 0 and fp.cross_line_times[0] != INF
        if not (
            (fp.finished or cfg.print_dnf)
            and (
                fp.n_laps_finished != 0
                or cfg.print_dns
                or (cfg.print_dnf and group_started)
            )
            and (not fp.disqualified or cfg.print_dsq)
        ):
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
            found_gs = next((g for g in group_list if g.group_id == fp.group_id), None)
            if found_gs and not fp.disqualified and fp.finished:
                buf.write(f"({found_gs.place})")
                found_gs.place += 1
            buf.write("</NOBR></td>\n")
        if cfg.show_team:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}><NOBR>{fp.team}</NOBR></td>\n")
        if cfg.show_city:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.city}</td>\n")

        if cfg.show_lap_times and multi_lap:
            for lc in range(max_laps):
                if fp.n_laps_finished > lc:
                    if cfg.is_number_of_tries():
                        buf.write(f"<td ALIGN=center COLSPAN={cols}>")
                        buf.write(
                            _format_time(fp.lap_times[lc], cfg.n_signs_after_point)
                        )
                        buf.write(f"<NOBR>{fp.lap_penalty[lc]}</NOBR>")
                    else:
                        buf.write(f"<td ALIGN=center COLSPAN={cols}>")
                        buf.write(
                            _format_time(fp.lap_times[lc], cfg.n_signs_after_point)
                        )
                    if fp.stages != 1 and fp.lap_finish_numbers[lc] != -1:
                        buf.write(f"({fp.lap_finish_numbers[lc]})")
                    if cfg.show_lap_finish:
                        buf.write(
                            f"<BR>{st.additional_text_style}("
                            f"{_format_time(fp.finish_lap_times[lc], cfg.n_signs_after_point)}"  # noqa: E501
                            f")</FONT>"
                        )
                    buf.write("</td>\n")
                elif lc == fp.n_laps_finished and lc < fp.n_laps:
                    lp_crossed = lc < len(fp.control_points) and any(
                        v != -1 for v in fp.control_points[lc].segment_crosses
                    )
                    cell = "UNKNOWN" if lp_crossed else ""
                    buf.write(f"<td ALIGN=center COLSPAN={cols}>{cell}</td>\n")
                else:
                    buf.write(f"<td ALIGN=center COLSPAN={cols}></td>\n")

        if cfg.show_finish_time:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>")
            if fp.finished and not fp.disqualified:
                if abs_leader is None:
                    abs_leader = fp
                last_t = (
                    fp.get_total_time()
                    if cfg.is_number_of_tries()
                    else (
                        fp.finish_lap_times[fp.n_laps_finished - 1]
                        if fp.n_laps_finished > 0
                        else 0.0
                    )
                )
                last_leader_t = (
                    abs_leader.get_total_time()
                    if cfg.is_number_of_tries()
                    else (
                        abs_leader.finish_lap_times[fp.n_laps_finished - 1]
                        if fp.n_laps_finished > 0
                        and fp.n_laps_finished <= abs_leader.n_laps_finished
                        else 0.0
                    )
                )
                if last_t > 0:
                    buf.write(_format_time(last_t, cfg.n_signs_after_point))
                    if cfg.show_time_difference and abs_leader is not None:
                        diff = last_t - last_leader_t
                        sign = "+" if diff > 0 else ""
                        buf.write(
                            f"<BR>{st.additional_text_style}({sign}"
                            f"{_format_time(diff, cfg.n_signs_after_point)})</FONT>"
                        )
                    if cfg.show_n_finished_laps:
                        n_shown = (
                            fp.get_n_successful_tries()
                            if cfg.is_number_of_tries()
                            else fp.n_laps_finished
                        )
                        buf.write(f'<BR><FONT SIZE="3">({n_shown})</FONT>')
            buf.write("</td>\n")

        if cfg.show_additional_info:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>{fp.extra_info}</td>\n")
        if cfg.show_time_shift:
            buf.write(f"<td ALIGN=center ROWSPAN={rows}>")
            if cfg.skip_first_lap_effective():
                if fp.cross_line_times[0] == INF:
                    buf.write("NOT STARTED")
                else:
                    buf.write(
                        _format_time(
                            fp.cross_line_times[0],
                            cfg.n_signs_after_point,
                            write_date=True,
                        )
                    )
            else:
                buf.write(_format_time(fp.start_delay, cfg.n_signs_after_point))
            buf.write("</td>\n")

        buf.write("</tr>\n")

        # use_all_buttons data sub-row
        if cfg.use_all_buttons and cfg.show_lap_times and multi_lap:
            buf.write(f'<tr style="{row_style}">')
            for j in range(max_laps):
                cell_id = f'id="0_Additional {j} Laps_{abs_place}"'
                if fp.n_laps_finished > j:
                    best_lap = fp.lap_times[j]
                    place_lap = 1
                    best_finish = fp.finish_lap_times[j]
                    place_finish = 1
                    for other in sorted_protocol:
                        if other.n_laps_finished <= j:
                            continue
                        if other.lap_times[j] < fp.lap_times[j]:
                            place_lap += 1
                            best_lap = min(best_lap, other.lap_times[j])
                        if other.finish_lap_times[j] < fp.finish_lap_times[j]:
                            place_finish += 1
                            best_finish = min(best_finish, other.finish_lap_times[j])
                    b_open = "<B>" if place_lap == 1 else ""
                    b_close = "</B>" if place_lap == 1 else ""
                    buf.write(
                        f"<td COLSPAN={cols} ROWSPAN=1 {cell_id} ALIGN=center>"
                        f'<FONT SIZE="1">{b_open}'
                    )
                    buf.write(
                        _format_time(
                            fp.lap_times[j] - best_lap, cfg.n_signs_after_point
                        )
                    )
                    buf.write(f"&nbsp({place_lap}){b_close}")
                    if cfg.show_lap_finish:
                        bf_open = "<B>" if place_finish == 1 else ""
                        bf_close = "</B>" if place_finish == 1 else ""
                        buf.write(f"<BR>{bf_open}{st.additional_info_style}")
                        buf.write(
                            _format_time(
                                fp.finish_lap_times[j] - best_finish,
                                cfg.n_signs_after_point,
                            )
                        )
                        buf.write(f"&nbsp({place_finish})</FONT>{bf_close}")
                    buf.write("</FONT></td>\n")
                else:
                    buf.write(
                        f"<td COLSPAN={cols} ROWSPAN=1 {cell_id} ALIGN=center></td>\n"
                    )
            buf.write("</tr>\n")

        # CP segment sub-row (n_points+1 segments per lap)
        if (
            cfg.show_lap_times
            and multi_lap
            and n_points > 0
            and not cfg.is_number_of_tries()
        ):
            buf.write(f'<tr style="{row_style}">')
            for lc in range(max_laps):
                in_progress = lc == fp.n_laps_finished and lc < fp.n_laps
                for cp_i in range(n_points + 1):
                    cp_idx = lc * (n_points + 1) + cp_i
                    cell_id = f'id="0_Lap {cp_idx} splits_{abs_place}"'
                    buf.write(f"<td {cell_id} ALIGN=center>")
                    if (lc < fp.n_laps_finished or in_progress) and lc < len(
                        fp.control_points
                    ):
                        sc_val = fp.control_points[lc].segment_crosses[cp_i]
                        st_val = fp.control_points[lc].segment_times[cp_i]
                        if sc_val != -1:
                            if st_val == -2.0:
                                buf.write("ERR")
                            else:
                                buf.write(_format_time(st_val, cfg.n_signs_after_point))
                        elif lc < fp.n_laps_finished or any(
                            v != -1 for v in fp.control_points[lc].segment_crosses
                        ):
                            buf.write("UNKNOWN")
                    buf.write("</td>\n")
            buf.write("</tr>\n")

    buf.write("</table>\n")
    _write_footer(buf, cfg)

    with Path(path).open("w", encoding="utf-8") as out:
        out.write(buf.getvalue() + "\n")
