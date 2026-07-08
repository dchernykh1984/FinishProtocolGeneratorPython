"""Tests for build_live_stats (place/qty/gaps/laps, DSQ handling, toggles)."""

from __future__ import annotations

from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import RaceConfig
from app.live_stats import build_live_stats
from app.models import (
    FinishCompetitorElement,
    GroupStartElement,
    StartProtocolElement,
)

BASE_T = 15921 * 86400
START_T = BASE_T + 3600


def _start(cid: str, group: str, n_laps: int = 2) -> StartProtocolElement:
    return StartProtocolElement.from_line(
        f"{cid}#Name {cid}#{group}#{n_laps}#1#1990#Team#City##0 00:00:00.000#"
    )


def _group(gid: str, seconds: float) -> GroupStartElement:
    d = int(seconds // 86400)
    rem = seconds - d * 86400
    h = int(rem // 3600)
    rem -= h * 3600
    m = int(rem // 60)
    s = int(rem - m * 60)
    return GroupStartElement.from_line(f"{gid}#{d} {h}:{m}:{s}.000#")


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
    cfg.send_group_statistics = True
    cfg.send_absolute_statistics = True
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    return cfg


def _run(start_list, finish_list, cfg, group_list=None):
    log: list[str] = []
    protocol = calculate_protocol(
        start_list, group_list or [], finish_list, [], [], cfg, log
    )
    return generate_sorted_protocol(protocol, cfg, 0)


def _one_group_scenario(cfg):
    # One group, mass start; 1 does 2 laps, 2 does 2 laps slower, 3 does 1 lap (DNF).
    start_list = [_start("1", "G"), _start("2", "G"), _start("3", "G")]
    group_list = [_group("G", START_T)]
    finish_list = [
        _finish("1", START_T + 100, "nextLap"),
        _finish("1", START_T + 200, "nextLap"),
        _finish("2", START_T + 120, "nextLap"),
        _finish("2", START_T + 230, "nextLap"),
        _finish("3", START_T + 150, "nextLap"),
    ]
    return _run(start_list, finish_list, cfg, group_list)


class TestPlaceQtyLaps:
    def test_places_and_qty_absolute(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert stats["1"]["place_abs"] == "1"
        assert stats["2"]["place_abs"] == "2"
        assert stats["3"]["place_abs"] == "3"  # DNF still gets a number
        assert stats["1"]["qty_abs"] == "3"

    def test_laps_done_over_total(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert stats["1"]["laps"] == "2/2"
        assert stats["3"]["laps"] == "1/2"


class TestGaps:
    def test_gap_to_prev_and_next_same_lap(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        # 1 and 2 both did 2 laps: 200 vs 230 -> 30s.
        assert stats["2"]["gap_prev_abs"] == "+0:30"
        assert stats["1"]["gap_next_abs"] == "+0:30"

    def test_leader_has_no_gap_prev_last_has_no_gap_next(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert "gap_prev_abs" not in stats["1"]
        assert "gap_next_abs" not in stats["3"]

    def test_gap_across_lap_difference_uses_common_lap(self):
        # 2 (2 laps) vs 3 (1 lap): compared at lap 1 -> 3 is 150, 2 is 120 -> 30s.
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert stats["2"]["gap_next_abs"] == "+0:30"
        assert stats["3"]["gap_prev_abs"] == "+0:30"


class TestDsq:
    def _scenario_with_dsq(self, cfg):
        start_list = [_start("1", "G"), _start("2", "G"), _start("3", "G")]
        group_list = [_group("G", START_T)]
        finish_list = [
            _finish("1", START_T + 100, "nextLap"),
            _finish("1", START_T + 200, "nextLap"),
            _finish("2", START_T + 120, "nextLap"),
            _finish("2", START_T + 230, "nextLap"),
            _finish("2", START_T + 300, "DSQ"),
            _finish("3", START_T + 150, "nextLap"),
        ]
        return _run(start_list, finish_list, cfg, group_list)

    def test_dsq_shows_dsq_and_is_excluded_from_numbering(self):
        cfg = _cfg()
        stats = build_live_stats(self._scenario_with_dsq(cfg), cfg)
        assert stats["2"]["place_abs"] == "DSQ"
        assert "gap_prev_abs" not in stats["2"]
        assert "gap_next_abs" not in stats["2"]
        # 1 and 3 are numbered 1 and 2 (DSQ 2 skipped), qty still counts everyone.
        assert stats["1"]["place_abs"] == "1"
        assert stats["3"]["place_abs"] == "2"
        assert stats["1"]["qty_abs"] == "3"

    def test_dsq_still_reports_laps(self):
        cfg = _cfg()
        stats = build_live_stats(self._scenario_with_dsq(cfg), cfg)
        assert stats["2"]["laps"] == "2/2"


class TestGroupVsAbsolute:
    def _two_group_scenario(self, cfg):
        start_list = [
            _start("1", "A"),
            _start("2", "A"),
            _start("3", "B"),
        ]
        group_list = [_group("A", START_T), _group("B", START_T)]
        finish_list = [
            _finish("1", START_T + 100, "nextLap"),
            _finish("1", START_T + 200, "nextLap"),
            _finish("2", START_T + 120, "nextLap"),
            _finish("2", START_T + 240, "nextLap"),
            _finish("3", START_T + 110, "nextLap"),
            _finish("3", START_T + 210, "nextLap"),
        ]
        return _run(start_list, finish_list, cfg, group_list)

    def test_group_place_is_within_group(self):
        cfg = _cfg()
        stats = build_live_stats(self._two_group_scenario(cfg), cfg)
        # Absolute: 1 (200) < 3 (210) < 2 (240).
        assert stats["1"]["place_abs"] == "1"
        assert stats["3"]["place_abs"] == "2"
        assert stats["2"]["place_abs"] == "3"
        # Group A has 1 and 2; group B has only 3.
        assert stats["1"]["place_group"] == "1"
        assert stats["2"]["place_group"] == "2"
        assert stats["1"]["qty_group"] == "2"
        assert stats["3"]["place_group"] == "1"
        assert stats["3"]["qty_group"] == "1"


class TestToggles:
    def test_group_only(self):
        cfg = _cfg(send_group_statistics=True, send_absolute_statistics=False)
        stats = build_live_stats(_one_group_scenario(cfg), cfg)
        assert "place_group" in stats["1"]
        assert "place_abs" not in stats["1"]
        assert "laps" in stats["1"]

    def test_absolute_only(self):
        cfg = _cfg(send_group_statistics=False, send_absolute_statistics=True)
        stats = build_live_stats(_one_group_scenario(cfg), cfg)
        assert "place_abs" in stats["1"]
        assert "place_group" not in stats["1"]

    def test_both_off_returns_empty(self):
        cfg = _cfg(send_group_statistics=False, send_absolute_statistics=False)
        stats = build_live_stats(_one_group_scenario(cfg), cfg)
        assert stats == {}


class TestGapLeader:
    def test_gap_to_scope_leader(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        # Leader is 1 (200); 2 is +0:30 at lap 2, 3 is +0:50 at their last lap (lap 1).
        assert stats["2"]["gap_leader_abs"] == "+0:30"
        assert stats["3"]["gap_leader_abs"] == "+0:50"
        # One group here, so the group leader gap matches.
        assert stats["2"]["gap_leader_group"] == "+0:30"

    def test_leader_has_no_gap_leader(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert "gap_leader_abs" not in stats["1"]
        assert "gap_leader_group" not in stats["1"]


class TestGapDelta:
    def test_per_lap_delta_when_gap_grows(self):
        # 1 vs 2: gap 20s at lap 1 -> 30s at lap 2, so it grew by 10s.
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert stats["2"]["gap_prev_abs_delta"] == "+0:10"
        assert stats["1"]["gap_next_abs_delta"] == "+0:10"
        assert stats["2"]["gap_prev_group_delta"] == "+0:10"

    def test_delta_absent_with_only_one_common_lap(self):
        # 3 has done a single lap, so no previous-lap gap exists to compare.
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert "gap_prev_abs_delta" not in stats["3"]

    def test_delta_negative_when_gap_shrinks(self):
        start_list = [_start("1", "G"), _start("2", "G")]
        group_list = [_group("G", START_T)]
        finish_list = [
            _finish("1", START_T + 100, "nextLap"),
            _finish("1", START_T + 230, "nextLap"),
            _finish("2", START_T + 140, "nextLap"),  # 40s behind at lap 1
            _finish("2", START_T + 250, "nextLap"),  # only 20s behind at lap 2
        ]
        cfg = _cfg()
        stats = build_live_stats(_run(start_list, finish_list, cfg, group_list), cfg)
        assert stats["2"]["gap_prev_abs"] == "+0:20"
        # gap went 40s -> 20s over the last lap: shrank by 20s.
        assert stats["2"]["gap_prev_abs_delta"] == "-0:20"


class TestGapLeaderDelta:
    def test_per_lap_delta_of_leader_gap(self):
        # 2 vs leader 1: gap 20s at lap 1 -> 30s at lap 2, so it grew by 10s.
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert stats["2"]["gap_leader_abs_delta"] == "+0:10"
        assert stats["2"]["gap_leader_group_delta"] == "+0:10"

    def test_leader_has_no_leader_delta(self):
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert "gap_leader_abs_delta" not in stats["1"]

    def test_leader_delta_absent_with_one_common_lap(self):
        # 3 shares only lap 1 with the leader, so there is no previous lap to compare.
        stats = build_live_stats(_one_group_scenario(_cfg()), _cfg())
        assert stats["3"]["gap_leader_abs"] == "+0:50"
        assert "gap_leader_abs_delta" not in stats["3"]

    def test_leader_delta_negative_when_gap_shrinks(self):
        start_list = [_start("1", "G"), _start("2", "G")]
        group_list = [_group("G", START_T)]
        finish_list = [
            _finish("1", START_T + 100, "nextLap"),
            _finish("1", START_T + 230, "nextLap"),
            _finish("2", START_T + 140, "nextLap"),  # 40s behind leader at lap 1
            _finish("2", START_T + 250, "nextLap"),  # 20s behind leader at lap 2
        ]
        cfg = _cfg()
        stats = build_live_stats(_run(start_list, finish_list, cfg, group_list), cfg)
        assert stats["2"]["gap_leader_abs"] == "+0:20"
        assert stats["2"]["gap_leader_abs_delta"] == "-0:20"


class TestNewKeysRespectToggles:
    def test_group_only_omits_abs_leader_and_delta(self):
        cfg = _cfg(send_group_statistics=True, send_absolute_statistics=False)
        stats = build_live_stats(_one_group_scenario(cfg), cfg)
        assert "gap_leader_group" in stats["2"]
        assert "gap_prev_group_delta" in stats["2"]
        assert "gap_leader_group_delta" in stats["2"]
        assert "gap_leader_abs" not in stats["2"]
        assert "gap_prev_abs_delta" not in stats["2"]
        assert "gap_leader_abs_delta" not in stats["2"]
