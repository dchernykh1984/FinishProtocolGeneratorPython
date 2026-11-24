"""The calculations every view of a protocol shares, and the statuses they all read."""

from __future__ import annotations

from protocol_scenarios import SCENARIOS

from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import RACE_TYPE_MASS_SPLITTED, RaceConfig
from app.html_writer import write_absolute_protocol, write_group_protocol
from app.live_stats import build_live_stats
from app.models import (
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    StartProtocolElement,
)
from app.protocol_rows import (
    group_places,
    is_printed,
    leads,
    place_status,
    prepare_statuses,
    result_parts,
    shared_places,
)


def _two_finishers():
    """The race from the plan review: one group start never seen, one seen at 5 s."""
    cfg = RaceConfig(
        race_type=RACE_TYPE_MASS_SPLITTED,
        send_group_statistics=True,
        send_absolute_statistics=True,
    )
    starts = [
        StartProtocolElement.from_line("1#First#A#1#1####"),
        StartProtocolElement.from_line("2#Second#B#1#1####"),
    ]
    groups = [GroupStartElement("A", 0.0), GroupStartElement("B", 5.0)]
    marks = [
        FinishCompetitorElement("1", 10.0, "nextLap"),
        FinishCompetitorElement("2", 15.0, "nextLap"),
    ]
    protocol = calculate_protocol(starts, groups, marks, [], [], cfg, [])
    return generate_sorted_protocol(protocol, cfg, 0), groups, cfg


def test_live_stats_after_the_writers_keep_the_statuses_they_had(tmp_path):
    # Live statistics have always been built after the writers, which settle who
    # finished; moving that into prepare_statuses must leave the watch's places as
    # they were -- 1 never started, so the watch says DNS, as the protocol does.
    protocol, groups, cfg = _two_finishers()
    write_group_protocol(str(tmp_path / "g.html"), protocol, groups, cfg)
    write_absolute_protocol(str(tmp_path / "a.html"), protocol, groups, cfg)
    stats = build_live_stats(protocol, cfg)
    assert (stats["1"]["place_abs"], stats["2"]["place_abs"]) == ("DNS", "1")


def test_prepare_statuses_alone_gives_the_same_live_stats_as_the_writers(tmp_path):
    written, groups, cfg = _two_finishers()
    write_group_protocol(str(tmp_path / "g.html"), written, groups, cfg)
    prepared, _, _ = _two_finishers()
    prepare_statuses(prepared, cfg)
    assert build_live_stats(prepared, cfg) == build_live_stats(written, cfg)


def test_prepare_statuses_is_idempotent():
    protocol, _, cfg = _two_finishers()
    prepare_statuses(protocol, cfg)
    once = [(fp.finished, fp.disqualified) for fp in protocol]
    prepare_statuses(protocol, cfg)
    assert [(fp.finished, fp.disqualified) for fp in protocol] == once


def test_a_rider_who_missed_the_start_check_prints_and_places_as_a_dns():
    # He rode and finished, but a DNS row is printed as one and takes no place.
    fp = FinishProtocolElement(
        StartProtocolElement.from_line("1#A#G#1#1####"), False, 0
    )
    fp.finished, fp.n_laps_finished, fp.missed_start_check = True, 1, True
    cfg = RaceConfig(print_dnf=True, print_dns=False)
    assert not is_printed(fp, cfg)
    cfg.print_dns = True
    assert is_printed(fp, cfg)
    # A finisher needs no "Print DNF", which is what "Disable DNF" makes everyone.
    cfg.print_dnf = False
    assert is_printed(fp, cfg)
    fp.finished = False
    assert not is_printed(fp, cfg)
    assert place_status(fp, 1, cfg) == ("DNS", "dns")
    everything = RaceConfig(print_dnf=True, print_dns=True)
    assert group_places([fp], [GroupStartElement("G", 100.0)], everything) == {}


