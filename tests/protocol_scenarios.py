"""Races that exercise every protocol mode and the settings that change a protocol.

Each scenario returns what a protocol run hands its writers -- the sorted protocol,
the groups, the config and the control-point count -- so the same race feeds the HTML
golden files (tests/fixtures/golden/), the document builder and the comparison between
the two. Priority modes (Mass/Splitted, Custom Start, Number of Tries) get the full set
of settings; the others one each.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.attempt_rules import AttemptRule, rules_json
from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import (
    RACE_TYPE_CUSTOM_START,
    RACE_TYPE_ELIMINATOR_QUALIFICATION,
    RACE_TYPE_MASS_SPLITTED,
    RACE_TYPE_NUMBER_OF_TRIES,
    RACE_TYPE_SPIRIDONOV,
    RaceConfig,
)
from app.models import FinishCompetitorElement, GroupStartElement, StartProtocolElement

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Race:
    protocol: list
    groups: list[GroupStartElement]
    cfg: RaceConfig
    n_points: int


def _cfg(**settings) -> RaceConfig:
    base: dict[str, object] = {
        "race_name": "Scenario race",
        "race_date": "2026-07-18",
        "race_place": "Medeu",
        "weather": "+14, sunny",
        "track_conditions": "dry",
        "main_referee": "Chief Referee",
        "additional_referee": "Secretary Name",
        "organizer": "Club & Co",
        "sponsor": '<a href="https://example.com/sponsor">Sponsor</a>',
        "bottom_text": "<p>Thanks</p>",
    }
    base.update(settings)
    return RaceConfig(**base)  # type: ignore[arg-type]


def _mark(bib, seconds, action="nextLap", penalty=0.0):
    return FinishCompetitorElement(str(bib), float(seconds), action, penalty)


def _start(line: str, cfg: RaceConfig) -> StartProtocolElement:
    return StartProtocolElement.from_line(
        line, skip_first_lap=cfg.skip_first_lap_effective()
    )


def _run(cfg, starts, groups, finishes, points=(), checks=()) -> Race:
    start_list = [_start(line, cfg) for line in starts]
    group_list = [GroupStartElement(g, float(t)) for g, t in groups]
    known = {g.group_id for g in group_list}
    for s in start_list:
        if s.group_id not in known:
            known.add(s.group_id)
            group_list.append(GroupStartElement(s.group_id, 0.0))
    remote = [list(p) for p in points]
    protocol = calculate_protocol(
        start_list, group_list, list(finishes), remote, list(checks), cfg, []
    )
    n_points = cfg.intermediate_point_count(len(remote))
    return Race(
        generate_sorted_protocol(protocol, cfg, n_points), group_list, cfg, n_points
    )


# ------------------------------------------------------------------ Mass/Splitted


_MASS_STARTS = [
    "1#Anna Ivanova#W30#3#1#1990#Team A#Almaty#bike X#",
    "2#Boris Petrov#M40#3#1#1980#Team B#Bishkek##",
    "3#Vera Sidorova#W30#3#1#1992#Team A#Almaty##",
    "4#Gleb Orlov#M40#3#1#1979###DSQ rider#",
    "5#Dmitry Not Started#M40#3#1#1985##Astana##",
    "6#Elena Dnf#W30#3#1#1991#Team C###0 00:00:30.000",
]


def _mass_finishes():
    marks = []
    for bib, laps in {
        1: [600, 590, 610],
        2: [580, 600, 605],
        3: [620, 615, 600],
        4: [590, 590, 590],
        6: [700],
    }.items():
        t = 1000.0 + (30 if bib == 6 else 0)
        for lap in laps:
            t += lap
            marks.append(_mark(bib, t))
    marks.append(_mark(4, 1500, "DSQ: cut the course"))
    marks.append(_mark(4, 1600, "DSQ: no chip <check>"))
    return marks


def _mass(**settings) -> Race:
    cfg = _cfg(race_type=RACE_TYPE_MASS_SPLITTED, **settings)
    return _run(cfg, _MASS_STARTS, [("W30", 1000), ("M40", 1000)], _mass_finishes())


def _mass_points(**settings) -> Race:
    cfg = _cfg(race_type=RACE_TYPE_MASS_SPLITTED, n_remote_points=2, **settings)
    finishes = _mass_finishes()
    point1, point2 = [], []
    for mark in finishes:
        if mark.action == "nextLap":
            point1.append(
                _mark(
                    mark.competitor_id,
                    mark.seconds - 400,
                    penalty=5 if mark.competitor_id == "2" else 0,
                )
            )
            if mark.competitor_id != "3":  # a timekeeper who missed one rider
                point2.append(_mark(mark.competitor_id, mark.seconds - 200))
    return _run(
        cfg, _MASS_STARTS, [("W30", 1000), ("M40", 1000)], finishes, [point1, point2]
    )


def _relay(**settings) -> Race:
    cfg = _cfg(race_type=RACE_TYPE_MASS_SPLITTED, **settings)
    starts = ["10#Relay One#R#2#2#2000#Team R###", "20#Relay Two#R#2#2#2001#Team S###"]
    finishes = [_mark(10, 1600), _mark(11, 2210), _mark(20, 1620), _mark(21, 2200)]
    return _run(cfg, starts, [("R", 1000)], finishes)


# ------------------------------------------------------------------- Custom Start


_CUSTOM_STARTS = [
    "1#Anna Custom#W#2#1#1990#Team A###",
    "2#Boris Custom#M#2#1#1980#Team B###",
    "3#Vera Never#W#2#1#1992####",
    "4#Gleb Halfway#M#2#1#1979####",
]


def _custom(**settings) -> Race:
    cfg = _cfg(race_type=RACE_TYPE_CUSTOM_START, **settings)
    finishes = [
        _mark(1, 86400 * 3 + 1000),
        _mark(1, 86400 * 3 + 1600),
        _mark(1, 86400 * 3 + 2210),
        _mark(2, 86400 * 3 + 1100),
        _mark(2, 86400 * 3 + 1690),
        _mark(2, 86400 * 3 + 2300),
        _mark(4, 86400 * 3 + 1200),
        _mark(4, 86400 * 3 + 1800),
        _mark(2, 86400 * 3 + 900, "DSQ: early start"),
    ]
    return _run(cfg, _CUSTOM_STARTS, [], finishes)


# ---------------------------------------------------------------- Number of Tries


def _tries(rules=None, *, points=0, **settings) -> Race:
    cfg = _cfg(
        race_type=RACE_TYPE_NUMBER_OF_TRIES,
        attempt_rules_json=rules_json(rules) if rules is not None else "[]",
        # Rules time each attempt from a start stream to a finish stream (plus any
        # control points); the legacy mode reads one stream alternating start, finish.
        n_remote_points=points + 1 if rules is not None else 0,
        **settings,
    )
    extra = "" if rules is not None else "1:1,2,3"
    starts = [
        f"1#Anna Tries#W#3#1#1990#Team A#Almaty#{extra}#",
        f"2#Boris Tries#M#3#1#1980#Team B#Bishkek#{extra}#",
        f"3#Vera Tries#W#3#1#1992#Team A##{extra}#",
        f"4#Gleb None#M#3#1#1979###{extra}#",
        f"5#Dina Equal#W#3#1#1993###{extra}#",
    ]
    attempts: dict[int, list[tuple[int, int | None]]] = {
        1: [(1000, 1150), (1300, 1440), (1600, None)],
        2: [(1010, 1150), (1310, 1460), (1610, 1730)],
        3: [(1020, 1200), (1320, None), (1620, 1770)],
        5: [(1030, 1170), (1330, 1470), (1630, 1770)],
    }
    starts_stream: list = []
    finish_stream: list = []
    cp_stream: list = []
    for bib, pairs in attempts.items():
        for start, finish in pairs:
            starts_stream.append(_mark(bib, start))
            if finish is not None:
                finish_stream.append(_mark(bib, finish, penalty=0))
                if points:
                    cp_stream.append(_mark(bib, (start + finish) / 2))
            elif points:
                cp_stream.append(_mark(bib, start + 60))
    finish_stream.append(_mark(2, 1460, "Gate <7> & flag", 5))
    finish_stream.append(_mark(3, 1210, "Touch", 2))
    if points:
        return _run(cfg, starts, [], starts_stream, [cp_stream, finish_stream])
    if rules is None:
        # Legacy mode: one stream alternating start, finish.
        alternating = sorted(
            starts_stream + finish_stream, key=lambda m: (m.competitor_id, m.seconds)
        )
        return _run(cfg, starts, [], alternating)
    return _run(cfg, starts, [], starts_stream, [finish_stream])


_ASC = (
    AttemptRule("Best of 2 and 3", 1, (2, 3), "asc"),
    AttemptRule("Qualification", 1, (1,), "desc"),
)
_DESC = (AttemptRule("Longest", 2, (1, 2, 3), "desc"),)


# --------------------------------------------------------------------- the matrix


def _example(**settings) -> Race:
    """The committed example race (data/), loaded as test_example_data does."""
    from test_example_data import _load_cfg, _run_pipeline

    cfg = _load_cfg()
    for key, value in settings.items():
        setattr(cfg, key, value)
    _, sorted_abs, groups = _run_pipeline(cfg)
    return Race(sorted_abs, groups, cfg, 0)


SCENARIOS: dict[str, Callable[[], Race]] = {
    # Mass/Splitted (P1)
    "mass_basic": lambda: _mass(),
    "mass_all_columns": lambda: _mass(
        show_additional_info=True,
        show_time_shift=True,
        show_n_finished_laps=True,
        show_lap_finish=True,
    ),
    "mass_print_all": lambda: _mass(print_dns=True, print_dsq=True, print_dnf=True),
    "mass_disable_dnf": lambda: _mass(disable_dnf=True, print_dsq=True),
    "mass_hide_empty": lambda: _mass(hide_empty_columns=True, print_dns=True),
    "mass_lap_stats": lambda: _mass(use_all_buttons=True, show_lap_finish=True),
    "mass_lap_stats_no_finish": lambda: _mass(use_all_buttons=True),
    "mass_points_buttons": lambda: _mass_points(use_buttons=True),
    "mass_points_no_buttons": lambda: _mass_points(),
    "mass_points_everything": lambda: _mass_points(
        use_buttons=True, use_all_buttons=True, show_lap_finish=True
    ),
    "mass_no_lap_times": lambda: _mass(
        show_lap_times=False, show_time_difference=False
    ),
    "mass_relay": lambda: _relay(show_lap_finish=True),
    "example_race": lambda: _example(),
    "example_race_lap_stats": lambda: _example(
        use_all_buttons=True, show_lap_finish=True
    ),
    # Custom Start (P1)
    "custom_basic": lambda: _custom(
        show_time_shift=True, print_dns=True, print_dsq=True
    ),
    "custom_disable_dsq": lambda: _custom(show_time_shift=True, disable_dsq=True),
    "custom_registration_period": lambda: _custom(
        show_time_shift=True, start_registration_period=150.0
    ),
    # Number of Tries (P1)
    "tries_asc": lambda: _tries(_ASC, show_n_finished_laps=True, print_dns=True),
    "tries_desc": lambda: _tries(_DESC, show_n_finished_laps=True),
    "tries_legacy": lambda: _tries(None),
    "tries_points": lambda: _tries(
        _ASC, points=1, use_buttons=True, hide_empty_columns=True
    ),
    "tries_disable_dnf": lambda: _tries(_ASC, disable_dnf=True, show_time_shift=True),
    # the others (P2)
    "eliminator_qualification": lambda: _example(
        race_type=RACE_TYPE_ELIMINATOR_QUALIFICATION
    ),
    "spiridonov": lambda: _example(race_type=RACE_TYPE_SPIRIDONOV),
}

GOLDEN = ROOT / "tests" / "fixtures" / "golden"
