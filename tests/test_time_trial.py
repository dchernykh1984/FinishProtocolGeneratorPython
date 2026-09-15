"""Tests for the time-trial start schedule, selection and board layout."""

from __future__ import annotations

from datetime import datetime

from app.models import GroupStartElement, StartProtocolElement
from app.time_trial import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    ALIGN_RIGHT,
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    StartEntry,
    TimeTrialView,
    board_items,
    board_transform,
    build_start_entries,
    format_clock,
    format_countdown,
    now_seconds,
    select_view,
)

BASE = now_seconds(datetime(2026, 9, 15, 10, 0, 0))


def _start(cid: str, group: str, delay: float, name: str = "") -> StartProtocolElement:
    elem = StartProtocolElement.from_line(
        f"{cid}#{name or 'Rider ' + cid}#{group}#1#1#1990#Team#City##0 00:00:00.000#"
    )
    elem.start_delay = delay
    return elem


def _bib(entry: StartEntry | None) -> str | None:
    """Bib of a slot, or None when the slot is empty."""
    return None if entry is None else entry.competitor_id


def _entries(*pairs: tuple[str, float]) -> list[StartEntry]:
    return [
        StartEntry(competitor_id=cid, name=f"Rider {cid}", start_time=BASE + offset)
        for cid, offset in pairs
    ]


class TestNowSeconds:
    def test_matches_the_timing_file_scale(self) -> None:
        # 2026-09-15 is 20711 days after the epoch; 10:30:15 is 37815 s into the day.
        value = now_seconds(datetime(2026, 9, 15, 10, 30, 15))
        assert value == 20711 * 86400 + 37815

    def test_keeps_sub_second_precision(self) -> None:
        value = now_seconds(datetime(2026, 9, 15, 0, 0, 1, 500000))
        assert value == 20711 * 86400 + 1.5

    def test_default_argument_reads_the_clock(self) -> None:
        assert now_seconds() > 20000 * 86400


class TestBuildStartEntries:
    def test_start_time_is_group_start_plus_personal_offset(self) -> None:
        groups = [GroupStartElement(group_id="G", seconds=BASE)]
        entries = build_start_entries([_start("7", "G", 90.0)], groups)
        assert [(e.competitor_id, e.start_time) for e in entries] == [("7", BASE + 90)]

    def test_entries_come_back_in_start_order(self) -> None:
        groups = [GroupStartElement(group_id="G", seconds=BASE)]
        starts = [
            _start("3", "G", 120.0),
            _start("1", "G", 0.0),
            _start("2", "G", 60.0),
        ]
        entries = build_start_entries(starts, groups)
        assert [e.competitor_id for e in entries] == ["1", "2", "3"]

    def test_riders_from_different_groups_interleave_by_time(self) -> None:
        groups = [
            GroupStartElement(group_id="A", seconds=BASE),
            GroupStartElement(group_id="B", seconds=BASE + 30),
        ]
        starts = [_start("10", "A", 60.0), _start("20", "B", 0.0)]
        entries = build_start_entries(starts, groups)
        assert [e.competitor_id for e in entries] == ["20", "10"]

    def test_equal_times_fall_back_to_bib_order(self) -> None:
        groups = [GroupStartElement(group_id="G", seconds=BASE)]
        starts = [_start("30", "G", 0.0), _start("4", "G", 0.0)]
        entries = build_start_entries(starts, groups)
        assert [e.competitor_id for e in entries] == ["4", "30"]

    def test_non_numeric_bibs_still_sort(self) -> None:
        groups = [GroupStartElement(group_id="G", seconds=BASE)]
        starts = [_start("b", "G", 0.0), _start("a", "G", 0.0)]
        entries = build_start_entries(starts, groups)
        assert [e.competitor_id for e in entries] == ["a", "b"]

    def test_group_without_a_start_time_is_left_out(self) -> None:
        # The generator substitutes 0.0 for a group missing from groups.txt; carrying
        # that through would date the rider to 1970 and pin them as "just started".
        groups = [
            GroupStartElement(group_id="G", seconds=BASE),
            GroupStartElement(group_id="UNKNOWN", seconds=0.0),
        ]
        starts = [_start("1", "G", 0.0), _start("2", "UNKNOWN", 0.0)]
        entries = build_start_entries(starts, groups)
        assert [e.competitor_id for e in entries] == ["1"]

    def test_group_absent_from_the_list_is_left_out(self) -> None:
        groups = [GroupStartElement(group_id="G", seconds=BASE)]
        starts = [_start("1", "G", 0.0), _start("2", "OTHER", 0.0)]
        entries = build_start_entries(starts, groups)
        assert [e.competitor_id for e in entries] == ["1"]

    def test_no_registered_riders_gives_no_entries(self) -> None:
        assert build_start_entries([], [GroupStartElement("G", BASE)]) == []

    def test_carries_the_rider_name(self) -> None:
        groups = [GroupStartElement(group_id="G", seconds=BASE)]
        entries = build_start_entries([_start("5", "G", 0.0, "Ivanov Ivan")], groups)
        assert entries[0].name == "Ivanov Ivan"


