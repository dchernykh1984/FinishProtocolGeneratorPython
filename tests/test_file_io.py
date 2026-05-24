"""Tests for file_io helpers."""

from __future__ import annotations

import tempfile

from app.file_io import (
    load_config_file,
    load_template,
    read_finish_times,
    read_group_times,
    read_start_protocol,
)


def _tmp(content: str, encoding: str = "utf-8") -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", encoding=encoding, suffix=".txt", delete=False
    )
    f.write(content)
    f.close()
    return f.name


class TestReadLines:
    def test_utf8(self) -> None:
        path = _tmp("173#John#GroupA#3#1#1990#T#C##0 00:00:00.000#\n")
        sp = read_start_protocol(path)
        assert len(sp) == 1
        assert sp[0].competitor_id == "173"

    def test_empty_lines_skipped(self) -> None:
        path = _tmp("\n\n173#John#GroupA#3#1#1990#T#C##0 00:00:00.000#\n\n")
        sp = read_start_protocol(path)
        assert len(sp) == 1

    def test_cp1251(self) -> None:
        line = (
            "5#\u0418\u0432\u0430\u043d"
            "#\u0413\u0440\u0443\u043f\u043f\u0430"
            "#3#1#1985#\u0422#\u0413##0 00:00:00.000#\n"
        )
        path = _tmp(line, encoding="cp1251")
        sp = read_start_protocol(path)
        assert len(sp) == 1
        assert sp[0].competitor_id == "5"


class TestReadStartProtocol:
    def test_basic(self) -> None:
        content = (
            "1#Alice#GroupA#3#1#1990#TeamA#CityA##0 00:00:00.000#\n"
            "2#Bob#GroupA#3#1#1985#TeamB#CityB##0 00:00:00.000#\n"
        )
        path = _tmp(content)
        result = read_start_protocol(path)
        assert len(result) == 2
        assert result[0].name == "Alice"
        assert result[1].name == "Bob"

    def test_skip_first_lap(self) -> None:
        content = "1#Alice#GroupA#3#1#1990#T#C##0 00:00:00.000#\n"
        path = _tmp(content)
        normal = read_start_protocol(path)
        skip = read_start_protocol(path, skip_first_lap=True)
        assert skip[0].n_laps == normal[0].n_laps + 1


class TestReadGroupTimes:
    def test_basic(self) -> None:
        content = "GroupA#15921 11:11:5.846#\nGroupB#15921 11:15:21.468#\n"
        path = _tmp(content)
        result = read_group_times(path)
        assert len(result) == 2
        assert result[0].group_id == "GroupA"
        expected = 15921 * 86400 + 11 * 3600 + 11 * 60 + 5.846
        assert abs(result[0].seconds - expected) < 1e-3


class TestReadFinishTimes:
    def test_basic(self) -> None:
        content = (
            "1#15921 11:35:29.615#nextLap#\n"
            "2#15921 11:36:00.000#finish#\n"
            "3#15921 11:37:00.000#DSQ#\n"
        )
        path = _tmp(content)
        result = read_finish_times(path)
        assert len(result) == 3
        assert result[0].action == "nextLap"
        assert result[1].action == "finish"
        assert result[2].action == "DSQ"


def _fixed_13() -> list[str]:
    """13 required positional fields for C++ fpg_info.txt format."""
    return [
        "MySponsor",
        "MyRace",
        "2024-06-01",
        "Moscow",
        "Sunny",
        "Ref1",
        "Ref2",
        "OrgName",
        "Good",
        "60",
        "3600",
        "1",
        "Mass/Splitted",
    ]


def _cpp_header_through_ftp() -> list[str]:
    """Full C++ header through FTP section (needed for testing later sections)."""
    return [
        *_fixed_13(),
        # referee_label, secretary_label (always)
        "Referee",
        "Secretary",
        # 4 action values (always)
        "None",
        "None",
        "None",
        "None",
        # 3 FTP values (always, may be empty)
        "",
        "",
        "",
    ]


