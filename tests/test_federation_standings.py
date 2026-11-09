"""The ordering rules of the federation-protocol skill (SKILL.md, "Final places")."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_PATH = (
    Path(__file__).resolve().parents[1]
    / ".claude"
    / "skills"
    / "federation-protocol"
    / "scripts"
    / "standings.py"
)
_spec = importlib.util.spec_from_file_location("federation_standings", _PATH)
assert _spec is not None and _spec.loader is not None
standings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(standings)


def _heat(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [
        {
            "bib": bib,
            "place": place,
            "status": "ok" if place.isdigit() else place.lower(),
        }
        for bib, place in rows
    ]


def _places(
    heats: dict[str, list[dict[str, str]]],
    qualified: list[str],
    without_result: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """The group's rows as (place, bib); ``qualified`` in qualification order."""
    riders: dict[str, Any] = {
        bib: {"qual_place": i, "qual_status": ""} for i, bib in enumerate(qualified, 1)
    }
    for bib, status in (without_result or {}).items():
        riders[bib] = {"qual_place": None, "qual_status": status}
    data = {
        "riders": riders,
        "qualification": {"G": qualified + list(without_result or {})},
        "ladders": {"G": heats},
    }
    return [(r["place"], r["bib"]) for r in standings.group_standings("G", data)]


def test_finishers_go_straight_on_and_dropouts_share_the_last_place() -> None:
    # A rider of the final who did not finish lets the small final's winner up to
    # 4th; every finals DNF takes 8th, the last place a finalist can take.
    heats = {
        "1/2 final 1": _heat(("A", "1"), ("B", "2"), ("G", "3"), ("H", "4")),
        "1/2 final 2": _heat(("C", "1"), ("D", "2"), ("F", "3"), ("E", "DNF")),
        "Final": _heat(("B", "1"), ("A", "2"), ("C", "3"), ("D", "DNF")),
        "Small final": _heat(("G", "5"), ("F", "6"), ("H", "DNF")),
    }
    got = _places(heats, ["A", "B", "C", "D", "E", "F", "G", "H"])
    assert got == [
        ("1", "B"), ("2", "A"), ("3", "C"), ("4", "G"), ("5", "F"),
        ("8", "D"), ("8", "E"), ("8", "H"),
    ]  # fmt: skip


def test_a_small_final_not_held_goes_by_qualification() -> None:
    # Nobody failed to start a heat that never ran: places by qualification, and the
    # semi-final DNF still takes the last place after them.
    heats = {
        "1/2 final 1": _heat(("A", "1"), ("B", "2"), ("G", "3"), ("H", "4")),
        "1/2 final 2": _heat(("C", "1"), ("D", "2"), ("F", "3"), ("E", "DNF")),
        "Final": _heat(("A", "1"), ("B", "2"), ("C", "3"), ("D", "4")),
        "Small final": _heat(("G", "DNS"), ("H", "DNS"), ("F", "DNS")),
    }
    got = _places(heats, ["A", "B", "C", "D", "E", "F", "G", "H", "I"], {"Z": "DNS"})
    assert got == [
        ("1", "A"), ("2", "B"), ("3", "C"), ("4", "D"), ("5", "F"), ("6", "G"),
        ("7", "H"), ("8", "E"), ("9", "I"), ("DNS", "Z"),
    ]  # fmt: skip


def test_a_small_final_nobody_finished_was_still_held() -> None:
    # Started and nobody crossed the line: DNF, not the DNS of a heat never run, so
    # its riders share the last place rather than going by qualification.
    heats = {
        "1/2 final 1": _heat(("A", "1"), ("B", "2"), ("G", "3"), ("H", "4")),
        "1/2 final 2": _heat(("C", "1"), ("D", "2"), ("F", "3"), ("E", "4")),
        "Final": _heat(("A", "1"), ("B", "2"), ("C", "3"), ("D", "4")),
        "Small final": _heat(("G", "DNF"), ("H", "DNF"), ("F", "DNF"), ("E", "DNF")),
    }
    got = _places(heats, ["A", "B", "C", "D", "E", "F", "G", "H"])
    assert got == [
        ("1", "A"), ("2", "B"), ("3", "C"), ("4", "D"),
        ("8", "E"), ("8", "F"), ("8", "G"), ("8", "H"),
    ]  # fmt: skip


def test_a_disqualified_finalist_frees_his_place_and_goes_last() -> None:
    heats = {
        "1/2 final 1": _heat(("A", "1"), ("B", "2"), ("G", "3"), ("H", "4")),
        "1/2 final 2": _heat(("C", "1"), ("D", "2"), ("F", "3"), ("E", "DSQ")),
        "Final": _heat(("B", "1"), ("C", "2"), ("A", "3"), ("D", "4")),
        "Small final": _heat(("G", "DNS"), ("H", "DNS"), ("F", "DNS")),
    }
    got = _places(
        heats, ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"], {"X": "DNF"}
    )
    assert got == [
        ("1", "B"), ("2", "C"), ("3", "A"), ("4", "D"), ("5", "F"), ("6", "G"),
        ("7", "H"), ("8", "I"), ("9", "J"), ("DNF", "X"), ("DSQ", "E"),
    ]  # fmt: skip


def test_a_final_only_ladder_continues_with_the_rest() -> None:
    heats = {"Final": _heat(("B", "1"), ("A", "2"), ("C", "3"), ("D", "DNF"))}
    got = _places(heats, ["A", "B", "C", "D", "E"], {"Y": "DNF", "Z": "DNS"})
    assert got == [
        ("1", "B"), ("2", "A"), ("3", "C"), ("4", "D"), ("5", "E"),
        ("DNF", "Y"), ("DNS", "Z"),
    ]  # fmt: skip


def test_a_rider_disqualified_in_the_qualification_is_last_as_dsq() -> None:
    # Dropping him would print a group short of a rider with nothing said; DSQ
    # always goes last, wherever it was given.
    heats = {"Final": _heat(("B", "1"), ("A", "2"), ("C", "DSQ"))}
    got = _places(heats, ["A", "B", "C", "D"], {"X": "DSQ", "Y": "DNS"})
    assert got == [
        ("1", "B"),
        ("2", "A"),
        ("3", "D"),
        ("DNS", "Y"),
        ("DSQ", "C"),
        ("DSQ", "X"),
    ]


def test_a_finalist_with_nowhere_to_go_is_an_error() -> None:
    # A semi-final finisher seated in neither final means the ladder data is broken;
    # silently dropping him would hide it.
    heats = {
        "1/2 final 1": _heat(("A", "1"), ("B", "2"), ("G", "3"), ("H", "4")),
        "Final": _heat(("A", "1")),
    }
    with pytest.raises(ValueError, match="finalists with no place"):
        _places(heats, ["A", "B", "G", "H"])
