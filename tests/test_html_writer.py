"""Tests for HTML protocol generation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import (
    RACE_TYPE_CUSTOM_START,
    RACE_TYPE_ELIMINATOR_QUALIFICATION,
    RaceConfig,
)
from app.html_writer import (
    _draw_button,
    _format_time,
    write_absolute_protocol,
    write_group_protocol,
)
from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
)

# ---------------------------------------------------------------------------
# _format_time
# ---------------------------------------------------------------------------


class TestFormatTime:
    def test_zero(self) -> None:
        assert _format_time(0.0, 1) == "00:00:00.0"

    def test_one_hour(self) -> None:
        assert _format_time(3600.0, 0) == "01:00:00"

    def test_one_minute_and_half(self) -> None:
        assert _format_time(90.5, 1) == "00:01:30.5"

    def test_negative(self) -> None:
        assert _format_time(-60.0, 0) == "-00:01:00"

    def test_large_value_unknown(self) -> None:
        big = 400 * 24 * 3600
        assert _format_time(big, 1) == "UNKNOWN"

    def test_days(self) -> None:
        val = 2 * 86400 + 3600
        result = _format_time(val, 0)
        assert "days" in result
        assert "01:00:00" in result

    def test_one_day(self) -> None:
        val = 86400 + 60
        result = _format_time(val, 0)
        assert "day" in result
        assert "days" not in result


# ---------------------------------------------------------------------------
# write_group_protocol / write_absolute_protocol -- smoke tests
# ---------------------------------------------------------------------------

BASE_T = 15921 * 86400


def _make_scenario():
    start_list = [
        StartProtocolElement.from_line(
            "1#Alice#GroupA#3#1#1990#TeamA#CityA##0 00:00:00.000#"
        ),
        StartProtocolElement.from_line(
            "2#Bob#GroupA#3#1#1985#TeamB#CityB##0 00:00:00.000#"
        ),
        StartProtocolElement.from_line(
            "3#Carol#GroupB#2#1#1992#TeamC#CityC##0 00:00:00.000#"
        ),
    ]
    group_list = [
        GroupStartElement.from_line("GroupA#15921 1:0:0.000#"),
        GroupStartElement.from_line("GroupB#15921 1:0:0.000#"),
    ]
    finish_list = [
        FinishCompetitorElement.from_line(f"1#{15921} 1:5:0.000#nextLap#"),
        FinishCompetitorElement.from_line(f"1#{15921} 1:10:0.000#nextLap#"),
        FinishCompetitorElement.from_line(f"1#{15921} 1:15:0.000#finish#"),
        FinishCompetitorElement.from_line(f"2#{15921} 1:6:0.000#nextLap#"),
        FinishCompetitorElement.from_line(f"2#{15921} 1:12:0.000#nextLap#"),
        FinishCompetitorElement.from_line(f"2#{15921} 1:18:0.000#finish#"),
        FinishCompetitorElement.from_line(f"3#{15921} 1:5:30.000#nextLap#"),
        FinishCompetitorElement.from_line(f"3#{15921} 1:11:0.000#finish#"),
    ]
    cfg = RaceConfig()
    log: list[str] = []
    protocol = calculate_protocol(start_list, group_list, finish_list, [], [], cfg, log)
    sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
    return sorted_proto, group_list, cfg


class TestWriteGroupProtocol:
    def test_creates_file(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "charset=utf-8" in content

    def test_contains_group_names(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "GroupA" in content
        assert "GroupB" in content

    def test_contains_competitor_names(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Alice" in content
        assert "Bob" in content


class TestWriteAbsoluteProtocol:
    def test_creates_file(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "charset=utf-8" in content

    def test_contains_overall_results(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Overall results" in content

    def test_contains_all_competitors(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Alice" in content
        assert "Bob" in content
        assert "Carol" in content

    def test_race_name_in_header(self) -> None:
        sorted_proto, group_list, cfg = _make_scenario()
        cfg.race_name = "Test Race 2024"
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Test Race 2024" in content

    def test_print_dns_shows_dns_competitor(self) -> None:
        start_list = [
            StartProtocolElement.from_line(
                "10#NoStart#G#2#1#1990#T#C##0 00:00:00.000#"
            ),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list: list[FinishCompetitorElement] = []
        cfg = RaceConfig()
        cfg.print_dns = True
        cfg.print_dnf = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "DNS" in content or "NoStart" in content


class TestWriteAllOptions:
    """Test both write functions with all optional columns enabled."""

    def _full_cfg(self) -> RaceConfig:
        cfg = RaceConfig()
        cfg.race_name = "Test Race"
        cfg.race_date = "2024-06-01"
        cfg.race_place = "Moscow"
        cfg.track_conditions = "Dry"
        cfg.weather = "Sunny"
        cfg.organizer = "OrgName"
        cfg.main_referee = "Ref1"
        cfg.additional_referee = "Ref2"
        cfg.bottom_text = "Footer text"
        cfg.show_place = True
        cfg.show_id = True
        cfg.show_name = True
        cfg.show_age = True
        cfg.show_team = True
        cfg.show_city = True
        cfg.show_group = True
        cfg.show_lap_times = True
        cfg.show_finish_time = True
        cfg.show_time_difference = True
        cfg.show_additional_info = True
        cfg.show_time_shift = True
        cfg.show_n_finished_laps = True
        cfg.show_lap_finish = True
        cfg.print_dnf = True
        cfg.print_dns = True
        cfg.print_dsq = True
        cfg.stretch = True
        return cfg

    def _build(self):
        start_list = [
            StartProtocolElement.from_line(
                "1#Alice#G#2#1#1990#TA#CA#Info1#0 00:00:00.000#"
            ),
            StartProtocolElement.from_line("2#Bob#G#2#1#1985#TB#CB##0 00:00:00.000#"),
            StartProtocolElement.from_line("3#Eve#G#2#1#1992#TC#CC##0 00:00:00.000#"),
            StartProtocolElement.from_line("4#Dan#G#2#1#2000#TD#CD##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            # Alice finishes 2 laps
            FinishCompetitorElement.from_line("1#15921 1:5:0.000#nextLap#"),
            FinishCompetitorElement.from_line("1#15921 1:10:0.000#finish#"),
            # Bob finishes only 1 lap (DNF)
            FinishCompetitorElement.from_line("2#15921 1:6:0.000#nextLap#"),
            # Eve is DSQ
            FinishCompetitorElement.from_line("3#15921 1:4:0.000#DSQ#"),
            # Dan DNS -- no finish records
        ]
        return start_list, group_list, finish_list

    def test_group_protocol_all_options(self) -> None:
        start_list, group_list, finish_list = self._build()
        cfg = self._full_cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Test Race" in content
        assert "Moscow" in content
        assert "Sunny" in content
        assert "OrgName" in content
        assert "Ref1" in content
        assert "Footer text" in content
        assert "Alice" in content

    def test_absolute_protocol_all_options(self) -> None:
        start_list, group_list, finish_list = self._build()
        cfg = self._full_cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Overall results" in content
        assert "Alice" in content
        assert "Bob" in content
        assert "DSQ" in content

    def test_absolute_hide_empty_columns(self) -> None:
        start_list, group_list, finish_list = self._build()
        cfg = self._full_cfg()
        cfg.hide_empty_columns = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "charset=utf-8" in content

    def test_group_protocol_hide_empty_columns(self) -> None:
        start_list, group_list, finish_list = self._build()
        cfg = self._full_cfg()
        cfg.hide_empty_columns = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "charset=utf-8" in content


_CP_BASE = 15921 * 86400  # epoch base for CP tests


def _make_cp_scenario(n_cp: int = 1, alice_crosses_cp1: bool = True):
    """Scenario: 2 competitors, 2 laps, n_cp remote control points."""
    t0 = _CP_BASE + 3600  # group start (01:00:00 of that day)
    start_list = [
        StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
        StartProtocolElement.from_line("2#Bob#G#2#1#1985#TB#CB##0 00:00:00.000#"),
    ]
    group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
    finish_list = [
        FinishCompetitorElement(competitor_id="1", seconds=t0 + 300, action="nextLap"),
        FinishCompetitorElement(competitor_id="1", seconds=t0 + 600, action="finish"),
        FinishCompetitorElement(competitor_id="2", seconds=t0 + 360, action="nextLap"),
        FinishCompetitorElement(competitor_id="2", seconds=t0 + 720, action="finish"),
    ]
    # CP1: Alice crosses at t0+150 (mid lap 1); Bob doesn't
    cp1_list = []
    if alice_crosses_cp1:
        cp1_list.append(
            FinishCompetitorElement(competitor_id="1", seconds=t0 + 150, action="cp1")
        )
    remote_points = [cp1_list]
    if n_cp == 2:
        # CP2: nobody crosses (tests empty cell rendering)
        remote_points.append([])
    cfg = RaceConfig()
    cfg.show_lap_times = True
    log: list[str] = []
    protocol = calculate_protocol(
        start_list, group_list, finish_list, remote_points, [], cfg, log
    )
    n_points = len(remote_points)
    sorted_proto = generate_sorted_protocol(protocol, cfg, n_points)
    return sorted_proto, group_list, cfg, n_points


class TestControlPointRendering:
    def test_group_cp_subheader_present(self) -> None:
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        assert "(1 split)" in content

    def test_group_cp_time_rendered(self) -> None:
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        # Alice crosses CP1 at t0+150 = 02:30 from lap start
        assert "02:30" in content

    def test_group_cp_err_when_not_crossed_on_finished_lap(self) -> None:
        # Bob finishes 2 laps but never crosses CP1 -> ERR in completed-lap cells
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        assert "ERR" in content

    def test_absolute_cp_subheader_present(self) -> None:
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        assert "(1 split)" in content

    def test_absolute_cp_time_rendered(self) -> None:
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        assert "02:30" in content

    def test_group_cp_colspan_when_is_number_of_tries(self) -> None:
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        cfg.race_type = RACE_TYPE_NUMBER_OF_TRIES
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        # CP split header NOT rendered for NumberOfTries
        assert "(1 split)" not in content
        # COLSPAN=2 (n_points+1) used instead
        assert "COLSPAN=2" in content

    def test_group_cp_lap_time_uses_colspan(self) -> None:
        sorted_proto, group_list, cfg, n_points = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points)
        content = Path(path).read_text(encoding="utf-8")
        # Non-NumberOfTries: lap time cell must use COLSPAN=2 (n_points+1)
        assert "COLSPAN=2" in content

    def test_group_cp_last_segment_rendered(self) -> None:
        # Alice: CP1 at t0+100 -> segment[0]=100s="01:40", segment[1]=200s="03:20"
        t0 = _CP_BASE + 3600
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 300, action="nextLap"
            ),
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 600, action="finish"
            ),
        ]
        cp1_list = [
            FinishCompetitorElement(competitor_id="1", seconds=t0 + 100, action="cp1")
        ]
        cfg = RaceConfig()
        cfg.show_lap_times = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [cp1_list], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        assert "01:40" in content  # segment[0]: start -> CP1
        assert "03:20" in content  # segment[1]: CP1 -> lap finish

    def test_absolute_cp_last_segment_rendered(self) -> None:
        t0 = _CP_BASE + 3600
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 300, action="nextLap"
            ),
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 600, action="finish"
            ),
        ]
        cp1_list = [
            FinishCompetitorElement(competitor_id="1", seconds=t0 + 100, action="cp1")
        ]
        cfg = RaceConfig()
        cfg.show_lap_times = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [cp1_list], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        assert "01:40" in content  # segment[0]: start -> CP1
        assert "03:20" in content  # segment[1]: CP1 -> lap finish

    def test_group_no_cp_when_n_points_zero(self) -> None:
        sorted_proto, group_list, cfg, _ = _make_cp_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        # n_points=0 overrides: no CP header, single lap-time cells
        write_group_protocol(path, sorted_proto, group_list, cfg, 0)
        content = Path(path).read_text(encoding="utf-8")
        assert "CP1" not in content

    def test_group_empty_lap_cells_when_not_finished(self) -> None:
        # Only Alice finishes lap1; scenario with 2 laps where Bob finishes only 1
        t0 = _CP_BASE + 3600
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
            StartProtocolElement.from_line("2#Bob#G#2#1#1985#TB#CB##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 300, action="nextLap"
            ),
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 600, action="finish"
            ),
            FinishCompetitorElement(
                competitor_id="2", seconds=t0 + 360, action="nextLap"
            ),
            # Bob has only 1 lap
        ]
        remote_points = [
            [FinishCompetitorElement(competitor_id="1", seconds=t0 + 150, action="cp1")]
        ]
        cfg = RaceConfig()
        cfg.print_dnf = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, remote_points, [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        assert "(1 split)" in content
        assert "charset=utf-8" in content


def _make_in_progress_cp_scenario():
    """Scenario: Alice finishes lap 1, then crosses CP1 but NOT lap 2 finish."""
    t0 = _CP_BASE + 3600
    start_list = [
        StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
    ]
    group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
    finish_list = [
        # lap 1 finished
        FinishCompetitorElement(competitor_id="1", seconds=t0 + 300, action="nextLap"),
        # lap 2 NOT finished -- Alice is in-progress on lap 2
    ]
    # CP1 crossed on lap 2 (in-progress lap) at t0+450
    cp1_list = [
        FinishCompetitorElement(
            competitor_id="1", seconds=t0 + 150, action="cp1"
        ),  # lap 1
        FinishCompetitorElement(
            competitor_id="1", seconds=t0 + 450, action="cp1"
        ),  # lap 2
    ]
    cfg = RaceConfig()
    cfg.show_lap_times = True
    cfg.print_dnf = True
    log: list[str] = []
    protocol = calculate_protocol(
        start_list, group_list, finish_list, [cp1_list], [], cfg, log
    )
    sorted_proto = generate_sorted_protocol(protocol, cfg, 1)
    return sorted_proto, group_list, cfg


class TestInProgressLapCPRendering:
    def test_group_crossed_cp_shown_on_in_progress_lap(self) -> None:
        # CP1 crossed at t0+450 on in-progress lap 2; segment time = 150s = "02:30"
        sorted_proto, group_list, cfg = _make_in_progress_cp_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        # lap2 CP1 segment = 450-300 = 150s -> "02:30"
        assert "02:30" in content

    def test_group_last_segment_err_on_in_progress_lap(self) -> None:
        # Last segment (CP1->lap finish) on in-progress lap must render ERR
        sorted_proto, group_list, cfg = _make_in_progress_cp_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        assert "ERR" in content

    def test_absolute_crossed_cp_shown_on_in_progress_lap(self) -> None:
        sorted_proto, group_list, cfg = _make_in_progress_cp_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        assert "02:30" in content

    def test_absolute_last_segment_err_on_in_progress_lap(self) -> None:
        sorted_proto, group_list, cfg = _make_in_progress_cp_scenario()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, 1)
        content = Path(path).read_text(encoding="utf-8")
        assert "ERR" in content

    def test_group_uncrossed_cp_err_on_in_progress_lap(self) -> None:
        # 0 laps finished; CP1 crossed on lap 1 (in-progress), CP2 never crossed.
        # Old buggy impl: 1 ERR (last segment only, CP2 cell left empty).
        # Correct impl:   2 ERRs (CP2 cell + last segment).
        t0 = _CP_BASE + 3600
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list: list[FinishCompetitorElement] = []  # no lap finished
        cp1_list = [
            FinishCompetitorElement(competitor_id="1", seconds=t0 + 150, action="cp1"),
        ]
        cp2_list: list = []
        cfg = RaceConfig()
        cfg.show_lap_times = True
        cfg.print_dns = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [cp1_list, cp2_list], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 2)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, 2)
        content = Path(path).read_text(encoding="utf-8")
        assert "02:30" in content
        assert content.count("ERR") == 2


class TestFormatTimeWriteDate:
    def test_write_date(self) -> None:
        # day 1 = 1970-01-02
        val = 86400.0
        result = _format_time(val, 0, write_date=True)
        assert "1970-01-02" in result

    def test_write_date_multi_month(self) -> None:
        # 31 days -> 1970-02-01
        val = 31 * 86400.0
        result = _format_time(val, 0, write_date=True)
        assert "1970-02-01" in result

    def test_write_date_year_boundary(self) -> None:
        # 366 days -> crosses into 1971
        val = 366 * 86400.0
        result = _format_time(val, 0, write_date=True)
        assert "1971" in result


class TestHtmlWriterEdgeCases:
    def test_group_protocol_with_sponsor(self) -> None:
        start_list = [
            StartProtocolElement.from_line("1#A#G#1#1#1990#T#C##0 00:00:00.000#")
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [FinishCompetitorElement.from_line("1#15921 1:5:0.000#finish#")]
        cfg = RaceConfig()
        cfg.sponsor = "ACME Sponsors"
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "ACME Sponsors" in content

    def test_relay_id_cell_in_group_protocol(self) -> None:
        # stages=2 -> id_cell shows multiple IDs
        start_list = [
            StartProtocolElement.from_line("10#Team AB#G#2#2#1990#T#C##0 00:00:00.000#")
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            FinishCompetitorElement.from_line("10#15921 1:5:0.000#nextLap#"),
            FinishCompetitorElement.from_line("11#15921 1:10:0.000#finish#"),
        ]
        cfg = RaceConfig()
        cfg.show_id = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        # relay team: IDs 10 and 11 both appear
        assert "10" in content and "11" in content

    def test_generate_text_protocol_creates_txt_file(self) -> None:
        start_list = [
            StartProtocolElement.from_line("1#A#G#1#1#1990#T#C##0 00:00:00.000#")
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [FinishCompetitorElement.from_line("1#15921 1:5:0.000#finish#")]
        cfg = RaceConfig()
        cfg.race_type = RACE_TYPE_ELIMINATOR_QUALIFICATION
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        txt_path = path + ".txt"
        content = Path(txt_path).read_text(encoding="utf-8")
        # C++ machine-readable: id#name#group#n_laps#stages#year#team#city#extra#place#
        assert "1#A#G#1#1#1990#T#C##1#" in content

    def test_generate_text_protocol_dsq_dnf(self) -> None:
        # The text protocol writes ONLY finished, non-DSQ competitors (matching C++)
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#T#C##0 00:00:00.000#"),
            StartProtocolElement.from_line("2#Bob#G#2#1#1985#T#C##0 00:00:00.000#"),
            StartProtocolElement.from_line("3#Eve#G#2#1#1992#T#C##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            FinishCompetitorElement.from_line("1#15921 1:5:0.000#nextLap#"),
            FinishCompetitorElement.from_line("1#15921 1:10:0.000#finish#"),
            FinishCompetitorElement.from_line("2#15921 1:6:0.000#nextLap#"),
            FinishCompetitorElement.from_line("3#15921 1:4:0.000#DSQ#"),
        ]
        cfg = RaceConfig()
        cfg.race_type = RACE_TYPE_ELIMINATOR_QUALIFICATION
        cfg.print_dnf = True
        cfg.print_dsq = True
        cfg.print_dns = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        txt_path = path + ".txt"
        content = Path(txt_path).read_text(encoding="utf-8")
        # Only Alice finished; Bob (DNF) and Eve (DSQ) are excluded from the .txt
        assert "Alice" in content
        assert "Bob" not in content
        assert "Eve" not in content

    def test_group_protocol_skip_first_lap_show_time_shift(self) -> None:
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#T#C##0 00:00:00.000#"),
            StartProtocolElement.from_line("2#Bob#G#2#1#1985#T#C##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        # Bob never crosses (INF start time)
        finish_list = [
            FinishCompetitorElement.from_line("1#15921 1:1:0.000#nextLap#"),
            FinishCompetitorElement.from_line("1#15921 1:6:0.000#nextLap#"),
            FinishCompetitorElement.from_line("1#15921 1:11:0.000#finish#"),
        ]
        cfg = RaceConfig()
        cfg.race_type = RACE_TYPE_CUSTOM_START
        cfg.show_time_shift = True
        cfg.print_dns = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "NOT STARTED" in content


# ---------------------------------------------------------------------------
# collapsible buttons (use_buttons / use_all_buttons)
# ---------------------------------------------------------------------------


def _make_two_lap_scenario(n_cp: int = 0):
    """Two competitors, same group, 2 laps each."""
    t0 = _CP_BASE + 3600
    start_list = [
        StartProtocolElement.from_line("1#Alice#G#2#1#1990#TA#CA##0 00:00:00.000#"),
        StartProtocolElement.from_line("2#Bob#G#2#1#1985#TB#CB##0 00:00:00.000#"),
    ]
    group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
    finish_list = [
        FinishCompetitorElement(competitor_id="1", seconds=t0 + 300, action="nextLap"),
        FinishCompetitorElement(competitor_id="1", seconds=t0 + 650, action="finish"),
        FinishCompetitorElement(competitor_id="2", seconds=t0 + 320, action="nextLap"),
        FinishCompetitorElement(competitor_id="2", seconds=t0 + 700, action="finish"),
    ]
    remote_points: list[list] = []
    if n_cp > 0:
        cp_list = [
            FinishCompetitorElement(competitor_id="1", seconds=t0 + 150, action="cp1"),
            FinishCompetitorElement(competitor_id="2", seconds=t0 + 160, action="cp1"),
        ]
        remote_points = [cp_list]
    cfg = RaceConfig()
    cfg.show_lap_times = True
    log: list[str] = []
    protocol = calculate_protocol(
        start_list, group_list, finish_list, remote_points, [], cfg, log
    )
    sorted_proto = generate_sorted_protocol(protocol, cfg, n_cp)
    return sorted_proto, group_list, cfg


class TestDrawButton:
    def test_button_output(self) -> None:
        from io import StringIO

        buf = StringIO()
        _draw_button(buf, "MyBtn", "Col ", " data", 2, 3)
        out = buf.getvalue()
        assert "MyBtn" in out
        assert "showhideall(0, 'Col 0 data', 1)" in out
        assert "showhideall(1, 'Col 2 data', 1)" in out
        assert out.startswith("<button")


class TestUseAllButtons:
    def test_group_use_all_buttons_header_rendered(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario()
        cfg.use_all_buttons = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Additional 0 Laps_0" in content
        assert "Rank(Lap)" in content
        assert "showhideall" in content

    def test_group_use_all_buttons_data_row_rendered(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario()
        cfg.use_all_buttons = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Additional 0 Laps_1" in content
        assert "Additional 0 Laps_2" in content

    def test_group_use_all_buttons_lap_finish_header(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario()
        cfg.use_all_buttons = True
        cfg.show_lap_finish = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Lap " in content
        assert "Rank(Lap)" in content

    def test_group_use_buttons_center_rendered(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario(n_cp=1)
        cfg.use_buttons = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points=1)
        content = Path(path).read_text(encoding="utf-8")
        assert "Lap 0 splits" in content
        assert "showhideall" in content

    def test_group_use_all_buttons_empty_lap_cell(self) -> None:
        t0 = _CP_BASE + 3600
        start_list = [
            StartProtocolElement.from_line("1#Alice#G#2#1#1990#T#C##0 00:00:00.000#"),
            StartProtocolElement.from_line("2#Bob#G#2#1#1985#T#C##0 00:00:00.000#"),
        ]
        group_list = [GroupStartElement.from_line("G#15921 1:0:0.000#")]
        finish_list = [
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 300, action="nextLap"
            ),
            FinishCompetitorElement(
                competitor_id="1", seconds=t0 + 650, action="finish"
            ),
            # Bob finishes only lap 1 (DNF after)
            FinishCompetitorElement(
                competitor_id="2", seconds=t0 + 310, action="nextLap"
            ),
        ]
        cfg = RaceConfig()
        cfg.show_lap_times = True
        cfg.use_all_buttons = True
        cfg.print_dnf = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        # Bob DNF: lap 2 additional-stats cell should exist but be empty
        assert "Additional 1 Laps" in content

    def test_absolute_use_all_buttons_header_rendered(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario()
        cfg.use_all_buttons = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "0_Additional 0 Laps_0" in content
        assert "Rank(Lap)" in content

    def test_absolute_use_all_buttons_data_row_rendered(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario()
        cfg.use_all_buttons = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "0_Additional 0 Laps_1" in content

    def test_absolute_use_all_buttons_lap_finish(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario()
        cfg.use_all_buttons = True
        cfg.show_lap_finish = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg)
        content = Path(path).read_text(encoding="utf-8")
        assert "Rank(Lap)" in content

    def test_group_cp_splits_id_in_data_row(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_group_protocol(path, sorted_proto, group_list, cfg, n_points=1)
        content = Path(path).read_text(encoding="utf-8")
        assert "0_Lap 0 splits_1" in content

    def test_absolute_cp_splits_id_in_data_row(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario(n_cp=1)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, n_points=1)
        content = Path(path).read_text(encoding="utf-8")
        assert "0_Lap 0 splits_1" in content

    def test_absolute_use_buttons_center_rendered(self) -> None:
        sorted_proto, group_list, cfg = _make_two_lap_scenario(n_cp=1)
        cfg.use_buttons = True
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        write_absolute_protocol(path, sorted_proto, group_list, cfg, n_points=1)
        content = Path(path).read_text(encoding="utf-8")
        assert "Lap 0 splits" in content
