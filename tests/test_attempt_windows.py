"""Separate start/finish streams, incomplete windows and chronological splits."""

import pytest

from app.attempt_rules import AttemptRule, rules_json
from app.calculator import calculate_protocol, check_start_protocol
from app.config import RACE_TYPE_NUMBER_OF_TRIES, RaceConfig
from app.html_writer import write_absolute_protocol, write_group_protocol
from app.live_stats import build_live_stats
from app.models import FinishCompetitorElement, StartProtocolElement


def marks(*times):
    return [FinishCompetitorElement("1", t, "nextLap") for t in times]


def run(starts=None, points=None, **settings):
    if starts is None:
        starts = marks(1000, 1100, 1200)
    if points is None:
        points = [
            marks(1010, 1108, 1205),
            marks(1020, 1118, 1215),
            marks(1030, 1128, 1220),
        ]
    cfg = RaceConfig(
        race_type=RACE_TYPE_NUMBER_OF_TRIES,
        n_remote_points=len(points),
        attempt_rules_json=rules_json((AttemptRule("R", 1, (2, 3), "asc"),)),
        **settings,
    )
    start = StartProtocolElement.from_line("1#Name#G#3#1#1990#T#C#Free text#")
    log = []
    fp = calculate_protocol([start], [], starts, points, [], cfg, log)[0]
    check_start_protocol([fp], starts, [start], points, cfg, log)
    return fp, cfg, log


def test_windows_use_point_zero_starts_and_highest_point_finishes():
    fp, _, log = run()
    assert fp.lap_times[:3] == [30, 28, 20]
    assert fp.get_total_time() == 20
    assert fp.n_laps_finished == 3
    assert fp.control_points[0].segment_times == [10, 10, 10]
    assert fp.control_points[1].segment_times == [8, 10, 10]
    assert not any("crossings, expected" in message for message in log)


def test_missing_finish_keeps_attempt_numbers_and_does_not_borrow_next_finish():
    fp, _, log = run(
        points=[marks(1010, 1108, 1205), marks(1020, 1118, 1215), marks(1128, 1220)]
    )
    assert fp.lap_times[:3] == [0, 28, 20]
    assert fp.n_laps_finished == 2
    assert not fp.lap_completed(0)
    assert fp.lap_completed(2)
    assert fp.counted_attempts() == [2]
    assert fp.finished
    assert fp.attempt_closed[0]
    assert any("attempt 1 not finished" in message for message in log)


def test_missing_intermediate_keeps_finish_time_and_marks_unknown_segment():
    fp, _, _ = run(
        points=[marks(1108, 1205), marks(1020, 1118, 1215), marks(1030, 1128, 1220)]
    )
    assert fp.lap_times[0] == 30
    assert fp.control_points[0].segment_times == [-1, -2, 10]
    assert fp.control_points[0].segment_crosses[0] == -1


def test_out_of_order_point_is_not_used_as_a_negative_segment():
    fp, _, _ = run(points=[marks(1020), marks(1010), marks(1030, 1128, 1220)])
    assert fp.lap_times[0] == 30
    assert fp.control_points[0].segment_times == [20, -1, -2]


def test_latest_unfinished_attempt_can_have_partial_splits():
    fp, _, _ = run(
        points=[marks(1010, 1108, 1205), marks(1020, 1118), marks(1030, 1128)]
    )
    assert fp.attempts_seen == 3
    assert not fp.attempt_closed[2]
    assert not fp.lap_completed(2)
    assert fp.control_points[2].segment_times == [5, -1, -1]
    assert fp.get_total_time() == 28
    assert fp.finished


def test_finish_mark_cannot_replace_an_incomplete_primary_rule():
    fp, _, _ = run(
        starts=[FinishCompetitorElement("1", 1000, "finish")],
        points=[[], [], marks(1030)],
    )
    assert fp.lap_completed(0)
    assert not fp.finished