def test_a_dns_of_the_start_check_is_nobodys_leader_and_keeps_his_time():
    # A gap measured from a DNS row would rank the rows after it against a rider
    # who has no place; his own time still shows when nobody else finished.
    fp = FinishProtocolElement(
        StartProtocolElement.from_line("1#A#G#1#1####"), False, 0
    )
    fp.finished, fp.n_laps_finished, fp.missed_start_check = True, 1, True
    fp.finish_lap_times[0] = 95.5
    assert not leads(fp)
    parts = result_parts(fp, None, RaceConfig())
    assert parts.time == "00:01:35.5" and parts.gap == ""
    # Nor a gap to a leader who rode fewer laps: it would be his whole race time.
    leader = FinishProtocolElement(
        StartProtocolElement.from_line("2#B#G#1#1####"), False, 0
    )
    leader.finished, leader.n_laps_finished = True, 1
    leader.finish_lap_times[0] = 90.0
    fp.n_laps_finished = 2
    fp.finish_lap_times[1] = 180.0
    parts = result_parts(fp, leader, RaceConfig())
    assert parts.time == "00:03:00.0" and parts.gap == ""


def test_a_finisher_without_a_leader_shows_no_result():
    # Only a DNS of the start check keeps his time without a leader; a finisher
    # always has one, himself at least, so a missing one means nothing to show.
    fp = FinishProtocolElement(
        StartProtocolElement.from_line("1#A#G#1#1####"), False, 0
    )
    fp.finished, fp.n_laps_finished = True, 1
    fp.finish_lap_times[0] = 95.5
    assert result_parts(fp, None, RaceConfig()).time == ""


def test_place_status_names_dsq_dnf_dns_and_places():
    race = SCENARIOS["mass_print_all"]()
    prepare_statuses(race.protocol, race.cfg)
    statuses = {fp.name: place_status(fp, 7, race.cfg) for fp in race.protocol}
    assert statuses["Gleb Orlov"] == ("DSQ", "dsq")
    # Their group started, so a rider never seen at the finish did not finish.
    assert statuses["Dmitry Not Started"] == ("DNF", "dnf")
    assert statuses["Elena Dnf"] == ("DNF", "dnf")
    assert statuses["Anna Ivanova"] == ("7", "ok")
    custom = SCENARIOS["custom_basic"]()
    prepare_statuses(custom.protocol, custom.cfg)
    never = next(fp for fp in custom.protocol if fp.name == "Vera Never")
    assert place_status(never, 1, custom.cfg) == ("DNS", "dns")
    # Disable DNS: everyone counts as started, so a rider never seen did not finish.
    custom.cfg.disable_dns = True
    assert place_status(never, 1, custom.cfg) == ("DNF", "dnf")


def test_group_places_count_printed_finishers_and_do_not_change_the_groups():
    race = SCENARIOS["mass_print_all"]()
    prepare_statuses(race.protocol, race.cfg)
    before = [g.place for g in race.groups]
    places = group_places(race.protocol, race.groups, race.cfg)
    assert [g.place for g in race.groups] == before
    by_name = {fp.name: places.get(id(fp)) for fp in race.protocol}
    assert by_name["Gleb Orlov"] is None  # disqualified
    w30 = sorted(
        p
        for name, p in by_name.items()
        if p and name in ("Anna Ivanova", "Vera Sidorova")
    )
    assert w30 == [1, 2]
    assert all(is_printed(fp, race.cfg) for fp in race.protocol if id(fp) in places)


def _group_of_four(offsets):
    """One group, one rider per offset, each with a single finish mark at it."""
    cfg = RaceConfig()
    starts = [
        StartProtocolElement.from_line(f"{i}#Rider {i}#A#1#1####")
        for i in range(1, len(offsets) + 1)
    ]
    groups = [GroupStartElement("A", 100.0)]
    marks = [
        FinishCompetitorElement(str(i), 100.0 + offset, "nextLap")
        for i, offset in enumerate(offsets, start=1)
    ]
    protocol = calculate_protocol(starts, groups, marks, [], [], cfg, [])
    return generate_sorted_protocol(protocol, cfg, 0), cfg


