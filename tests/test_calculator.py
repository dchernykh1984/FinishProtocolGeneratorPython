"""Tests for calculate_protocol, generate_sorted_protocol, and check_start_protocol."""

from __future__ import annotations

import pytest

from app.calculator import (
    _number_less,
    calculate_protocol,
    check_start_protocol,
    generate_sorted_protocol,
    report_repeated_groups,
    spiridonov,
)
from app.config import RACE_TYPE_CUSTOM_START, RaceConfig
from app.models import (
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    StartProtocolElement,
    parse_time_string,
)
from app.protocol_rows import is_printed, place_status

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

BASE_T = 15921 * 86400  # day offset used in realistic tests


@pytest.mark.parametrize("disable_dsq", [False, True])
def test_custom_start_keeps_legacy_start_at_an_earlier_dsq_mark(disable_dsq):
    cfg = RaceConfig(race_type=RACE_TYPE_CUSTOM_START, disable_dsq=disable_dsq)
    start = StartProtocolElement.from_line("1#Name#G#2#1#####")
    marks = [
        FinishCompetitorElement("1", 100, "DSQ"),
        FinishCompetitorElement("1", 200, "nextLap"),
        FinishCompetitorElement("1", 500, "nextLap"),
    ]
    fp = calculate_protocol([start], [], marks, [], [], cfg, [])[0]
    assert fp.cross_line_times[0] == 100
    assert fp.lap_times[:2] == [100, 300]
    assert fp.n_laps_finished == 2
    assert fp.finished
    assert fp.get_total_time() == 400
    assert fp.disqualified == (not disable_dsq)


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

    def test_bare_dsq_has_no_reasons(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("7", start_t + 100, "DSQ")]
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], _cfg(), []
        )
        assert protocol[0].disqualified is True
        assert protocol[0].dsq_reasons == []

    def test_dsq_reason_at_finish(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("7", start_t + 100, "DSQ: unsportsmanlike")]
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], _cfg(), []
        )
        assert protocol[0].disqualified is True
        assert protocol[0].dsq_reasons == ["finish: unsportsmanlike"]

    def test_dsq_reason_at_control_point(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        # One remote control point (CP 1) carrying a DSQ mark for competitor 7.
        remote_points = [[_finish("7", start_t + 50, "DSQ: crossed the tape")]]
        protocol = calculate_protocol(
            start_list, group_list, [], remote_points, [], _cfg(), []
        )
        assert protocol[0].disqualified is True
        assert protocol[0].dsq_reasons == ["CP 1: crossed the tape"]

    def test_dsq_reasons_from_finish_and_control_point(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("7", start_t + 100, "DSQ: insulted a referee")]
        remote_points = [[_finish("7", start_t + 50, "DSQ: cut the course")]]
        protocol = calculate_protocol(
            start_list, group_list, finish_list, remote_points, [], _cfg(), []
        )
        assert protocol[0].disqualified is True
        assert protocol[0].dsq_reasons == [
            "finish: insulted a referee",
            "CP 1: cut the course",
        ]

    def test_control_point_dsq_is_not_counted_as_a_crossing(self) -> None:
        # A DSQ mark on a control-point stream must not be treated as a lap crossing.
        start_t = BASE_T + 3600
        start_list = [_start("7", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        remote_points = [[_finish("7", start_t + 50, "DSQ: reason")]]
        protocol = calculate_protocol(
            start_list, group_list, [], remote_points, [], _cfg(), []
        )
        fp = protocol[0]
        assert all(v == -1 for v in fp.control_points[0].segment_crosses)


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


class TestAGroupWithoutAStartTime:
    """Mass start: nothing can be timed from a start that was never recorded.

    Counting from 0 timed the laps from 1970 and sorted a rider with a finish mark
    among the finishers, a delay or not, only to print him DNS afterwards.
    """

    def _run(
        self, groups: list[GroupStartElement]
    ) -> tuple[dict[str, FinishProtocolElement], list[str]]:
        t = BASE_T + 3600
        start_list = [
            _start("1", "G", n_laps=2),
            _start("2", "G", n_laps=2, delay=30.0),
            _start("3", "H", n_laps=2),
            _start("4", "H", n_laps=2),
        ]
        finish_list = [
            mark
            for bib in ("1", "2", "3")
            for mark in (_finish(bib, t + 100), _finish(bib, t + 200, "finish"))
        ] + [_finish("4", t + 100)]
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, groups, finish_list, [], [], _cfg(), log
        )
        return {fp.competitor_id: fp for fp in protocol}, log

    @pytest.mark.parametrize(
        "groups",
        [
            [_group("H", BASE_T + 3600)],
            [_group("H", BASE_T + 3600), GroupStartElement("G", 0.0)],
        ],
        ids=["not listed", "listed without a time"],
    )
    def test_its_riders_did_not_start_and_ride_no_lap(
        self, groups: list[GroupStartElement]
    ) -> None:
        riders, log = self._run(groups)
        for bib in ("1", "2"):
            assert riders[bib].n_laps_finished == 0
            assert not riders[bib].finished
            assert place_status(riders[bib], 1, _cfg()) == ("DNS", "dns")
        assert riders["3"].finished and riders["3"].n_laps_finished == 2
        assert [m for m in log if "no start time" in m] == [
            "ERROR: group G has no start time in the group times file, but its riders "
            "have marks: none of their laps can be timed"
        ]

    @pytest.mark.parametrize(
        ("finish_list", "points", "level"),
        [
            ([], [], "WARNING"),
            ([_finish("1", BASE_T + 100, "DSQ")], [], "WARNING"),
            ([], [[_finish("1", BASE_T + 100)]], "ERROR"),
        ],
        ids=["not started yet", "a DSQ is no mark", "a control point mark"],
    )
    def test_a_warning_until_one_of_its_riders_has_a_mark(
        self,
        finish_list: list[FinishCompetitorElement],
        points: list[list[FinishCompetitorElement]],
        level: str,
    ) -> None:
        # A later wave not started yet is a normal moment of a race; marks that
        # nothing can time are not (maintainer, 2026-11-24).
        log: list[str] = []
        cfg = _cfg(n_remote_points=len(points))
        calculate_protocol(
            [_start("1", "G"), _start("2", "G")], [], finish_list, points, [], cfg, log
        )
        assert [m.split(":")[0] for m in log if "no start time" in m] == [level]

    def test_they_sort_after_every_rider_who_started(self) -> None:
        # Behind a rider who started and did not finish: DNF before DNS.
        riders, _log = self._run([_group("H", BASE_T + 3600)])
        order = generate_sorted_protocol(list(riders.values()), _cfg(), 0)
        assert [fp.competitor_id for fp in order] == ["3", "4", "1", "2"]

    def test_disable_dns_makes_them_dnf_and_prints_them_as_such(self) -> None:
        riders, _log = self._run([_group("H", BASE_T + 3600)])
        cfg = _cfg(disable_dns=True, print_dnf=True, print_dns=False)
        for bib in ("1", "2"):
            assert place_status(riders[bib], 1, cfg) == ("DNF", "dnf")
            assert is_printed(riders[bib], cfg)

    def test_spiridonov_still_shows_their_coefficient(self) -> None:
        cfg = _cfg(race_type="Mass/Splitted (Spiridonov)")
        protocol = calculate_protocol([_start("1", "G")], [], [], [], [], cfg, [])
        assert protocol[0].extra_info == f"{spiridonov('1990'):.4f}"

    def test_disable_dnf_still_counts_them_as_finished(self) -> None:
        log: list[str] = []
        protocol = calculate_protocol(
            [_start("1", "G", n_laps=2)], [], [], [], [], _cfg(disable_dnf=True), log
        )
        assert protocol[0].finished and protocol[0].n_laps_finished == 0


def test_a_group_listed_twice_is_an_error() -> None:
    # A false start is started again without saving, so a second line is a slip.
    log: list[str] = []
    groups = [_group("A", BASE_T), _group("B", BASE_T), _group("A", BASE_T + 60)]
    report_repeated_groups(groups, log)
    assert log == [
        "ERROR: group A is listed 2 times in the group times file; a group is saved "
        "once, after a start that went well"
    ]


class TestStartCheckList:
    def test_a_missed_check_is_dns_not_dsq(self) -> None:
        # He broke no rule on the course, so he did not start rather than was
        # disqualified, and the laps he rode stay his (specs/001-start-check-dns).
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [_finish("1", start_t + 100, "finish")]
        # Non-empty start_check_list with competitor "99" (not matching "1")
        start_check_list = [_finish("99", start_t - 50, "nextLap")]
        cfg = _cfg()
        cfg.use_start_check_list = True
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], start_check_list, cfg, log
        )
        assert any("did not pass" in m for m in log)
        assert protocol[0].disqualified is False
        assert protocol[0].missed_start_check is True
        assert protocol[0].n_laps_finished == 1 and protocol[0].finished
        assert place_status(protocol[0], 1, cfg) == ("DNS", "dns")

    def _four(
        self, checked: tuple[str, ...] = ("1", "2"), disable_dns: bool = False
    ) -> tuple[list[FinishProtocolElement], RaceConfig, list[str]]:
        """A finisher, a DNF, the fastest rider without a check mark, and a DSQ."""
        t = BASE_T + 3600
        start_list = [_start(bib, "G", n_laps=2) for bib in ("1", "2", "3", "4")]
        finish_list = [
            _finish("1", t + 100),
            _finish("1", t + 200, "finish"),
            _finish("2", t + 110),
            _finish("3", t + 90),
            _finish("3", t + 180, "finish"),
            _finish("4", t + 95),
            _finish("4", t + 190, "finish"),
            _finish("4", t + 191, "DSQ"),
        ]
        checks = [_finish(bib, t - 30) for bib in checked]
        cfg = _cfg(
            use_start_check_list=True,
            start_registration_period=60,
            disable_dns=disable_dns,
        )
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, [_group("G", t)], finish_list, [], checks, cfg, log
        )
        return generate_sorted_protocol(protocol, cfg, 0), cfg, log

    def test_the_statuses_go_finishers_dnf_dns_dsq(self) -> None:
        # The DNS rode the fastest, and still goes after the rider who did not
        # finish; the DSQ missed the check too and is DSQ all the same.
        order, cfg, log = self._four()
        assert [
            (fp.competitor_id, place_status(fp, place, cfg)[0])
            for place, fp in enumerate(order, 1)
        ] == [
            ("1", "1"),
            ("2", "DNF"),
            ("3", "DNS"),
            ("4", "DSQ"),
        ]
        assert [m for m in log if "did not pass" in m] == [
            "ERROR: 3 did not pass start registration",
            "ERROR: 4 did not pass start registration",
        ]

    def test_disable_dns_places_him_by_his_result(self) -> None:
        # Nobody is DNS: the fastest rider is first, and the log still says why
        # he would not have been.
        order, cfg, log = self._four(disable_dns=True)
        assert [
            (fp.competitor_id, place_status(fp, place, cfg)[0])
            for place, fp in enumerate(order, 1)
        ] == [
            ("3", "1"),
            ("1", "2"),
            ("2", "DNF"),
            ("4", "DSQ"),
        ]
        assert "ERROR: 3 did not pass start registration" in log

    def test_a_rider_who_never_started_is_not_checked(self) -> None:
        # Custom Start without a single mark: no start to check his mark against.
        start_t = BASE_T + 3600
        cfg = _cfg(race_type=RACE_TYPE_CUSTOM_START, use_start_check_list=True)
        log: list[str] = []
        protocol = calculate_protocol(
            [_start("7", "G", n_laps=1)],
            [],
            [],
            [],
            [_finish("7", start_t)],
            cfg,
            log,
        )
        assert not any("registration" in m for m in log)
        assert not protocol[0].missed_start_check
        assert place_status(protocol[0], 1, cfg) == ("DNS", "dns")

    def test_a_check_list_without_marks_checks_nobody(self) -> None:
        start_t = BASE_T + 3600
        cfg = _cfg(use_start_check_list=True)
        protocol = calculate_protocol(
            [_start("1", "G", n_laps=1)],
            [_group("G", start_t)],
            [_finish("1", start_t + 100, "finish")],
            [],
            [],
            cfg,
            [],
        )
        assert not protocol[0].missed_start_check and protocol[0].finished

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

    def test_two_finishers_printed_the_same_are_reported(self) -> None:
        # One digit after the point: 100.06 s and 100.14 s both come out as the same
        # tenth, so the protocol shows one time and two places, and those places are
        # what the finals are seeded from.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1), _start("2", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.06, "finish"),
            _finish("2", start_t + 100.14, "finish"),
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        shared = [m for m in log if "are all printed as" in m]
        assert shared and shared[0].startswith("WARNING:")
        assert "1" in shared[0] and "2" in shared[0]

    def test_finishers_the_protocol_tells_apart_are_not_reported(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1), _start("2", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.04, "finish"),
            _finish("2", start_t + 100.26, "finish"),
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "are all printed as" in m]

    def test_two_groups_on_one_time_are_not_a_tie(self) -> None:
        # Different groups ride different races; only places inside one are compared.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1), _start("2", "H", n_laps=1)]
        group_list = [_group("G", start_t), _group("H", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "finish"),
            _finish("2", start_t + 100.0, "finish"),
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "are all printed as" in m]

    def test_one_crossing_recorded_twice_is_reported(self) -> None:
        # A second timekeeper on the same finish line: the site merges every device's
        # stream of the competition, so each crossing arrives twice.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "finish"),
            _finish("1", start_t + 100.2, "finish"),
        ]
        cfg = _cfg(minimal_time_for_lap=10)
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        doubled = [m for m in log if "one crossing recorded twice" in m]
        assert doubled and doubled[0].startswith("ERROR:")
        assert "1" in doubled[0]

    def test_honest_laps_are_not_reported_as_doubled(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "nextLap"),
            _finish("1", start_t + 200.0, "finish"),
        ]
        cfg = _cfg(minimal_time_for_lap=10)
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "one crossing recorded twice" in m]

    def test_number_of_tries_is_not_asked_about_shared_times(self) -> None:
        # The attempt count is printed beside the time and is what ranks them, so a
        # shared total time is not a result nobody can read off the page.
        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=2), _start("2", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 10, "nextLap"),
            _finish("1", start_t + 20, "finish"),
            _finish("2", start_t + 30, "nextLap"),
            _finish("2", start_t + 40, "finish"),
        ]
        cfg = _cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES)
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "are all printed as" in m]

    def test_a_stage_change_beside_a_finish_is_not_a_double_mark(self) -> None:
        # The results file carries records that are not readings of the line, and the
        # finals are handed the file as it stands.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "finish"),
            _finish("1", start_t + 100.2, "nextStage"),
        ]
        cfg = _cfg(minimal_time_for_lap=10)
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "one crossing recorded twice" in m]

    def test_a_real_dead_heat_is_not_reported_as_unreadable(self) -> None:
        # Both rode the same millisecond, so the protocol gives them one place and
        # there is nothing the page is failing to show.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1), _start("2", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "finish"),
            _finish("2", start_t + 100.0, "finish"),
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "are all printed as" in m]

    def test_a_lapped_rider_crossing_with_the_leader_is_not_reported(self) -> None:
        # Same instant, different lap: nothing about their places is unclear.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=2), _start("2", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 50.0, "nextLap"),
            _finish("1", start_t + 100.0, "finish"),
            _finish("2", start_t + 100.0, "finish"),
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "are all printed as" in m]

    def test_without_the_minimal_lap_time_nothing_is_called_a_double(self) -> None:
        # The setting is what says how close two crossings have to be to be the same
        # crossing; left at nothing it asks nothing.
        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=1)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "finish"),
            _finish("1", start_t + 100.2, "finish"),
        ]
        cfg = _cfg()
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "one crossing recorded twice" in m]

    def test_number_of_tries_marks_are_not_called_doubles(self) -> None:
        # There the setting is the shortest attempt, and the marks come in
        # start/finish pairs with as little rest between attempts as the rider likes.
        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        start_t = BASE_T + 3600
        start_list = [_start("1", "G", n_laps=2)]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 100.0, "nextLap"),
            _finish("1", start_t + 100.2, "finish"),
        ]
        cfg = _cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES, minimal_time_for_lap=10)
        protocol = self._build_protocol(start_list, group_list, finish_list, cfg)
        log: list[str] = []
        check_start_protocol(protocol, finish_list, start_list, [], cfg, log)
        assert not [m for m in log if "one crossing recorded twice" in m]

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


