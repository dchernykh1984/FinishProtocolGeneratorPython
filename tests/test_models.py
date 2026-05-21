"""Tests for data models and parsing."""

import math

from app.models import (
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    IntermediateCrosses,
    StartProtocolElement,
    get_field,
    parse_time_string,
    to_int,
)


class TestParseTimeString:
    def test_zero(self) -> None:
        assert parse_time_string("0") == 0.0

    def test_empty(self) -> None:
        assert parse_time_string("") == 0.0

    def test_days_and_time(self) -> None:
        # 1 day + 1 hour + 1 min + 1 sec + 0.5 sec
        val = parse_time_string("1 1:1:1.500")
        assert abs(val - (86400 + 3600 + 60 + 1.5)) < 1e-6

    def test_realistic_timestamp(self) -> None:
        # from test data: "15921 11:11:5.846"
        val = parse_time_string("15921 11:11:5.846")
        expected = 15921 * 86400 + 11 * 3600 + 11 * 60 + 5.846
        assert abs(val - expected) < 1e-3

    def test_no_fraction(self) -> None:
        val = parse_time_string("0 1:2:3")
        assert abs(val - (3600 + 120 + 3)) < 1e-9

    def test_result_timestamp(self) -> None:
        val = parse_time_string("15921 11:35:29.615")
        expected = 15921 * 86400 + 11 * 3600 + 35 * 60 + 29.615
        assert abs(val - expected) < 1e-3


class TestGetField:
    def test_basic(self) -> None:
        assert get_field("a#b#c", 0) == "a"
        assert get_field("a#b#c", 1) == "b"
        assert get_field("a#b#c", 2) == "c"

    def test_out_of_range(self) -> None:
        assert get_field("a#b", 5) == ""

    def test_trailing_sep(self) -> None:
        assert get_field("173#Name#Group#99#1#", 0) == "173"
        assert get_field("173#Name#Group#99#1#", 3) == "99"


class TestToInt:
    def test_valid(self) -> None:
        assert to_int("42") == 42
        assert to_int("0") == 0

    def test_invalid(self) -> None:
        assert to_int("abc") == 0
        assert to_int("") == 0


class TestStartProtocolElement:
    _LINE = "173#John Doe#Group A#6#1#1985#TeamX#CityY#comment#0 00:00:00.000#"

    def test_from_line(self) -> None:
        sp = StartProtocolElement.from_line(self._LINE)
        assert sp.competitor_id == "173"
        assert sp.name == "John Doe"
        assert sp.group_id == "Group A"
        assert sp.n_laps == 6
        assert sp.stages == 1
        assert sp.year_of_birth == "1985"
        assert sp.team == "TeamX"
        assert sp.city == "CityY"
        assert sp.extra_info == "comment"
        assert sp.start_delay == 0.0
        assert sp.number == 173

    def test_skip_first_lap_increments_laps(self) -> None:
        sp = StartProtocolElement.from_line(self._LINE, skip_first_lap=True)
        assert sp.n_laps == 7

    def test_non_numeric_id(self) -> None:
        line = "ABC#Name#Group#3#1#1990#Team#City##0 00:00:00.000#"
        sp = StartProtocolElement.from_line(line)
        assert sp.competitor_id == "ABC"
        assert sp.number == 0


class TestFinishCompetitorElement:
    def test_nextlap(self) -> None:
        fc = FinishCompetitorElement.from_line("1#15921 11:35:29.615#nextLap#")
        assert fc.competitor_id == "1"
        assert fc.action == "nextLap"
        assert fc.penalty == 0.0
        expected_t = 15921 * 86400 + 11 * 3600 + 35 * 60 + 29.615
        assert abs(fc.seconds - expected_t) < 1e-3

    def test_finish(self) -> None:
        fc = FinishCompetitorElement.from_line("42#15921 12:00:00.000#finish#")
        assert fc.action == "finish"

    def test_dsq(self) -> None:
        fc = FinishCompetitorElement.from_line("7#15921 11:00:00.000#DSQ#")
        assert fc.action == "DSQ"

    def test_numeric_penalty(self) -> None:
        fc = FinishCompetitorElement.from_line("5#15921 11:00:00.000#nextLap#30#")
        assert fc.penalty == 30.0