def test_an_exact_dead_heat_shares_a_place_and_keeps_both_rows():
    protocol, cfg = _group_of_four([10.0, 11.0, 11.0, 12.0])
    prepare_statuses(protocol, cfg)
    places = shared_places([fp for fp in protocol if is_printed(fp, cfg)], cfg)
    assert [places[id(fp)] for fp in protocol] == [1, 2, 2, 4]
    assert len(protocol) == 4


def test_results_that_only_print_the_same_keep_their_own_places():
    # 11.06 and 11.14 both come out as the same tenth, but they are not one time:
    # printing a dead heat there would invent one that never happened.
    protocol, cfg = _group_of_four([10.0, 11.06, 11.14, 12.0])
    prepare_statuses(protocol, cfg)
    places = shared_places([fp for fp in protocol if is_printed(fp, cfg)], cfg)
    assert [places[id(fp)] for fp in protocol] == [1, 2, 3, 4]


def test_a_group_place_starts_where_its_start_line_says_and_shares_a_dead_heat():
    cfg = RaceConfig()
    starts = [
        StartProtocolElement.from_line(f"{i}#Rider {i}#A#1#1####") for i in range(1, 4)
    ]
    group = GroupStartElement("A", 100.0)
    group.place = 5
    marks = [
        FinishCompetitorElement("1", 110.0, "nextLap"),
        FinishCompetitorElement("2", 111.0, "nextLap"),
        FinishCompetitorElement("3", 111.0, "nextLap"),
    ]
    protocol = calculate_protocol(starts, [group], marks, [], [], cfg, [])
    sorted_protocol = generate_sorted_protocol(protocol, cfg, 0)
    prepare_statuses(sorted_protocol, cfg)
    places = group_places(sorted_protocol, [group], cfg)
    assert [places[id(fp)] for fp in sorted_protocol] == [5, 6, 6]


def test_a_lapped_rider_crossing_with_the_leader_does_not_share_his_place():
    # Same millisecond over a different number of laps is not a dead heat.
    cfg = RaceConfig()
    starts = [
        StartProtocolElement.from_line("1#Leader#A#2#1####"),
        StartProtocolElement.from_line("2#Lapped#A#1#1####"),
    ]
    groups = [GroupStartElement("A", 100.0)]
    marks = [
        FinishCompetitorElement("1", 150.0, "nextLap"),
        FinishCompetitorElement("1", 200.0, "nextLap"),
        FinishCompetitorElement("2", 200.0, "nextLap"),
    ]
    protocol = calculate_protocol(starts, groups, marks, [], [], cfg, [])
    sorted_protocol = generate_sorted_protocol(protocol, cfg, 0)
    prepare_statuses(sorted_protocol, cfg)
    places = shared_places([fp for fp in sorted_protocol if is_printed(fp, cfg)], cfg)
    assert sorted(places.values()) == [1, 2]


def _places(offsets):
    protocol, cfg = _group_of_four(offsets)
    prepare_statuses(protocol, cfg)
    places = shared_places([fp for fp in protocol if is_printed(fp, cfg)], cfg)
    return [places[id(fp)] for fp in protocol]


def test_a_dead_heat_in_the_middle_numbers_one_two_two_four():
    assert _places([10.0, 11.0, 11.0, 12.0, 13.0, 14.0]) == [1, 2, 2, 4, 5, 6]


def test_four_riders_on_one_time_all_take_first_and_the_next_is_fifth():
    assert _places([10.0, 10.0, 10.0, 10.0, 13.0, 14.0]) == [1, 1, 1, 1, 5, 6]


def _w_places(race):
    """The places of group W's placed riders, by name."""
    prepare_statuses(race.protocol, race.cfg)
    places = group_places(race.protocol, race.groups, race.cfg)
    return {
        fp.name: places[id(fp)]
        for fp in race.protocol
        if fp.group_id == "W" and id(fp) in places
    }