class TestLoadConfigFile:
    def test_required_fields(self) -> None:
        path = _tmp("\n".join(_fixed_13()) + "\n")
        cfg = load_config_file(path)
        assert cfg["sponsor"] == "MySponsor"
        assert cfg["race_name"] == "MyRace"
        assert cfg["race_date"] == "2024-06-01"
        assert cfg["race_type"] == "Mass/Splitted"
        assert cfg["minimal_time_for_lap"] == "60"

    def test_partial_file(self) -> None:
        path = _tmp("MySponsor\n")
        cfg = load_config_file(path)
        assert cfg["sponsor"] == "MySponsor"
        assert "race_name" not in cfg

    def test_optional_section_refresh(self) -> None:
        # C++ stores Timer.Interval in ms; 30000 ms -> 30 s after conversion.
        lines = [*_fixed_13(), "RefreshProtocol", "30000"]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("auto_refresh_interval") == "30"

    def test_refresh_roundtrip_seconds(self) -> None:
        # Python saves interval * 1000 (ms); loading back must give original seconds.
        interval_sec = 45
        lines = [*_fixed_13(), "RefreshProtocol", str(interval_sec * 1000)]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("auto_refresh_interval") == str(interval_sec)

    def test_optional_section_info(self) -> None:
        lines = [*_fixed_13(), "Info", "Extra info label"]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("show_additional_info") == "1"
        assert cfg.get("additional_info_label") == "Extra info label"

    def test_referee_secretary_labels(self) -> None:
        lines = [*_fixed_13(), "My Referee", "My Secretary"]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("referee_label") == "My Referee"
        assert cfg.get("secretary_label") == "My Secretary"

    def test_optional_show_id_name(self) -> None:
        lines = [
            *_fixed_13(),
            "Referee",
            "Secretary",
            "ID",
            "No.",
            "Name",
            "Full Name",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("show_id") == "1"
        assert cfg.get("id_label") == "No."
        assert cfg.get("show_name") == "1"
        assert cfg.get("name_label") == "Full Name"

    def test_optional_laps_block(self) -> None:
        lines = [
            *_fixed_13(),
            "Referee",
            "Secretary",
            "Laps",
            "Lap Name",
            "Round",
            "Lap Finish Info",
            "Cumulative",
            "Lap Finish",
            "Hide Empty Columns",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("show_lap_times") == "1"
        assert cfg.get("lap_name") == "Round"
        assert cfg.get("lap_additional_info") == "Cumulative"
        assert cfg.get("show_lap_finish") == "1"
        assert cfg.get("hide_empty_columns") == "1"

    def test_file_paths_section(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "/remote/",
            "2",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg["start_protocol_file"] == "start.txt"
        assert cfg["group_time_file"] == "groups.txt"
        assert cfg["finish_time_file"] == "results.txt"
        assert cfg["group_protocol_file"] == "gr.html"
        assert cfg["absolute_protocol_file"] == "abs.html"
        assert cfg["remote_points_path"] == "/remote/"
        assert cfg["n_remote_points"] == "2"

    def test_empty_remote_points_path(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",  # empty remote_points_path
            "0",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg["remote_points_path"] == ""
        assert cfg["n_remote_points"] == "0"

    def test_disable_dnf_dsq(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
            "Disable DNF",
            "Disable DSQ",
            "",  # bottom_text
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("disable_dnf") == "1"
        assert cfg.get("disable_dsq") == "1"

    def test_use_start_check_list(self) -> None:
        # C++ stores action (not file path) after UseStartCheckList token.
        lines = [
            *_cpp_header_through_ftp(),
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
            "UseStartCheckList",
            "Merge",
            "300",
            "Footer",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("use_start_check_list") == "1"
        assert cfg.get("start_check_list_action") == "Merge"
        assert cfg.get("start_check_list_file") == "temp/results_start.txt"
        assert cfg.get("start_registration_period") == "300"
        assert cfg.get("bottom_text") == "Footer"

    def test_bottom_text(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
            "Race footer text",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("bottom_text") == "Race footer text"

    def test_print_dnf_dns_dsq_flags(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "Print DNF",
            "Print DNS",
            "Print DSQ",
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg.get("print_dnf") == "1"
        assert cfg.get("print_dns") == "1"
        assert cfg.get("print_dsq") == "1"
        assert cfg.get("start_protocol_file") == "start.txt"

    def test_cpp_race_type_mass_splitted_mapped(self) -> None:
        fields = _fixed_13()
        fields[-1] = "Mass Start or Splitted Start"
        path = _tmp("\n".join(fields) + "\n")
        cfg = load_config_file(path)
        assert cfg["race_type"] == "Mass/Splitted"

    def test_cpp_race_type_spiridonov_mapped(self) -> None:
        fields = _fixed_13()
        fields[-1] = "Mass Start or Splitted Start with Spiridonov's coefficients"
        path = _tmp("\n".join(fields) + "\n")
        cfg = load_config_file(path)
        assert cfg["race_type"] == "Mass/Splitted (Spiridonov)"

    def test_finish_time_labels(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "Finish",
            "Time Difference",
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
            "Footer",
            "FinishTimeLabel",
            "My Time Label",
            "TimeDifferenceLabel",
            "My Gap Label",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg["show_finish_time"] == "1"
        assert cfg["finish_time_label"] == "My Time Label"
        assert cfg["show_time_difference"] == "1"
        assert cfg["time_difference_label"] == "My Gap Label"

    def test_full_cpp_format(self) -> None:
        """Exercise all optional sections in a single complete-format file."""
        lines = [
            *_fixed_13(),
            "Info",
            "Extra info",
            "RefreshProtocol",
            "60000",
            "Referee label",
            "Secretary label",
            "ID",
            "No.",
            "Name",
            "Full Name",
            "Age",
            "YOB",
            "Team",
            "Team",
            "City",
            "City",
            "Laps",
            "Lap Name",
            "Round",
            "Lap Finish Info",
            "Cumulative",
            "Lap Finish",
            "Hide Empty Columns",
            "Buttons",
            "All Buttons",
            "UploadGroups",
            "UploadAbsolute",
            "None",
            "None",
            "None",
            "None",
            "",
            "",
            "",
            "Finish",
            "Time Difference",
            "Number Of Laps Finished",
            "Group",
            "Grp",
            "Place",
            "Plc",
            "TimeShift",
            "Start time",
            "Stratch",
            "Print DNF",
            "Print DNS",
            "Print DSQ",
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "/remote/",
            "3",
            "Disable DNF",
            "Disable DSQ",
            "Use File Logger",
            "Use Interface Logger",
            "Err and Wrn only",
            "Laps Difference Erroros",
            "10",
            "UseStartCheckList",
            "Download",
            "300",
            "Footer text",
            "FinishTimeLabel",
            "Finish time",
            "TimeDifferenceLabel",
            "(gap from ldr)",
            "NFinishedLapsLabel",
            "(rounds)",
            "TemplateFile",
            "custom_template.html",
            "ButtonsLabel",
            "My splits btn",
            "AllButtonsLabel",
            "My stats btn",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg["show_additional_info"] == "1"
        assert cfg["additional_info_label"] == "Extra info"
        assert cfg["auto_refresh_interval"] == "60"  # 60000 ms / 1000 = 60 s
        assert cfg["referee_label"] == "Referee label"
        assert cfg["secretary_label"] == "Secretary label"
        assert cfg["show_id"] == "1"
        assert cfg["id_label"] == "No."
        assert cfg["show_name"] == "1"
        assert cfg["show_age"] == "1"
        assert cfg["show_team"] == "1"
        assert cfg["show_city"] == "1"
        assert cfg["show_lap_times"] == "1"
        assert cfg["lap_name"] == "Round"
        assert cfg["lap_additional_info"] == "Cumulative"
        assert cfg["show_lap_finish"] == "1"
        assert cfg["hide_empty_columns"] == "1"
        assert cfg["use_buttons"] == "1"
        assert cfg["use_all_buttons"] == "1"
        assert cfg["upload_groups"] == "1"
        assert cfg["upload_absolute"] == "1"
        assert cfg["show_finish_time"] == "1"
        assert cfg["finish_time_label"] == "Finish time"
        assert cfg["show_time_difference"] == "1"
        assert cfg["time_difference_label"] == "(gap from ldr)"
        assert cfg["show_n_finished_laps"] == "1"
        assert cfg["show_group"] == "1"
        assert cfg["group_label"] == "Grp"
        assert cfg["show_place"] == "1"
        assert cfg["place_label"] == "Plc"
        assert cfg["show_time_shift"] == "1"
        assert cfg["time_shift_label"] == "Start time"
        assert cfg["stretch"] == "1"
        assert cfg["print_dnf"] == "1"
        assert cfg["print_dns"] == "1"
        assert cfg["print_dsq"] == "1"
        assert cfg["start_protocol_file"] == "start.txt"
        assert cfg["remote_points_path"] == "/remote/"
        assert cfg["n_remote_points"] == "3"
        assert cfg["disable_dnf"] == "1"
        assert cfg["disable_dsq"] == "1"
        assert cfg["use_file_logger"] == "1"
        assert cfg["use_interface_logger"] == "1"
        assert cfg["errors_warnings_only"] == "1"
        assert cfg["check_laps_difference"] == "1"
        assert cfg["laps_difference_pct"] == "10"
        assert cfg["use_start_check_list"] == "1"
        assert cfg["start_check_list_action"] == "Download"
        assert cfg["start_registration_period"] == "300"
        assert cfg["bottom_text"] == "Footer text"
        assert cfg["finish_time_label"] == "Finish time"
        assert cfg["time_difference_label"] == "(gap from ldr)"
        assert cfg["n_finished_laps_label"] == "(rounds)"
        assert cfg["template_file"] == "custom_template.html"
        assert cfg["use_buttons_label"] == "My splits btn"
        assert cfg["use_all_buttons_label"] == "My stats btn"

    def test_buttons_labels(self) -> None:
        lines = [
            *_cpp_header_through_ftp(),
            "Finish",
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
            "Footer",
            "TemplateFile",
            "tmpl.html",
            "ButtonsLabel",
            "Show splits",
            "AllButtonsLabel",
            "Show stats",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg["use_buttons_label"] == "Show splits"
        assert cfg["use_all_buttons_label"] == "Show stats"

    def test_buttons_label_only(self) -> None:
        """AllButtonsLabel absent - only ButtonsLabel present."""
        lines = [
            *_cpp_header_through_ftp(),
            "Finish",
            "start.txt",
            "groups.txt",
            "results.txt",
            "gr.html",
            "abs.html",
            "",
            "0",
            "Footer",
            "ButtonsLabel",
            "My btn",
        ]
        path = _tmp("\n".join(lines) + "\n")
        cfg = load_config_file(path)
        assert cfg["use_buttons_label"] == "My btn"
        assert "use_all_buttons_label" not in cfg


class TestLoadTemplate:
    def test_all_fields(self) -> None:
        content = "\n".join(
            [
                "width:100%",
                "top-style",
                "even-style",
                "odd-style",
                "<FONT group>",
                "<FONT addtop>",
                "<FONT add>",
                "<FONT toptxt>",
                "<FONT infotop>",
                "<FONT info>",
                ".common { color: red; }",
            ]
        )
        path = _tmp(content)
        st = load_template(path)
        assert st is not None
        assert st.table_style == "width:100%"
        assert st.top_line_style == "top-style"
        assert st.even_line_style == "even-style"
        assert st.odd_line_style == "odd-style"
        assert st.group_name_style == "<FONT group>"
        assert st.additional_text_top_style == "<FONT addtop>"
        assert st.additional_text_style == "<FONT add>"
        assert st.top_text_style == "<FONT toptxt>"
        assert st.additional_info_top_style == "<FONT infotop>"
        assert st.additional_info_style == "<FONT info>"
        assert st.common_style_text == ".common { color: red; }"

    def test_missing_file_returns_none(self) -> None:
        assert load_template("/nonexistent/template.html") is None

    def test_partial_file_pads_with_empty(self) -> None:
        path = _tmp("only-table-style\n")
        st = load_template(path)
        assert st is not None
        assert st.table_style == "only-table-style"
        assert st.top_line_style == ""
