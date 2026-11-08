"""The calculations every view of a protocol shares, and the statuses they all read."""

from __future__ import annotations

from protocol_scenarios import SCENARIOS

from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import RACE_TYPE_MASS_SPLITTED, RaceConfig
from app.html_writer import write_absolute_protocol, write_group_protocol
from app.live_stats import build_live_stats
from app.models import FinishCompetitorElement, GroupStartElement, StartProtocolElement
from app.protocol_rows import (
    group_places,
    is_printed,
    place_status,
    prepare_statuses,
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
    # they were.
    protocol, groups, cfg = _two_finishers()
    write_group_protocol(str(tmp_path / "g.html"), protocol, groups, cfg)
    write_absolute_protocol(str(tmp_path / "a.html"), protocol, groups, cfg)
    stats = build_live_stats(protocol, cfg)
    assert (stats["1"]["place_abs"], stats["2"]["place_abs"]) == ("2", "1")


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
    """One group of four, each with a single finish mark at the given second."""
    cfg = RaceConfig()
    starts = [
        StartProtocolElement.from_line(f"{i}#Rider {i}#A#1#1####") for i in range(1, 5)
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
