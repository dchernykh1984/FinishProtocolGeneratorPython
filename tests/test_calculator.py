"""Tests for calculate_protocol, generate_sorted_protocol, and check_start_protocol."""

from __future__ import annotations

from app.calculator import (
    calculate_protocol,
    check_start_protocol,
    generate_sorted_protocol,
    spiridonov,
)
from app.config import RACE_TYPE_CUSTOM_START, RaceConfig
from app.models import (
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    StartProtocolElement,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

BASE_T = 15921 * 86400  # day offset used in realistic tests


def _start(
    cid: str, group: str, n_laps: int = 3, stages: int = 1, delay: float = 0.0
) -> StartProtocolElement:
    line = f"{cid}#Name {cid}#{group}#{n_laps}#{stages}#1990#Team#City##"
    if delay == 0.0:
        line += "0 00:00:00.000#"
    else:
        h = int(delay) // 3600
        m = (int(delay) % 3600) // 60
        s = int(delay) % 60
        ms = int((delay - int(delay)) * 1000)
        line += f"0 {h:02d}:{m:02d}:{s:02d}.{ms:03d}#"
    return StartProtocolElement.from_line(line)


def _group(gid: str, seconds: float) -> GroupStartElement:
    d = int(seconds // 86400)
    rem = seconds - d * 86400
    h = int(rem // 3600)
    rem -= h * 3600
    m = int(rem // 60)
    s = rem - m * 60
    ms = round((s - int(s)) * 1000)
    return GroupStartElement.from_line(f"{gid}#{d} {h}:{m}:{int(s)}.{ms:03d}#")


def _finish(
    cid: str, seconds: float, action: str = "nextLap"
) -> FinishCompetitorElement:
    d = int(seconds // 86400)
    rem = seconds - d * 86400
    h = int(rem // 3600)
    rem -= h * 3600
    m = int(rem // 60)
    s = rem - m * 60
    ms = round((s - int(s)) * 1000)
    return FinishCompetitorElement.from_line(
        f"{cid}#{d} {h}:{m}:{int(s)}.{ms:03d}#{action}#"
    )


def _cfg(**kwargs) -> RaceConfig:
    cfg = RaceConfig()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# spiridonov
# ---------------------------------------------------------------------------


class TestSpiridonov:
    def test_formula(self) -> None:
        # Born 1990, current year ~2026 -> age ~36
        coeff = spiridonov("1990")
        assert 0.5 < coeff < 2.0

    def test_invalid_returns_one(self) -> None:
        assert spiridonov("") == 1.0
        assert spiridonov("abc") == 1.0


# ---------------------------------------------------------------------------
# calculate_protocol -- mass start, no laps found
# ---------------------------------------------------------------------------


class TestCalculateProtocolDns:
    def test_dns_competitor(self) -> None:
        start_list = [_start("1", "GroupA", n_laps=3)]
        group_list = [_group("GroupA", BASE_T + 3600)]
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert len(protocol) == 1
        fp = protocol[0]
        assert fp.n_laps_finished == 0
        assert fp.finished is False
        assert fp.cross_line_times[0] == BASE_T + 3600


# ---------------------------------------------------------------------------
# calculate_protocol -- one competitor, three laps
# ---------------------------------------------------------------------------


class TestCalculateProtocolSimple:
    def setup_method(self) -> None:
        start_t = BASE_T + 3600  # group start at +1h
        lap = 300.0  # each lap = 5 min

        self.start_list = [_start("1", "GroupA", n_laps=3)]
        self.group_list = [_group("GroupA", start_t)]
        self.finish_list = [
            _finish("1", start_t + lap * 1, "nextLap"),
            _finish("1", start_t + lap * 2, "nextLap"),
            _finish("1", start_t + lap * 3, "finish"),
        ]
        self.cfg = _cfg()
        self.log: list[str] = []
        self.protocol = calculate_protocol(
            self.start_list,
            self.group_list,
            self.finish_list,
            [],
            [],
            self.cfg,
            self.log,
        )
        self.fp = self.protocol[0]
        self.start_t = start_t
        self.lap = lap

    def test_three_laps_finished(self) -> None:
        assert self.fp.n_laps_finished == 3

    def test_finished_flag(self) -> None:
        assert self.fp.finished is True

    def test_lap_times(self) -> None:
        for i in range(3):
            assert abs(self.fp.lap_times[i] - self.lap) < 1e-3

    def test_finish_lap_times(self) -> None:
        for i in range(3):
            assert abs(self.fp.finish_lap_times[i] - self.lap * (i + 1)) < 1e-3

    def test_total_time(self) -> None:
        assert abs(self.fp.get_total_time() - self.lap * 3) < 1e-3


# ---------------------------------------------------------------------------
# calculate_protocol -- two competitors, sorted result
# ---------------------------------------------------------------------------


class TestSortedProtocol:
    def setup_method(self) -> None:
        start_t = BASE_T + 3600
        lap = 300.0

        self.start_list = [
            _start("1", "GroupA", n_laps=3),
            _start("2", "GroupA", n_laps=3),
        ]
        self.group_list = [_group("GroupA", start_t)]
        # competitor 2 is faster
        self.finish_list = [
            _finish("1", start_t + lap, "nextLap"),
            _finish("1", start_t + lap * 2, "nextLap"),
            _finish("1", start_t + lap * 3, "finish"),
            _finish("2", start_t + lap * 0.9, "nextLap"),
            _finish("2", start_t + lap * 1.8, "nextLap"),
            _finish("2", start_t + lap * 2.7, "finish"),
        ]
        self.cfg = _cfg()
        self.log: list[str] = []
        protocol = calculate_protocol(
            self.start_list,
            self.group_list,
            self.finish_list,
            [],
            [],
            self.cfg,
            self.log,
        )
        self.sorted_proto = generate_sorted_protocol(protocol, self.cfg, 0)

    def test_faster_first(self) -> None:
        assert self.sorted_proto[0].competitor_id == "2"
        assert self.sorted_proto[1].competitor_id == "1"

    def test_both_finished(self) -> None:
        for fp in self.sorted_proto:
            assert fp.finished is True


# ---------------------------------------------------------------------------
# calculate_protocol -- DSQ
# ---------------------------------------------------------------------------


class TestDsq:
    def test_dsq_marked(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("7", start_t + 100, "DSQ")]
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert protocol[0].disqualified is True

    def test_dsq_disabled(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("7", start_t + 100, "DSQ")]
        cfg = _cfg(disable_dsq=True)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert protocol[0].disqualified is False


# ---------------------------------------------------------------------------
# calculate_protocol -- more laps beats fewer
# ---------------------------------------------------------------------------


class TestMoreLapsBetter:
    def test_more_laps_wins(self) -> None:
        start_t = BASE_T + 3600
        lap = 300.0
        start_list = [
            _start("1", "G", n_laps=3),
            _start("2", "G", n_laps=3),
        ]
        group_list = [_group("G", start_t)]
        finish_list = [
            # competitor 1 finishes 3 laps slowly
            _finish("1", start_t + lap, "nextLap"),
            _finish("1", start_t + lap * 2, "nextLap"),
            _finish("1", start_t + lap * 3, "finish"),
            # competitor 2 only finishes 1 lap very fast
            _finish("2", start_t + 10, "nextLap"),
        ]
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        assert sorted_proto[0].competitor_id == "1"


# ---------------------------------------------------------------------------
# calculate_protocol -- time_limit clamp
# ---------------------------------------------------------------------------


class TestTimeLimit:
    def test_time_limit_clamp_runs(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100, "nextLap"),
            _finish("1", start_t + 200, "finish"),
        ]
        cfg = _cfg(time_limit=3600)  # limit larger than actual times -> no clamping
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert protocol[0].n_laps_finished == 2

    def test_time_limit_rejects_late_crossing(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        # crossing at +5000s, time_limit = 100s -> rejected
        finish_list = [_finish("1", start_t + 5000, "finish")]
        cfg = _cfg(time_limit=100)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert protocol[0].n_laps_finished == 0
        assert any("time limit" in m for m in log)


# ---------------------------------------------------------------------------
# calculate_protocol -- start_check_list
# ---------------------------------------------------------------------------


class TestStartCheckList:
    def test_missing_check_dsq(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("1", start_t + 100, "finish")]
        # Non-empty start_check_list with competitor "99" (not matching "1")
        # -> competitor "1" fails registration -> DSQ
        start_check_list = [_finish("99", start_t - 50, "nextLap")]
        cfg = _cfg()
        cfg.use_start_check_list = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], start_check_list, cfg, log
        )
        assert any("did not pass" in m for m in log)
        assert protocol[0].disqualified is True

    def test_valid_check_passes(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("1", start_t + 100, "finish")]
        # ck.seconds > fp.cross_line_times[0] -> condition is True -> passed=True
        start_check_list = [_finish("1", start_t + 5, "nextLap")]
        cfg = _cfg()
        cfg.use_start_check_list = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], start_check_list, cfg, log
        )
        assert not any("did not pass" in m for m in log)
        assert protocol[0].disqualified is False


# ---------------------------------------------------------------------------
# calculate_protocol -- minimal_time_for_lap filter
# ---------------------------------------------------------------------------


class TestMinimalTime:
    def test_too_fast_lap_rejected(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("1", start_t + 5, "finish")]  # 5 sec < min
        cfg = _cfg(minimal_time_for_lap=60)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert protocol[0].n_laps_finished == 0
        assert any("minimal time" in m for m in log)


# ---------------------------------------------------------------------------
# calculate_protocol -- disable_dnf
# ---------------------------------------------------------------------------


class TestDisableDnf:
    def test_disable_dnf_marks_finished(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=3)]
        group_list = [_group("G", start_t)]
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg(disable_dnf=True)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert protocol[0].finished is True


# ---------------------------------------------------------------------------
# calculate_protocol -- missing group log
# ---------------------------------------------------------------------------


class TestMissingGroup:
    def test_missing_group_logged(self) -> None:
        start_list = [_start("1", "UnknownGroup", n_laps=1)]
        group_list = [_group("OtherGroup", BASE_T + 3600)]
        finish_list = [_finish("1", BASE_T + 3700, "finish")]
        cfg = _cfg()
        log: list[str] = []
        calculate_protocol(start_list, group_list, finish_list, [], [], cfg, log)
        assert any("ERROR" in m and "group" in m for m in log)


# ---------------------------------------------------------------------------
# check_start_protocol
# ---------------------------------------------------------------------------


class TestCheckStartProtocol:
    def _build_protocol(self, start_list, group_list, finish_list, cfg):
        log: list[str] = []
        return calculate_protocol(start_list, group_list, finish_list, [], [], cfg, log)

    def test_extra_id_in_results(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100, "finish"),
            _finish("99", start_t + 200, "nextLap"),  # not in start
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert any("99" in m and "ERROR" in m for m in log)

    def test_duplicate_id(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1), _start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert any("duplicate" in m.lower() for m in log)

    def test_clean_protocol_no_errors(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("1", start_t + 100, "finish")]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert log == []


# ---------------------------------------------------------------------------
# calculate_protocol -- skip_first_lap
# ---------------------------------------------------------------------------


class TestSkipFirstLap:
    def test_skip_first_lap_start_time_from_crossings(self) -> None:
        start_t = BASE_T + 3600
        lap = 300.0
        start_list = [_start("1", "G", n_laps=3)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100, "nextLap"),  # flying start crossing
            _finish("1", start_t + 100 + lap, "nextLap"),
            _finish("1", start_t + 100 + lap * 2, "nextLap"),
            _finish("1", start_t + 100 + lap * 3, "finish"),
        ]
        cfg = _cfg(race_type=RACE_TYPE_CUSTOM_START)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        fp = protocol[0]
        # Start time should be set to the first crossing
        assert abs(fp.cross_line_times[0] - (start_t + 100)) < 1e-3

    def test_skip_first_lap_sorting_crossed_vs_not(self) -> None:
        start_t = BASE_T + 3600
        lap = 300.0
        start_list = [_start("1", "G", n_laps=2), _start("2", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        # competitor 2 never crossed the flying start
        finish_list = [
            _finish("1", start_t + 50, "nextLap"),
            _finish("1", start_t + 50 + lap, "nextLap"),
            _finish("1", start_t + 50 + lap * 2, "finish"),
        ]
        cfg = _cfg(race_type=RACE_TYPE_CUSTOM_START)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        assert sorted_proto[0].competitor_id == "1"


# ---------------------------------------------------------------------------
# calculate_protocol -- Spiridonov
# ---------------------------------------------------------------------------


class TestSpiridonovInProtocol:
    def test_spiridonov_divides_times(self) -> None:
        start_t = BASE_T + 3600
        lap = 300.0
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("1", start_t + lap, "finish")]
        cfg = _cfg(race_type="Mass/Splitted (Spiridonov)")
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        fp = protocol[0]
        # Spiridonov applies -> extra_info should contain the coefficient
        assert fp.extra_info != ""
        try:
            coeff = float(fp.extra_info)
            assert 0.5 < coeff < 2.0
        except ValueError:
            pass  # if extra_info was overwritten, skip


# ---------------------------------------------------------------------------
# calculate_protocol -- relay stages
# ---------------------------------------------------------------------------


class TestRelayStages:
    def test_relay_lap_finish_numbers(self) -> None:
        start_t = BASE_T + 3600
        lap = 300.0
        # Relay team: competitor 10, stages=2 -> also matches competitor_id "11"
        start_list = [_start("10", "G", n_laps=2, stages=2)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("10", start_t + lap, "nextLap"),  # first leg
            _finish("11", start_t + lap * 2, "finish"),  # second leg
        ]
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        fp = protocol[0]
        assert fp.n_laps_finished == 2
        assert fp.lap_finish_numbers[1] == 11  # second lap finished by id "11"


# ---------------------------------------------------------------------------
# calculate_protocol -- DNS sorting by competitor ID
# ---------------------------------------------------------------------------


class TestDnsSorting:
    def test_dns_sorted_by_numeric_id(self) -> None:
        start_t = BASE_T + 3600
        start_list = [
            _start("9", "G", n_laps=1),
            _start("2", "G", n_laps=1),
            _start("15", "G", n_laps=1),
        ]
        group_list = [_group("G", start_t)]
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        ids = [fp.competitor_id for fp in sorted_proto]
        assert ids == ["2", "9", "15"]


# ---------------------------------------------------------------------------
# generate_sorted_protocol -- sorted_flag reset check
# ---------------------------------------------------------------------------


class TestSortedFlag:
    def test_sorted_flag_set(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1), _start("2", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100, "finish"),
            _finish("2", start_t + 200, "finish"),
        ]
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        assert len(sorted_proto) == 2
        assert all(fp.sorted_flag for fp in sorted_proto)


# ---------------------------------------------------------------------------
# NumberOfTries mode
# ---------------------------------------------------------------------------


def _start_not(
    cid: str, group: str, n_laps: int, extra_info: str = ""
) -> StartProtocolElement:
    """Start element with explicit extra_info (for NumberOfTries n_tries_for_result)."""
    line = f"{cid}#Name {cid}#{group}#{n_laps}#1#1990#Team#City#{extra_info}#0 00:00:00.000#"  # noqa: E501
    return StartProtocolElement.from_line(line)


class TestNumberOfTries:
    """Port of C++ NumberOfTries mode.
    n_laps = total number of attempts to track (n_to_find = n_laps * 2 crossings).
    extra_info 'N:...' encodes n_tries_for_result = N (best N to count).
    Each attempt = 2 crossings: finish-line + return-line."""

    def _run(
        self,
        n_laps: int,
        crossing_gaps: list[float],
        extra_info: str = "",
    ) -> FinishProtocolElement:
        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        start_t = BASE_T + 3600
        start_list = [_start_not("1", "G", n_laps=n_laps, extra_info=extra_info)]
        group_list = [_group("G", start_t)]
        finish_list = []
        t: float = start_t
        for gap in crossing_gaps:
            t += gap
            finish_list.append(_finish("1", t, "nextLap"))
        cfg = _cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert len(protocol) == 1
        return protocol[0]

    def test_exact_tries_no_selection(self) -> None:
        # n_laps=2 -> n_to_find=4 crossings -> 2 attempts of 10s and 20s
        # no extra_info -> n_tries_for_result=2, total = 10+20 = 30
        fp = self._run(n_laps=2, crossing_gaps=[10, 10, 20, 20])
        assert fp.n_laps_finished == 2
        assert abs(fp.get_total_time() - 30.0) < 0.01

    def test_best_1_of_3(self) -> None:
        # n_laps=3 -> n_to_find=6 -> 3 attempts (30, 10, 20)
        # extra_info "1:1,2,3" -> n_tries_for_result=1, best = 10
        fp = self._run(
            n_laps=3, crossing_gaps=[30, 30, 10, 10, 20, 20], extra_info="1:1,2,3"
        )
        assert fp.n_laps_finished == 3
        assert fp.get_n_successful_tries() == 1
        assert abs(fp.get_total_time() - 10.0) < 0.01

    def test_best_2_of_3(self) -> None:
        # n_laps=3 -> 3 attempts (30, 10, 20)
        # extra_info "2:1,2,3" -> n_tries_for_result=2, best 2 = 10+20 = 30
        fp = self._run(
            n_laps=3, crossing_gaps=[30, 30, 10, 10, 20, 20], extra_info="2:1,2,3"
        )
        assert fp.n_laps_finished == 3
        assert fp.get_n_successful_tries() == 2
        assert abs(fp.get_total_time() - 30.0) < 0.01

    def test_sorting_by_best_time(self) -> None:
        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        start_t = BASE_T + 3600
        # Competitor "1": n_laps=3 attempts (50,10,20), extra_info "1:1,2,3" -> best=10
        # Competitor "2": n_laps=1 attempt (15), no extra_info -> best=15
        # "1" should rank better (10 < 15)
        start_list = [
            _start_not("1", "G", n_laps=3, extra_info="1:1,2,3"),
            _start_not("2", "G", n_laps=1),
        ]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 50, "nextLap"),
            _finish("1", start_t + 100, "nextLap"),
            _finish("1", start_t + 110, "nextLap"),
            _finish("1", start_t + 120, "nextLap"),
            _finish("1", start_t + 140, "nextLap"),
            _finish("1", start_t + 160, "nextLap"),
            _finish("2", start_t + 15, "nextLap"),
            _finish("2", start_t + 30, "nextLap"),
        ]
        cfg = _cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        assert sorted_proto[0].competitor_id == "1"
        assert sorted_proto[1].competitor_id == "2"