def test_finish_is_earliest_in_its_window_and_ignores_points_after_finish():
    fp, _, _ = run(
        points=[marks(1010, 1035), marks(1020, 1040), marks(1045, 1030, 1128, 1220)]
    )
    assert fp.lap_times[0] == 30
    assert fp.control_points[0].segment_times == [10, 10, 10]


def test_duplicates_do_not_create_phantom_attempts():
    fp, _, _ = run(starts=marks(1200, 1000, 1000, 1100))
    assert fp.lap_times[:3] == [30, 28, 20]


def test_no_control_points_remains_strict_alternating_pairs():
    fp, _, _ = run(starts=marks(1000, 1030, 1100, 1128, 1200, 1220), points=[])
    assert fp.lap_times[:3] == [30, 28, 20]
    assert fp.get_total_time() == 20


def test_two_streams_have_no_intermediate_segments():
    fp, _, _ = run(points=[marks(1030, 1128, 1220)])
    assert fp.lap_times[:3] == [30, 28, 20]
    assert len(fp.control_points[0].segment_times) == 1


def test_penalties_and_time_cap_apply_inside_the_attempt():
    first = marks(1010, 1108, 1205)
    first[1].penalty = 7
    fp, _, _ = run(
        points=[first, marks(1020, 1118, 1215), marks(1030, 1128, 1220)], time_limit=32
    )
    assert fp.lap_times[:3] == [30, 32, 20]


def test_penalty_at_duplicate_crossing_timestamp_is_kept_and_explained():
    first = marks(1010, 1108, 1205)
    first.append(FinishCompetitorElement("1", 1108, "Penalty <judge>", 7))
    fp, _, _ = run(points=[first, marks(1020, 1118, 1215), marks(1030, 1128, 1220)])
    assert fp.lap_times[1] == 35
    assert "Penalty &lt;judge&gt;:7sec" in fp.lap_penalty[1]
    assert "<judge>" not in fp.lap_penalty[1]


def test_minimal_time_check_does_not_shift_later_attempts():
    fp, _, log = run(minimal_time_for_lap=25)
    assert fp.lap_times[:3] == [30, 28, 0]
    assert fp.get_total_time() == 28
    assert any("faster than minimal" in message for message in log)


def test_dsq_is_not_a_start_but_still_disqualifies():
    starts = [
        FinishCompetitorElement("1", 900, "DSQ: reason"),
        *marks(1000, 1100, 1200),
    ]
    fp, _, _ = run(starts=starts)
    assert fp.lap_times[:3] == [30, 28, 20]
    assert fp.disqualified
    assert fp.dsq_reasons


@pytest.mark.parametrize("scope", ["group", "absolute"])
def test_html_has_splits_and_keeps_failed_attempt_slot(tmp_path, scope):
    from app.models import GroupStartElement

    fp, cfg, _ = run(
        points=[marks(1010, 1108, 1205), marks(1020, 1118, 1215), marks(1128, 1220)],
        disable_dnf=True,
        hide_empty_columns=True,
    )
    path = tmp_path / "result.html"
    writer = write_group_protocol if scope == "group" else write_absolute_protocol
    writer(str(path), [fp], [GroupStartElement("G", 900)], cfg, 2)
    html = path.read_text(encoding="utf-8")
    assert "(1 split)" in html
    assert "(3 split)" in html
    assert "DNF</td>" in html
    assert "<B>00:00:20.0</B>" in html
    assert "Lap 3" in html
    assert '<td id="0_Lap 6 splits_1" ALIGN=center>00:00:05.0</td>' in html


def test_live_stats_use_counted_attempts_despite_a_hole():
    fp, cfg, _ = run(
        points=[[], [], marks(1128, 1220)],
        send_group_statistics=True,
        send_absolute_statistics=True,
    )
    stats = build_live_stats([fp], cfg)
    assert stats["1"]["laps"] == "1/1"


def test_missing_configured_stream_fails_instead_of_switching_timing_mode():
    cfg = RaceConfig(race_type=RACE_TYPE_NUMBER_OF_TRIES, n_remote_points=2)
    with pytest.raises(ValueError, match="every configured"):
        calculate_protocol([], [], [], [], [], cfg, [])