class TestDnfBeforeDns:
    def test_dnf_zero_laps_before_dns(self) -> None:
        """DNF (group started, 0 laps) must sort before DNS (group not found)."""
        start_t = BASE_T + 3600
        # competitor "1": group has no start time (DNS)
        # competitor "5": group started but 0 laps crossed (DNF)
        start_list = [_start("1", "NoGroup"), _start("5", "Started")]
        group_list = [_group("Started", start_t)]
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        ids = [fp.competitor_id for fp in sorted_proto]
        # "5" (DNF, group started) must appear before "1" (DNS, group not found)
        assert ids == ["5", "1"]

    def test_dnf_zero_laps_before_dns_with_smaller_delay(self) -> None:
        """DNF (group started) beats DNS even when DNS has a smaller start_delay."""
        start_t = BASE_T + 3600
        # id=1: no group start time (DNS), delay=0
        # id=5: group started (DNF, 0 laps), delay=10
        start_list = [
            _start("1", "NoGroup", delay=0.0),
            _start("5", "Started", delay=10.0),
        ]
        group_list = [_group("Started", start_t)]
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        ids = [fp.competitor_id for fp in sorted_proto]
        assert ids == ["5", "1"]

    def test_dns_sorted_by_id_among_themselves(self) -> None:
        """Two DNS athletes (same absent group) must still sort by numeric id."""
        start_list = [_start("9", "NoGroup"), _start("2", "NoGroup")]
        group_list: list[GroupStartElement] = []
        finish_list: list[FinishCompetitorElement] = []
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        ids = [fp.competitor_id for fp in sorted_proto]
        assert ids == ["2", "9"]


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


