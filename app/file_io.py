"""File reading helpers for protocol input files."""

from __future__ import annotations

from pathlib import Path

from app.config import HtmlStyles
from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
)


def _read_lines(path: str) -> list[str]:
    """Read non-empty lines from a text file (auto-detect encoding)."""
    p = Path(path)
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            text = p.read_text(encoding=enc)
            return [ln for ln in text.splitlines() if ln.strip()]
        except UnicodeDecodeError:
            continue
    return []


def _read_all_lines(path: str) -> list[str]:
    """Read all lines (including empty) from a text file (auto-detect encoding)."""
    p = Path(path)
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return p.read_text(encoding=enc).splitlines()
        except UnicodeDecodeError:
            continue
    return []


_TEMPLATE_FIELDS = (
    "table_style",
    "top_line_style",
    "even_line_style",
    "odd_line_style",
    "group_name_style",
    "additional_text_top_style",
    "additional_text_style",
    "top_text_style",
    "additional_info_top_style",
    "additional_info_style",
    "common_style_text",
)


def load_template(path: str) -> HtmlStyles | None:
    """Load an HTML styles template file (C++ positional format, 11 lines)."""
    p = Path(path)
    lines: list[str] = []
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            lines = p.read_text(encoding=enc).splitlines()
            break
        except UnicodeDecodeError, OSError:
            continue
    else:
        return None
    while len(lines) < len(_TEMPLATE_FIELDS):
        lines.append("")
    st = HtmlStyles()
    for field, value in zip(_TEMPLATE_FIELDS, lines, strict=False):
        setattr(st, field, value)
    return st


def read_start_protocol(
    path: str, skip_first_lap: bool = False
) -> list[StartProtocolElement]:
    return [
        StartProtocolElement.from_line(ln, skip_first_lap=skip_first_lap)
        for ln in _read_lines(path)
    ]


def read_group_times(path: str) -> list[GroupStartElement]:
    return [GroupStartElement.from_line(ln) for ln in _read_lines(path)]


def read_finish_times(path: str) -> list[FinishCompetitorElement]:
    return [FinishCompetitorElement.from_line(ln) for ln in _read_lines(path)]


# Maps C++ comboBoxRaceType display strings to Python internal race type constants.
_CPP_RACE_TYPE_MAP: dict[str, str] = {
    "Mass Start or Splitted Start": "Mass/Splitted",
    "Mass Start or Splitted Start with Spiridonov's coefficients": (
        "Mass/Splitted (Spiridonov)"
    ),
}