class TestGroupStartElement:
    def test_from_line(self) -> None:
        gs = GroupStartElement.from_line("Group A#15921 11:11:5.846#")
        assert gs.group_id == "Group A"
        expected_t = 15921 * 86400 + 11 * 3600 + 11 * 60 + 5.846
        assert abs(gs.seconds - expected_t) < 1e-3
        assert gs.place == 1


class TestIntermediateCrosses:
    def test_init(self) -> None:
        cp = IntermediateCrosses(3)
        assert len(cp.segment_crosses) == 3
        assert all(v == -1.0 for v in cp.segment_crosses)
        assert all(v == -1.0 for v in cp.segment_finishes)
        assert all(v == -1.0 for v in cp.segment_times)

    def test_zero_points(self) -> None:
        cp = IntermediateCrosses(0)
        assert cp.segment_crosses == []


class TestFinishProtocolElement:
    def _make_start(self, n_laps: int = 6) -> StartProtocolElement:
        line = f"10#Runner A#GroupA#{n_laps}#1#1990#Team#City##0 00:00:00.000#"
        return StartProtocolElement.from_line(line)

    def test_initial_state(self) -> None:
        start = self._make_start()
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        assert fp.finished is False
        assert fp.disqualified is False
        assert fp.n_laps_finished == 0
        assert fp.n_laps == 6
        assert len(fp.cross_line_times) >= 8

    def test_disable_dnf_sets_finished(self) -> None:
        start = self._make_start()
        fp = FinishProtocolElement(start, disable_dnf=True, n_points=0)
        assert fp.finished is True

    def test_is_same_competitor_by_id(self) -> None:
        start = self._make_start()
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fc = FinishCompetitorElement.from_line("10#15921 11:00:00.000#nextLap#")
        assert fp.is_same_competitor(fc) is True

    def test_is_same_competitor_different_id(self) -> None:
        start = self._make_start()
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fc = FinishCompetitorElement.from_line("99#15921 11:00:00.000#nextLap#")
        assert fp.is_same_competitor(fc) is False

    def test_is_same_competitor_relay(self) -> None:
        line = "10#Runner A#GroupA#6#2#1990#Team#City##0 00:00:00.000#"
        start = StartProtocolElement.from_line(line)
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fc11 = FinishCompetitorElement.from_line("11#15921 11:00:00.000#nextLap#")
        assert fp.is_same_competitor(fc11) is True
        fc12 = FinishCompetitorElement.from_line("12#15921 11:00:00.000#nextLap#")
        assert fp.is_same_competitor(fc12) is False

    def test_get_total_time_no_laps(self) -> None:
        start = self._make_start()
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        assert fp.get_total_time() == math.inf

    def test_get_total_time_with_laps(self) -> None:
        start = self._make_start()
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fp.n_laps_finished = 1
        fp.finish_lap_times[0] = 300.0
        assert fp.get_total_time() == 300.0

    def test_get_total_time_number_of_tries_best_selection(self) -> None:
        # n_laps=3, extra_info "2:1,2,3" -> n_tries_for_result=2
        # 3 attempts with times 30, 10, 20 -> best 2 = 10+20 = 30
        start = StartProtocolElement.from_line(
            "1#Name#G#3#1#1990#Team#City#2:1,2,3#0 00:00:00.000#"
        )
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fp.n_laps_finished = 3
        fp.lap_times[0] = 30.0
        fp.lap_times[1] = 10.0
        fp.lap_times[2] = 20.0
        fp.finish_lap_times[2] = 60.0
        assert abs(fp.get_total_time() - 30.0) < 0.01

    def test_get_n_successful_tries_capped(self) -> None:
        # n_laps=3, extra_info "2:1,2,3" -> n_tries_for_result=2; 3 finished -> capped at 2  # noqa: E501
        start = StartProtocolElement.from_line(
            "1#Name#G#3#1#1990#Team#City#2:1,2,3#0 00:00:00.000#"
        )
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fp.n_laps_finished = 3
        assert fp.get_n_successful_tries() == 2

    def test_get_n_successful_tries_not_capped(self) -> None:
        # n_laps=3, no extra_info -> n_tries_for_result=3; 2 finished -> not capped
        start = StartProtocolElement.from_line(
            "1#Name#G#3#1#1990#Team#City##0 00:00:00.000#"
        )
        fp = FinishProtocolElement(start, disable_dnf=False, n_points=0)
        fp.n_laps_finished = 2
        assert fp.get_n_successful_tries() == 2
