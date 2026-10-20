"""Config-wide attempt scoring, priority and missing-result semantics."""

import json

import pytest

from app.attempt_rules import AttemptRule, parse_attempt_rules, rules_json
from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import RACE_TYPE_NUMBER_OF_TRIES, RaceConfig
from app.models import (
    FinishCompetitorElement,
    FinishProtocolElement,
    GroupStartElement,
    StartProtocolElement,
)

RULES = (
    AttemptRule("Result", 1, (2, 3), "asc"),
    AttemptRule("Qualification", 1, (1,), "desc"),
)


def rider(bib: str, times: list[float], rules=RULES) -> FinishProtocolElement:
    start = StartProtocolElement.from_line(f"{bib}#Name#G#3#1#1990#T#C##")
    fp = FinishProtocolElement(start, False, 0)
    fp.attempt_rules = rules
    fp.n_tries_for_result = rules[0].attempts
    fp.n_laps_finished = len(times)
    fp.lap_times[: len(times)] = times
    return fp


def ranked(*riders: FinishProtocolElement) -> list[str]:
    cfg = RaceConfig(race_type=RACE_TYPE_NUMBER_OF_TRIES)
    return [fp.competitor_id for fp in generate_sorted_protocol(list(riders), cfg, 0)]


def test_rules_are_one_physical_line_and_labels_are_only_descriptions():
    rules = (AttemptRule("Result\n\u2028", 1, (2, 3), "asc"),)
    text = rules_json(rules)
    assert len(text.splitlines()) == 1
    assert text.isascii()
    assert parse_attempt_rules(text) == rules


@pytest.mark.parametrize("value", ["", "[]"])
def test_empty_rules_retain_legacy(value):
    assert parse_attempt_rules(value) == ()


@pytest.mark.parametrize(
    "data",
    [
        {},
        [None],
        [{"label": "Incomplete"}],
        [{"label": 1, "attempts": 1, "attempt_numbers": [1], "sort": "asc"}],
        [{"label": "R", "attempts": True, "attempt_numbers": [1], "sort": "asc"}],
        [{"label": "R", "attempts": 0, "attempt_numbers": [1], "sort": "asc"}],
        [{"label": "R", "attempts": 2, "attempt_numbers": [1], "sort": "asc"}],
        [{"label": "R", "attempts": 1, "attempt_numbers": [], "sort": "asc"}],
        [{"label": "R", "attempts": 1, "attempt_numbers": [0], "sort": "asc"}],
        [{"label": "R", "attempts": 1, "attempt_numbers": [True], "sort": "asc"}],
        [{"label": "R", "attempts": 1, "attempt_numbers": [1, 1], "sort": "asc"}],
        [{"label": "R", "attempts": 1, "attempt_numbers": [1], "sort": "bad"}],
    ],
)
def test_invalid_rules_fail_explicitly(data):
    with pytest.raises(ValueError, match="Attempt rule"):
        parse_attempt_rules(json.dumps(data))


def test_invalid_json_fails_explicitly():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_attempt_rules("[")


def test_qualification_orders_riders_before_any_counted_result():
    assert ranked(rider("1", [30]), rider("2", [40])) == ["2", "1"]


def test_final_result_takes_priority_after_attempt_two():
    assert ranked(rider("1", [30, 20]), rider("2", [40, 25])) == ["1", "2"]


def test_secondary_rule_breaks_equal_final_scores():
    assert ranked(rider("1", [30, 20, 25]), rider("2", [40, 25, 20])) == ["2", "1"]


def test_all_equal_rules_fall_back_to_numeric_bib():
    assert ranked(rider("10", [30, 20]), rider("2", [30, 20])) == ["2", "10"]


def test_missing_attempt_is_not_a_zero_time_win_in_descending_order():
    rules = (AttemptRule("Reverse", 1, (2,), "desc"),)
    assert ranked(rider("1", [30], rules), rider("2", [30, 20], rules)) == ["2", "1"]


def test_descending_still_selects_best_times_and_only_first_rule_defines_total():
    rules = (AttemptRule("R", 2, (1, 2, 3), "desc"), RULES[1])
    fp = rider("1", [30, 10, 20], rules)
    assert fp.get_total_time() == 30
    assert fp.get_n_successful_tries() == 2
    assert fp.selected_attempts(rules[0]) == [1, 2]


def test_equal_attempt_times_select_the_earlier_attempt():
    fp = rider("1", [30, 20, 20])
    assert fp.selected_attempts(RULES[0]) == [1]


def test_config_rules_override_personal_comment_and_exclude_waits():
    cfg = RaceConfig(
        race_type=RACE_TYPE_NUMBER_OF_TRIES, attempt_rules_json=rules_json(RULES)
    )
    start = StartProtocolElement.from_line("1#Name#G#3#1#1990#T#C#Free text#")
    marks = [
        FinishCompetitorElement("1", t, "nextLap")
        for t in (1000, 1030, 1100, 1120, 1200, 1218)
    ]
    log = []
    fp = calculate_protocol(
        [start], [GroupStartElement("G", 900)], marks, [], [], cfg, log
    )[0]
    assert fp.lap_times[:3] == [30, 20, 18]
    assert fp.get_total_time() == 18
    assert fp.get_n_successful_tries() == 1
    assert fp.finished
    assert fp.extra_info == "Free text"
    assert not any("invalid NumberOfTries" in message for message in log)


@pytest.mark.parametrize("scope", ["group", "absolute"])
def test_html_bolds_only_attempts_actually_in_primary_result(tmp_path, scope):
    from app.html_writer import (
        _format_time,
        write_absolute_protocol,
        write_group_protocol,
    )

    fp = rider("1", [30, 20, 20])
    fp.finished = True
    fp.cross_line_times[0] = 1000
    cfg = RaceConfig(race_type=RACE_TYPE_NUMBER_OF_TRIES)
    path = tmp_path / "result.html"
    writer = write_group_protocol if scope == "group" else write_absolute_protocol
    writer(str(path), [fp], [GroupStartElement("G", 900)], cfg, 0)
    text = path.read_text(encoding="utf-8")
    assert text.count(f"<B>{_format_time(20, 1)}</B>") == 1
    assert f"<B>{_format_time(30, 1)}</B>" not in text