class TestSelectView:
    def test_picks_the_three_riders_around_now(self) -> None:
        # Riders 1..5 a minute apart; at 2.5 min rider 3 is away and 4 is next.
        entries = _entries(("1", 0), ("2", 60), ("3", 120), ("4", 180), ("5", 240))
        view = select_view(entries, BASE + 150)
        assert _bib(view.started) == "3"
        assert _bib(view.next_up) == "4"
        assert _bib(view.after_next) == "5"

    def test_countdown_is_the_wait_for_the_next_rider(self) -> None:
        entries = _entries(("1", 0), ("2", 60))
        view = select_view(entries, BASE + 10)
        assert view.countdown == 50

    def test_a_rider_is_away_the_instant_their_time_arrives(self) -> None:
        entries = _entries(("1", 0), ("2", 60))
        view = select_view(entries, BASE + 60)
        assert _bib(view.started) == "2"
        assert view.next_up is None

    def test_before_the_first_start_nobody_has_gone(self) -> None:
        entries = _entries(("1", 0), ("2", 60))
        view = select_view(entries, BASE - 10)
        assert view.started is None
        assert _bib(view.next_up) == "1"
        assert _bib(view.after_next) == "2"

    def test_the_after_next_slot_empties_first(self) -> None:
        entries = _entries(("1", 0), ("2", 60), ("3", 120))
        view = select_view(entries, BASE + 70)
        assert _bib(view.next_up) == "3"
        assert view.after_next is None

    def test_once_everyone_has_gone_only_the_last_rider_remains(self) -> None:
        entries = _entries(("1", 0), ("2", 60))
        view = select_view(entries, BASE + 600)
        assert _bib(view.started) == "2"
        assert view.next_up is None
        assert view.after_next is None
        assert view.countdown is None

    def test_an_empty_schedule_leaves_every_slot_empty(self) -> None:
        view = select_view([], BASE)
        assert view.started is None
        assert view.next_up is None
        assert view.after_next is None
        assert view.countdown is None


class TestFormatting:
    def test_clock_shows_the_time_of_day(self) -> None:
        assert format_clock(now_seconds(datetime(2026, 9, 15, 9, 5, 7))) == "09:05:07"

    def test_clock_handles_midnight(self) -> None:
        assert format_clock(now_seconds(datetime(2026, 9, 15, 0, 0, 0))) == "00:00:00"

    def test_countdown_truncates_so_it_reads_like_a_start_call(self) -> None:
        # 15.7 s left is called as 15, not rounded up to 16.
        assert format_countdown(15.7) == "0:15"

    def test_countdown_shows_minutes(self) -> None:
        assert format_countdown(125) == "2:05"

    def test_countdown_shows_hours_when_the_wait_is_long(self) -> None:
        assert format_countdown(3725) == "1:02:05"

    def test_countdown_is_blank_when_nobody_is_left(self) -> None:
        assert format_countdown(None) == ""

    def test_countdown_never_goes_negative(self) -> None:
        assert format_countdown(-3) == "0:00"


class TestBoardTransform:
    def test_scales_by_the_tighter_axis_and_centres(self) -> None:
        scale, off_x, off_y = board_transform(DESIGN_WIDTH * 2, DESIGN_HEIGHT * 2)
        assert scale == 2.0
        assert (off_x, off_y) == (0.0, 0.0)

    def test_extra_width_is_split_either_side(self) -> None:
        scale, off_x, off_y = board_transform(DESIGN_WIDTH + 100, DESIGN_HEIGHT)
        assert scale == 1.0
        assert off_x == 50.0
        assert off_y == 0.0

    def test_a_window_with_no_area_scales_to_nothing(self) -> None:
        assert board_transform(0, 100) == (0.0, 0.0, 0.0)
        assert board_transform(100, 0) == (0.0, 0.0, 0.0)

    def test_every_glyph_grows_by_the_same_factor(self) -> None:
        view = select_view(_entries(("1", 0), ("2", 60), ("3", 120)), BASE + 10)
        items = board_items(view)
        small, _, _ = board_transform(DESIGN_WIDTH, DESIGN_HEIGHT)
        big, _, _ = board_transform(DESIGN_WIDTH * 3, DESIGN_HEIGHT * 3)
        ratios = {round(i.font_size * big / (i.font_size * small), 6) for i in items}
        assert ratios == {3.0}