class TestNumberTieBreak:
    """Ascending number order is the lowest-priority sort tie-breaker (everywhere)."""

    def test_number_less_numeric(self) -> None:
        assert _number_less("9", "10") is True
        assert _number_less("10", "9") is False
        assert _number_less("3", "30") is True

    def test_number_less_non_numeric_is_string_order(self) -> None:
        # "B10" < "B9" lexicographically ('1' < '9'); a mixed pair also falls to string.
        assert _number_less("B10", "B9") is True
        assert _number_less("A2", "B10") is True
        assert _number_less("5", "x") is True

    def test_equal_finishers_sorted_by_number_not_file_order(self) -> None:
        """Fully-equal finishers resolve to ascending number order, not file order."""
        start_t = BASE_T + 3600
        start_list = [_start(c, "G", n_laps=1) for c in ("30", "10", "3")]
        group_list = [_group("G", start_t)]
        # every competitor finishes the single lap at the same instant -> a total tie
        finish_list = [_finish(c, start_t + 100, "finish") for c in ("30", "10", "3")]
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        assert [fp.competitor_id for fp in sorted_proto] == ["3", "10", "30"]

    def test_legacy_tries_riders_without_an_attempt_go_by_number(self) -> None:
        # No completed attempt totals infinity: two such riders go by number, never into
        # an OverflowError that would leave the run without a protocol.
        from protocol_scenarios import _cfg as scenario_cfg
        from protocol_scenarios import _mark, _run

        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        cfg = scenario_cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES, attempt_rules_json="[]")
        lines = [f"{bib}#Rider {bib}#W#3#1#1990###1:1,2,3#" for bib in (3, 1, 2)]
        race = _run(cfg, lines, [], [_mark(3, 1000), _mark(3, 1150)])
        assert [fp.competitor_id for fp in race.protocol] == ["3", "1", "2"]

    def test_results_equal_to_the_millisecond_go_by_number(self) -> None:
        # Custom Start: a result is the difference of the rider's own two marks, so
        # two riders who rode the very same 39.363 hold floats 2.4e-7 apart
        # according to the time of day they went off. That noise decided which of
        # them was placed first -- and in the seeding file, which half of the finals
        # ladder he was sent to -- instead of the rule that a tie goes by number.
        def stamp(ms: int) -> str:
            seconds, frac = divmod(ms, 1000)
            return f"20765 00:00:{seconds:02d}.{frac:03d}"

        start_list = [_start(c, "G", n_laps=1) for c in ("5", "3")]
        finish_list = [
            _finish(cid, parse_time_string(stamp(ms)), "nextLap")
            for cid, begin in (("5", 0), ("3", 662))
            for ms in (begin, begin + 39363)
        ]
        cfg = _cfg(race_type=RACE_TYPE_CUSTOM_START)
        protocol = calculate_protocol(
            start_list, [_group("G", 0.0)], finish_list, [], [], cfg, []
        )
        # The two floats really are different, and the faster one is the higher bib.
        assert protocol[0].finish_lap_times[0] < protocol[1].finish_lap_times[0]
        ordered = generate_sorted_protocol(protocol, cfg, 0)
        assert [fp.competitor_id for fp in ordered] == ["3", "5"]

    def test_equal_finishers_non_numeric_ids_sorted_as_string(self) -> None:
        start_t = BASE_T + 3600
        start_list = [_start(c, "G", n_laps=1) for c in ("B9", "B10", "A2")]
        group_list = [_group("G", start_t)]
        finish_list = [_finish(c, start_t + 100, "finish") for c in ("B9", "B10", "A2")]
        cfg = _cfg()
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        sorted_proto = generate_sorted_protocol(protocol, cfg, 0)
        assert [fp.competitor_id for fp in sorted_proto] == ["A2", "B10", "B9"]


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

    def test_exact_tries_all_selected(self) -> None:
        # n_laps=2, extra_info "2:1,2" -> n_tries_for_result=2, all attempts selected
        # 2 attempts of 10s and 20s -> total = 10+20 = 30
        fp = self._run(n_laps=2, crossing_gaps=[10, 10, 20, 20], extra_info="2:1,2")
        assert fp.n_laps_finished == 2
        assert abs(fp.get_total_time() - 30.0) < 0.01

    def test_invalid_extra_info_produces_error(self) -> None:
        # empty extra_info is invalid in NumberOfTries mode (C++ checkAttemptsString())
        # calculator overrides n_tries_for_result=0; get_total_time() returns 0
        from app.config import RACE_TYPE_NUMBER_OF_TRIES

        start_t = BASE_T + 3600
        start_list = [_start_not("1", "G", n_laps=2, extra_info="")]
        group_list = [_group("G", start_t)]
        finish_list = [
            _finish("1", start_t + 10, "nextLap"),
            _finish("1", start_t + 20, "nextLap"),
            _finish("1", start_t + 30, "nextLap"),
            _finish("1", start_t + 50, "nextLap"),
        ]
        cfg = _cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES)
        log: list[str] = []
        protocol = calculate_protocol(
            start_list, group_list, finish_list, [], [], cfg, log
        )
        assert any("invalid NumberOfTries" in m for m in log)
        assert protocol[0].n_tries_for_result == 0
        assert protocol[0].get_total_time() == 0.0

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
