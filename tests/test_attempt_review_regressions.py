"""Third-review regressions through the protocol and live-stat consumers."""

import pytest

from app.attempt_rules import AttemptRule, rules_json
from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import RACE_TYPE_NUMBER_OF_TRIES, RaceConfig
from app.html_writer import write_absolute_protocol, write_group_protocol
from app.models import FinishCompetitorElement, GroupStartElement, StartProtocolElement


def scenario(times, *, start=1000, direction="asc"):
    cfg = RaceConfig(
        race_type=RACE_TYPE_NUMBER_OF_TRIES,
        attempt_rules_json=rules_json((AttemptRule("Result", 1, (1,), direction),)),
        send_group_statistics=True,
        send_absolute_statistics=True,
    )
    starts, marks = [], []
    for number, duration in enumerate(times, 1):
        bib = str(number)
        starts.append(StartProtocolElement.from_line(f"{bib}#Rider {bib}#G#1#1#####"))
        marks.append(FinishCompetitorElement(bib, start, "nextLap"))
        if duration is not None:
            marks.append(FinishCompetitorElement(bib, start + duration, "nextLap"))
    protocol = calculate_protocol(starts, [], marks, [], [], cfg, [])
    return generate_sorted_protocol(protocol, cfg, 0), cfg


@pytest.mark.parametrize("scope", ["group", "absolute"])
@pytest.mark.parametrize("duration", [30, None])
def test_zero_timestamp_is_a_real_attempt_start(tmp_path, scope, duration):
    protocol, cfg = scenario([duration], start=0)
    path = tmp_path / "result.html"
    writer = write_group_protocol if scope == "group" else write_absolute_protocol
    writer(str(path), protocol, [GroupStartElement("G", 0)], cfg, 0)
    text = path.read_text(encoding="utf-8")
    assert "Rider 1" in text
    if duration is not None:
        assert protocol[0].finished
        assert "00:00:30.0" in text
        assert ">DNF<" not in text
    else:
        assert ">DNF<" in text