def load_config_file(path: str) -> dict[str, str]:  # noqa: C901
    """Load a C++ fpg_info.txt race-info config file into a key-value dict.

    Mirrors the C++ buttonLoadRaceInfoData_Click sequential positional format.
    All lines (including empty) are preserved so that empty FTP/path fields
    don't cause mis-alignment.
    """
    lines = _read_all_lines(path)
    it = iter(lines)
    result: dict[str, str] = {}

    def nxt() -> str | None:
        return next(it, None)

    # 13 fixed positional fields
    fixed_keys = (
        "sponsor",
        "race_name",
        "race_date",
        "race_place",
        "weather",
        "main_referee",
        "additional_referee",
        "organizer",
        "track_conditions",
        "minimal_time_for_lap",
        "time_limit",
        "n_signs_after_point",
        "race_type",
    )
    for key in fixed_keys:
        v = nxt()
        if v is None:
            return result
        result[key] = v

    if result.get("race_type") in _CPP_RACE_TYPE_MAP:
        result["race_type"] = _CPP_RACE_TYPE_MAP[result["race_type"]]

    # optional "Info" block
    tok = nxt()
    if tok is None:
        return result
    if tok == "Info":
        result["show_additional_info"] = "1"
        v = nxt()
        if v is not None:
            result["additional_info_label"] = v
        tok = nxt()
        if tok is None:
            return result

    # optional "RefreshProtocol" block
    # C++ stores timerRefresh->Interval directly (milliseconds); convert to seconds.
    if tok == "RefreshProtocol":
        result["auto_refresh_enabled"] = "1"
        v = nxt()
        if v is not None:
            try:
                result["auto_refresh_interval"] = str(int(v) // 1000)
            except ValueError:
                result["auto_refresh_interval"] = v
        tok = nxt()
        if tok is None:
            return result

    # always: referee_label, secretary_label
    result["referee_label"] = tok
    tok = nxt()
    if tok is None:
        return result
    result["secretary_label"] = tok

    # optional column tags
    tok = nxt()
    if tok is None:
        return result

    if tok == "ID":
        result["show_id"] = "1"
        v = nxt()
        if v is not None:
            result["id_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "Name":
        result["show_name"] = "1"
        v = nxt()
        if v is not None:
            result["name_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "Age":
        result["show_age"] = "1"
        v = nxt()
        if v is not None:
            result["age_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "Team":
        result["show_team"] = "1"
        v = nxt()
        if v is not None:
            result["team_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "City":
        result["show_city"] = "1"
        v = nxt()
        if v is not None:
            result["city_label"] = v
        tok = nxt()
        if tok is None:
            return result

    # optional "Laps" block
    if tok == "Laps":
        result["show_lap_times"] = "1"
        tok = nxt()
        if tok is None:
            return result
        if tok == "Lap Name":
            v = nxt()
            if v is not None:
                result["lap_name"] = v
            tok = nxt()
            if tok is None:
                return result
        if tok == "Lap Finish Info":
            v = nxt()
            if v is not None:
                result["lap_additional_info"] = v
            tok = nxt()
            if tok is None:
                return result
        if tok == "Lap Finish":
            result["show_lap_finish"] = "1"
            tok = nxt()
            if tok is None:
                return result
        if tok == "Hide Empty Columns":
            result["hide_empty_columns"] = "1"
            tok = nxt()
            if tok is None:
                return result

    # optional "Buttons" / "All Buttons"
    if tok == "Buttons":
        result["use_buttons"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "All Buttons":
        result["use_all_buttons"] = "1"
        tok = nxt()
        if tok is None:
            return result

    # optional "UploadGroups" / "UploadAbsolute"
    if tok == "UploadGroups":
        result["upload_groups"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "UploadAbsolute":
        result["upload_absolute"] = "1"
        tok = nxt()
        if tok is None:
            return result

    # always: 4 action values (current tok is start_list_action)
    result["start_list_action"] = tok
    for key in ("group_times_action", "result_times_action", "remote_points_action"):
        v = nxt()
        if v is None:
            return result
        result[key] = v

    # always: 3 FTP values (may be empty lines)
    for key in ("ftp_path", "ftp_login", "ftp_password"):
        v = nxt()
        if v is None:
            return result
        result[key] = v

    tok = nxt()
    if tok is None:
        return result

    # optional "Finish" block
    if tok == "Finish":
        result["show_finish_time"] = "1"
        tok = nxt()
        if tok is None:
            return result
        if tok == "Time Difference":
            result["show_time_difference"] = "1"
            tok = nxt()
            if tok is None:
                return result
        if tok == "Number Of Laps Finished":
            result["show_n_finished_laps"] = "1"
            tok = nxt()
            if tok is None:
                return result
    # optional "Group" block
    if tok == "Group":
        result["show_group"] = "1"
        v = nxt()
        if v is not None:
            result["group_label"] = v
        tok = nxt()
        if tok is None:
            return result

    # optional "Place" block
    if tok == "Place":
        result["show_place"] = "1"
        v = nxt()
        if v is not None:
            result["place_label"] = v
        tok = nxt()
        if tok is None:
            return result

    # optional "TimeShift" block
    if tok == "TimeShift":
        result["show_time_shift"] = "1"
        v = nxt()
        if v is not None:
            result["time_shift_label"] = v
        tok = nxt()
        if tok is None:
            return result

    # optional flags (Stratch is a preserved C++ typo for "Stretch")
    if tok == "Stratch":
        result["stretch"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Print DNF":
        result["print_dnf"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Print DNS":
        result["print_dns"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Print DSQ":
        result["print_dsq"] = "1"
        tok = nxt()
        if tok is None:
            return result

    # always: 5 file paths (current tok is start_protocol_file)
    result["start_protocol_file"] = tok
    for key in (
        "group_time_file",
        "finish_time_file",
        "group_protocol_file",
        "absolute_protocol_file",
    ):
        v = nxt()
        if v is None:
            return result
        result[key] = v

    # always: remote points path and count
    for key in ("remote_points_path", "n_remote_points"):
        v = nxt()
        if v is None:
            return result
        result[key] = v

    tok = nxt()
    if tok is None:
        return result

    # optional disable flags and logger options
    if tok == "Disable DNF":
        result["disable_dnf"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Disable DSQ":
        result["disable_dsq"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Use File Logger":
        result["use_file_logger"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Use Interface Logger":
        result["use_interface_logger"] = "1"
        tok = nxt()
        if tok is None:
            return result

    if tok == "Err and Wrn only":
        result["errors_warnings_only"] = "1"
        tok = nxt()
        if tok is None:
            return result

    # optional "Laps Difference Erroros" (preserved C++ typo)
    if tok == "Laps Difference Erroros":
        result["check_laps_difference"] = "1"
        v = nxt()
        if v is not None:
            result["laps_difference_pct"] = v
        tok = nxt()
        if tok is None:
            return result

    # optional "UseStartCheckList" block
    # C++ stores: action (None/Download/Merge/Merge+Remove), then registration period.
    # The file path is hardcoded in C++ as temp\results_start.txt; mirror that default.
    if tok == "UseStartCheckList":
        result["use_start_check_list"] = "1"
        result["start_check_list_file"] = "temp/results_start.txt"
        v = nxt()
        if v is not None:
            result["start_check_list_action"] = v
        v = nxt()
        if v is not None:
            result["start_registration_period"] = v
        tok = nxt()
        if tok is None:
            return result

    # always: bottom_text (last C++ field)
    result["bottom_text"] = tok

    # Python-only label extensions (after bottom_text so C++ ignores them)
    tok = nxt()
    if tok is None:
        return result
    if tok == "FinishTimeLabel":
        v = nxt()
        if v is not None:
            result["finish_time_label"] = v
        tok = nxt()
        if tok is None:
            return result
    if tok == "TimeDifferenceLabel":
        v = nxt()
        if v is not None:
            result["time_difference_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "NFinishedLapsLabel":
        v = nxt()
        if v is not None:
            result["n_finished_laps_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "TemplateFile":
        v = nxt()
        if v is not None:
            result["template_file"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "ButtonsLabel":
        v = nxt()
        if v is not None:
            result["use_buttons_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "AllButtonsLabel":
        v = nxt()
        if v is not None:
            result["use_all_buttons_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "LapRankLabel":
        v = nxt()
        if v is not None:
            result["lap_rank_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "LapFinishRankLabel":
        v = nxt()
        if v is not None:
            result["lap_finish_rank_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "WeatherLabel":
        v = nxt()
        if v is not None:
            result["weather_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "TrackLabel":
        v = nxt()
        if v is not None:
            result["track_conditions_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "OrganizerLabel":
        v = nxt()
        if v is not None:
            result["organizer_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "OverallResultsLabel":
        v = nxt()
        if v is not None:
            result["overall_results_label"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpSiteUrl":
        v = nxt()
        if v is not None:
            result["http_site_url"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpUploadToken":
        v = nxt()
        if v is not None:
            result["http_upload_token"] = v
        tok = nxt()
        if tok is None:
            return result

    # Per-stream "local vs site" sources, in the order saved by _save_race_info_to_path
    # (right after HttpUploadToken). Old files lack these tags, so each block is skipped
    # when the current token doesn't match.
    for save_tag, key in (
        ("StartListSource", "start_list_source"),
        ("GroupTimesSource", "group_times_source"),
        ("FinishTimesSource", "finish_times_source"),
        ("RemotePointsSource", "remote_points_source"),
    ):
        if tok == save_tag:
            v = nxt()
            if v is not None:
                result[key] = v
            tok = nxt()
            if tok is None:
                return result

    if tok == "HttpCompetitionId":
        nxt()  # removed field - consume value and discard
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpProtocolType":
        nxt()  # removed field - consume value and discard
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpIsLive":
        v = nxt()
        if v is not None:
            result["http_is_live"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpStageLabel":
        v = nxt()
        if v is not None:
            result["http_stage_label"] = v
        tok = nxt()
        if tok is None:
            return result

    # Legacy tags (pre per-protocol actions); kept so old configs still migrate.
    if tok == "UploadHttpGroups":
        v = nxt()
        if v is not None:
            result["upload_http_groups"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "UploadHttpAbsolute":
        v = nxt()
        if v is not None:
            result["upload_http_absolute"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpGroupsAction":
        v = nxt()
        if v is not None:
            result["http_groups_action"] = v
        tok = nxt()
        if tok is None:
            return result

    if tok == "HttpAbsoluteAction":
        v = nxt()
        if v is not None:
            result["http_absolute_action"] = v

    return result