def test_a_number_of_tries_tie_break_parts_the_place_it_breaks():
    # Anna and Dina ride 140 s by the first rule; Anna's longer qualification puts her
    # ahead by the second, which parts their place too (maintainer, 2026-11-24).
    places = _w_places(SCENARIOS["tries_asc"]())
    assert (places["Anna Tries"], places["Dina Equal"]) == (1, 2)


def test_riders_equal_on_every_number_of_tries_rule_share_a_place():
    from protocol_scenarios import _tries

    from app.attempt_rules import AttemptRule

    rules = (
        AttemptRule("Best of 2 and 3", 1, (2, 3), "asc"),
        AttemptRule("Second", 1, (2,), "asc"),
    )
    places = _w_places(_tries(rules))
    # Both ride 140 s by either rule: the number only lists Anna first.
    assert (places["Anna Tries"], places["Dina Equal"], places["Vera Tries"]) == (
        1,
        1,
        3,
    )


def test_float_noise_on_the_first_rule_does_not_order_riders_a_tie_break_parts():
    # 140.150 s ridden at two times of day comes out of the subtraction as two floats a
    # few ten-millionths apart; bib 1 then wins the second rule by 10 s.
    from protocol_scenarios import _cfg, _run

    from app.attempt_rules import AttemptRule, rules_json
    from app.config import RACE_TYPE_NUMBER_OF_TRIES
    from app.models import parse_time_string

    def ride(ms):
        start = parse_time_string(f"20416 12:00:00.{ms:03d}")
        end = ms + 150
        return start, parse_time_string(
            f"20416 12:02:{20 + end // 1000:02d}.{end % 1000:03d}"
        )

    rides = {ms: ride(ms) for ms in range(1000)}
    longer = max(rides, key=lambda ms: rides[ms][1] - rides[ms][0])
    shorter = min(rides, key=lambda ms: rides[ms][1] - rides[ms][0])
    (s1, f1), (s2, f2) = rides[longer], rides[shorter]
    assert f1 - s1 != f2 - s2  # the noise this test is about
    rules = (
        AttemptRule("Result", 1, (1,), "asc"),
        AttemptRule("Tie-break", 1, (2,), "asc"),
    )
    cfg = _cfg(
        race_type=RACE_TYPE_NUMBER_OF_TRIES,
        attempt_rules_json=rules_json(rules),
        n_remote_points=1,
    )

    def mark(bib, t):
        return FinishCompetitorElement(str(bib), t, "nextLap", 0.0)

    starts = [mark(1, s1), mark(2, s2), mark(1, s1 + 600), mark(2, s2 + 600)]
    finishes = [mark(1, f1), mark(2, f2), mark(1, s1 + 650), mark(2, s2 + 660)]
    lines = ["1#Bib One#W#2#1#1990####", "2#Bib Two#W#2#1#1990####"]
    race = _run(cfg, lines, [], starts, [finishes])
    places = _w_places(race)
    assert [fp.competitor_id for fp in race.protocol] == ["1", "2"]
    assert (places["Bib One"], places["Bib Two"]) == (1, 2)


def test_legacy_number_of_tries_riders_without_an_attempt_sort_by_number():
    # No completed attempt totals infinity: two such riders go by number, never into an
    # OverflowError that would leave the run without a protocol.
    from protocol_scenarios import _cfg, _mark, _run

    from app.config import RACE_TYPE_NUMBER_OF_TRIES

    cfg = _cfg(race_type=RACE_TYPE_NUMBER_OF_TRIES, attempt_rules_json="[]")
    lines = [f"{bib}#Rider {bib}#W#3#1#1990###1:1,2,3#" for bib in (3, 1, 2)]
    race = _run(cfg, lines, [], [_mark(3, 1000), _mark(3, 1150)])
    assert [fp.competitor_id for fp in race.protocol] == ["3", "1", "2"]