class TestBoardItems:
    def _full_view(self) -> TimeTrialView:
        entries = _entries(("1", 0), ("2", 60), ("3", 120), ("4", 180))
        return select_view(entries, BASE + 70)

    def test_shows_clock_countdown_and_all_three_riders(self) -> None:
        texts = [i.text for i in board_items(self._full_view())]
        # next is 3, the one after is 4, and 2 has just gone
        assert "3" in texts and "Rider 3" in texts
        assert "4" in texts and "Rider 4" in texts
        assert "2" in texts and "Rider 2" in texts

    def test_the_next_rider_is_the_biggest_bib_on_the_board(self) -> None:
        items = {i.text: i for i in board_items(self._full_view())}
        assert items["3"].font_size > items["4"].font_size
        assert items["3"].font_size > items["2"].font_size

    def test_the_countdown_is_the_largest_text(self) -> None:
        items = board_items(self._full_view())
        biggest = max(items, key=lambda i: i.font_size)
        assert biggest.text == format_countdown(self._full_view().countdown)

    def test_the_one_after_next_sits_left_and_the_one_away_sits_right(self) -> None:
        items = {i.text: i for i in board_items(self._full_view())}
        assert items["4"].align == ALIGN_LEFT
        assert items["2"].align == ALIGN_RIGHT
        assert items["3"].align == ALIGN_CENTER

    def test_names_sit_below_their_bibs(self) -> None:
        items = {i.text: i for i in board_items(self._full_view())}
        assert items["Rider 3"].y > items["3"].y
        assert items["Rider 4"].y > items["4"].y
        assert items["Rider 2"].y > items["2"].y

    def test_names_are_smaller_than_their_bibs(self) -> None:
        items = {i.text: i for i in board_items(self._full_view())}
        assert items["Rider 3"].font_size < items["3"].font_size
        assert items["Rider 4"].font_size < items["4"].font_size

    def test_corner_riders_are_far_smaller_than_the_next_one(self) -> None:
        items = {i.text: i for i in board_items(self._full_view())}
        assert items["4"].font_size * 2 < items["3"].font_size

    def test_everything_stays_inside_the_design_area(self) -> None:
        for item in board_items(self._full_view()):
            assert item.x >= 0
            assert item.y >= 0
            assert item.x + item.width <= DESIGN_WIDTH
            assert item.y + item.height <= DESIGN_HEIGHT

    def test_the_corner_slots_do_not_overlap(self) -> None:
        items = {i.text: i for i in board_items(self._full_view())}
        left, right = items["4"], items["2"]
        assert left.x + left.width <= right.x

    def test_empty_slots_are_simply_not_drawn(self) -> None:
        # Everyone has gone: no countdown, no next bib, no next name, no after-next.
        view = select_view(_entries(("1", 0), ("2", 60)), BASE + 600)
        texts = [i.text for i in board_items(view)]
        assert texts == [format_clock(view.now), "2", "Rider 2"]

    def test_an_empty_schedule_leaves_only_the_clock(self) -> None:
        view = select_view([], BASE)
        assert [i.text for i in board_items(view)] == [format_clock(BASE)]

    def test_a_rider_without_a_name_still_shows_a_bib(self) -> None:
        view = select_view([StartEntry("9", "", BASE + 10)], BASE)
        texts = [i.text for i in board_items(view)]
        assert "9" in texts
        assert "" not in texts


class TestDuplicateGroupIds:
    def test_the_first_group_entry_wins_like_the_protocol(self) -> None:
        # calculate_protocol stops at the first matching group id, so the board has to
        # agree or it counts down to a time the protocol never uses.
        groups = [
            GroupStartElement(group_id="G", seconds=BASE),
            GroupStartElement(group_id="G", seconds=BASE + 3600),
        ]
        entries = build_start_entries([_start("1", "G", 0.0)], groups)
        assert entries[0].start_time == BASE

    def test_a_first_entry_without_a_time_still_excludes_the_rider(self) -> None:
        groups = [
            GroupStartElement(group_id="G", seconds=0.0),
            GroupStartElement(group_id="G", seconds=BASE),
        ]
        # The protocol would take the 0.0 and date the rider to 1970; the board shows
        # nobody rather than a rider who started decades ago.
        assert build_start_entries([_start("1", "G", 0.0)], groups) == []
