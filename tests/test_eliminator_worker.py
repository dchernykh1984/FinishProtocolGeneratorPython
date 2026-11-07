"""Eliminator Finals through the real generation worker.

The point of these is which file means what. The ladders live in their own file, and
the chronometer's two files keep their ordinary meaning: groups.txt says when each
heat started -- a heat is just a group to it -- and results.txt holds plain finish
marks, so one bib honestly appears in several heats.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.config import (
    HTTP_ACTION_NOTHING,
    HTTP_ACTION_UPLOAD,
    RACE_TYPE_ELIMINATOR_FINALS,
    RACE_TYPE_MASS_SPLITTED,
    RaceConfig,
)
from app.main_window import _GenerateWorker

_app = QApplication.instance() or QApplication(sys.argv)

_START = "\n".join(
    f"{100 + p}#Rider {p}#Men#1#1#1990#Team#City##{p}#" for p in range(1, 9)
)
_LADDERS = "Men#4#2#\n"

_SEMI1 = "Men - 1/2 final 1"
_SEMI2 = "Men - 1/2 final 2"
_FINAL = "Men - Final"
_SMALL = "Men - Small final"


def _chronometer(heats: list[tuple[str, list[str]]]) -> tuple[str, str]:
    """groups.txt and results.txt for heats ridden a minute apart, in order."""
    starts: list[str] = []
    marks: list[str] = []
    minute = 0
    for name, order in heats:
        starts.append(f"{name}#0 10:{minute:02d}:00.000#")
        for index, bib in enumerate(order, start=1):
            marks.append(f"{bib}#0 10:{minute:02d}:{index:02d}.000#finish#")
        minute += 1
    return "\n".join(starts) + "\n", "\n".join(marks) + "\n"


#: Both semi-finals ridden; the finals are still to come.
_SEMIS = [
    (_SEMI1, ["101", "105", "104", "108"]),
    (_SEMI2, ["102", "106", "103", "107"]),
]


def _cfg(tmp_path: Path, heats: list[tuple[str, list[str]]] | None = None, **kwargs):
    groups, results = _chronometer(_SEMIS if heats is None else heats)
    (tmp_path / "start.txt").write_text(_START, encoding="utf-8")
    (tmp_path / "ladders.txt").write_text(_LADDERS, encoding="utf-8")
    (tmp_path / "groups.txt").write_text(groups, encoding="utf-8")
    (tmp_path / "results.txt").write_text(results, encoding="utf-8")
    cfg = RaceConfig()
    cfg.race_type = RACE_TYPE_ELIMINATOR_FINALS
    cfg.start_protocol_file = str(tmp_path / "start.txt")
    cfg.eliminator_ladder_file = str(tmp_path / "ladders.txt")
    cfg.group_time_file = str(tmp_path / "groups.txt")
    cfg.finish_time_file = str(tmp_path / "results.txt")
    cfg.group_protocol_file = str(tmp_path / "group.html")
    cfg.absolute_protocol_file = str(tmp_path / "absolute.html")
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    return cfg


def _run(cfg: RaceConfig) -> tuple[list[str], list[str]]:
    worker = _GenerateWorker(cfg)
    messages: list[str] = []
    errors: list[str] = []
    worker.log_message.connect(messages.append)
    worker.error.connect(errors.append)
    worker.run()
    return messages, errors


class TestTheLadderRuns:
    def test_it_generates_without_error(self, tmp_path: Path) -> None:
        _messages, errors = _run(_cfg(tmp_path))
        assert errors == []

    def test_the_group_protocol_holds_the_ladder(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _run(cfg)
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        assert "Final" in page and "Small final" in page
        # The two heats were ridden, so their finishing order is on the page.
        assert "101" in page and "108" in page

    def test_the_times_ridden_reach_the_protocol(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _run(cfg)
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        assert "00:00:01.0" in page

    def test_no_absolute_protocol_is_written(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _run(cfg)
        assert not Path(cfg.absolute_protocol_file).exists()

    def test_the_run_reports_what_it_read(self, tmp_path: Path) -> None:
        messages, _errors = _run(_cfg(tmp_path))
        assert "  1 ladder(s) loaded" in messages
        assert "  8 competitors loaded" in messages
        assert "  2 heat start(s) loaded" in messages
        assert "  8 finish mark(s) loaded" in messages


class TestTheHeatListForTheChronometer:
    def test_it_is_written_beside_the_group_protocol(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _run(cfg)
        listed = (tmp_path / "heats.txt").read_text(encoding="utf-8").splitlines()
        assert listed == [_SEMI1, _SEMI2, _FINAL, _SMALL]

    def test_the_run_says_where_it_went(self, tmp_path: Path) -> None:
        messages, _errors = _run(_cfg(tmp_path))
        assert any("heat names for the chronometer" in m for m in messages)

    def test_it_follows_the_ladder_it_was_given(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        Path(cfg.eliminator_ladder_file).write_text("Men#4#1#\n", encoding="utf-8")
        _run(cfg)
        listed = (tmp_path / "heats.txt").read_text(encoding="utf-8").splitlines()
        assert listed == [_FINAL, _SMALL]

    def test_it_is_refused_rather_than_overwriting_an_input(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        # The group protocol sits beside the start list, so the heat list would
        # land on it.
        cfg.start_protocol_file = str(tmp_path / "heats.txt")
        Path(cfg.start_protocol_file).write_text(_START, encoding="utf-8")
        messages, errors = _run(cfg)
        assert errors == []
        assert any("would overwrite the start protocol" in m for m in messages)
        assert Path(cfg.start_protocol_file).read_text(encoding="utf-8") == _START


class TestTheTimingPipelineStaysOut:
    def test_a_start_file_of_places_does_not_break_the_time_parser(
        self, tmp_path: Path
    ) -> None:
        # Field 9 is "1".."8" here; read as a time of day it raises, which is why the
        # finals path asks for it as a place.
        _messages, errors = _run(_cfg(tmp_path))
        assert errors == []

    def test_live_statistics_are_not_sent(self, tmp_path: Path, monkeypatch) -> None:
        sent: list[object] = []

        def _send(*args: object, **kwargs: object) -> int:
            sent.append(args)
            return 0

        monkeypatch.setattr("app.main_window.upload_live_stats", _send)
        cfg = _cfg(
            tmp_path,
            http_site_url="https://example.test",
            http_upload_token="t",
            send_group_statistics=True,
            http_groups_action=HTTP_ACTION_NOTHING,
            http_absolute_action=HTTP_ACTION_NOTHING,
        )
        _run(cfg)
        assert sent == []

    def test_a_timed_race_still_sends_live_statistics(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # The guard must be about this mode, not about live stats in general.
        sent: list[object] = []

        def _send(*args: object, **kwargs: object) -> int:
            sent.append(args)
            return 0

        monkeypatch.setattr("app.main_window.upload_live_stats", _send)
        cfg = _cfg(
            tmp_path,
            race_type=RACE_TYPE_MASS_SPLITTED,
            http_site_url="https://example.test",
            http_upload_token="t",
            send_group_statistics=True,
            http_groups_action=HTTP_ACTION_NOTHING,
            http_absolute_action=HTTP_ACTION_NOTHING,
        )
        # After _cfg, which lays down the finals fixtures this race must not use.
        Path(cfg.group_time_file).write_text("Men#0 10:00:00.000#\n", encoding="utf-8")
        Path(cfg.start_protocol_file).write_text(
            "101#Rider#Men#1#1#1990#T#C##0 00:00:00.000#\n", encoding="utf-8"
        )
        Path(cfg.finish_time_file).write_text("", encoding="utf-8")
        _run(cfg)
        assert sent


class TestProblemsAreReported:
    def test_an_unsupported_heat_size_is_logged_and_stops_the_run(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        Path(cfg.eliminator_ladder_file).write_text("Men#8#2#\n", encoding="utf-8")
        messages, errors = _run(cfg)
        assert any("only 2 and 4 are supported" in m for m in messages)
        # The group has qualifiers but no usable ladder, so nothing is written.
        assert len(errors) == 1
        assert "No ladder for: Men" in errors[0]

    def test_a_group_whose_row_is_still_blank_stops_the_run(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        Path(cfg.eliminator_ladder_file).write_text("Men###\n", encoding="utf-8")
        _messages, errors = _run(cfg)
        assert len(errors) == 1
        assert "No ladder for: Men" in errors[0]
        assert not Path(cfg.group_protocol_file).exists()

    def test_a_ladder_file_that_is_not_there_says_what_to_do(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        Path(cfg.eliminator_ladder_file).unlink()
        _messages, errors = _run(cfg)
        assert len(errors) == 1
        assert "No ladder for: Men" in errors[0]

    def test_a_mark_that_belongs_to_no_heat_is_logged(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        with Path(cfg.finish_time_file).open("a", encoding="utf-8") as f:
            f.write("999#0 10:00:05.000#finish#\n")
        messages, _errors = _run(cfg)
        assert any("the finish mark for 999 belongs to no heat" in m for m in messages)

    def test_a_heat_name_the_chronometer_invented_is_logged(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        with Path(cfg.group_time_file).open("a", encoding="utf-8") as f:
            f.write("Men - 1/2 final 9#0 10:05:00.000#\n")
        messages, _errors = _run(cfg)
        assert any("no heat of any ladder is called" in m for m in messages)

    def test_a_missing_file_is_reported_rather_than_crashing(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        cfg.group_protocol_file = str(tmp_path / "nowhere" / "group.html")
        _messages, errors = _run(cfg)
        assert len(errors) == 1


class TestDisqualification:
    def _with_dsq(self, tmp_path: Path, **kwargs) -> RaceConfig:
        """The first semi-final ridden, with its winner disqualified afterwards."""
        cfg = _cfg(tmp_path, heats=[(_SEMI1, ["101", "105", "104", "108"])], **kwargs)
        with Path(cfg.finish_time_file).open("a", encoding="utf-8") as f:
            f.write("101#0 10:00:30.000#DSQ: cut in#\n")
        return cfg

    def test_a_disqualified_rider_does_not_go_on(self, tmp_path: Path) -> None:
        cfg = self._with_dsq(tmp_path)
        _run(cfg)
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        assert "DSQ" in page

    def test_disable_dsq_leaves_the_rider_in_the_heat(self, tmp_path: Path) -> None:
        # The setting means a disqualification mark does not disqualify, and such a
        # mark is not a crossing either, so for a ladder it means nothing at all.
        cfg = self._with_dsq(tmp_path, disable_dsq=True)
        messages, errors = _run(cfg)
        assert errors == []
        # Four crossings plus the disqualification mark, which is dropped.
        assert "  4 finish mark(s) loaded" in messages
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        assert "DSQ" not in page


class TestSiteDocument:
    def test_the_ladder_is_offered_to_the_site_as_data(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        captured: dict[str, object] = {}

        def _upload(*args: object, **kwargs: object) -> int:
            captured["document"] = kwargs.get("document")
            return 0

        monkeypatch.setattr("app.main_window.http_upload_protocol", _upload)
        cfg = _cfg(
            tmp_path,
            http_site_url="https://example.test",
            http_upload_token="t",
            http_groups_action=HTTP_ACTION_UPLOAD,
            http_absolute_action=HTTP_ACTION_NOTHING,
        )
        _run(cfg)
        document = captured.get("document")
        assert isinstance(document, dict)
        assert document["schema"] == 1
        assert document["sections"][0]["title"].endswith("Final")


@pytest.mark.parametrize("rounds", ["1", "2", "3"])
def test_a_ladder_of_any_depth_generates(tmp_path: Path, rounds: str) -> None:
    cfg = _cfg(tmp_path, heats=[])
    Path(cfg.eliminator_ladder_file).write_text(f"Men#4#{rounds}#\n", encoding="utf-8")
    _messages, errors = _run(cfg)
    assert errors == []
    assert Path(cfg.group_protocol_file).exists()


class TestQualificationFeedsTheFinals:
    """The pair has to work as one: qualification seeds the ladder.

    A qualification writes a start-protocol file whose last field is the place each
    rider took, with anyone disqualified left out and the places closed up. That file
    is what the finals mode reads places from, so the two only line up if the round
    trip does.
    """

    def _qualify(self, tmp_path: Path, dsq: str = "") -> Path:
        start = "\n".join(
            f"{100 + i}#Rider {i}#Men#1#1#1990#Team#City##0 00:00:00.000#"
            for i in range(1, 9)
        )
        # Slower bibs finish later, so the qualification order is 108 .. 101.
        lines = [f"{100 + i}#0 10:0:{10 - i}.000#finish#" for i in range(1, 9)]
        if dsq:
            lines.append(f"{dsq}#0 10:05:00.000#DSQ: cut in#")
        (tmp_path / "q_start.txt").write_text(start, encoding="utf-8")
        (tmp_path / "q_groups.txt").write_text(
            "Men#0 10:00:00.000#\n", encoding="utf-8"
        )
        (tmp_path / "q_results.txt").write_text("\n".join(lines), encoding="utf-8")
        cfg = RaceConfig()
        cfg.write_seeding_protocol = True
        cfg.start_protocol_file = str(tmp_path / "q_start.txt")
        cfg.group_time_file = str(tmp_path / "q_groups.txt")
        cfg.finish_time_file = str(tmp_path / "q_results.txt")
        cfg.group_protocol_file = str(tmp_path / "q_group.html")
        cfg.absolute_protocol_file = str(tmp_path / "q_absolute.html")
        _messages, errors = _run(cfg)
        assert errors == []
        return Path(cfg.group_protocol_file + ".txt")

    def test_qualification_writes_a_seeding_file(self, tmp_path: Path) -> None:
        seeding = self._qualify(tmp_path)
        assert seeding.exists()
        lines = seeding.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 8
        # Last field of each line is the place, counted from one.
        assert [line.split("#")[9] for line in lines] == [str(i) for i in range(1, 9)]

    def test_a_disqualified_qualifier_is_left_out_and_the_places_close_up(
        self, tmp_path: Path
    ) -> None:
        # Without renumbering, a gap at place 3 would push the eighth qualifier out
        # of an eight-seat ladder while only seven riders were seated.
        seeding = self._qualify(tmp_path, dsq="106")
        lines = seeding.read_text(encoding="utf-8").strip().split("\n")
        assert [line.split("#")[0] for line in lines] == [
            "108",
            "107",
            "105",
            "104",
            "103",
            "102",
            "101",
        ]
        assert [line.split("#")[9] for line in lines] == [str(i) for i in range(1, 8)]

    def test_the_seeding_file_seeds_the_ladder(self, tmp_path: Path) -> None:
        seeding = self._qualify(tmp_path)
        cfg = _cfg(tmp_path, heats=[])
        cfg.start_protocol_file = str(seeding)
        _messages, errors = _run(cfg)
        assert errors == []
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        # The fastest qualifier meets the fourth, eighth and fifth, as the C++
        # bracket paired them.
        assert page.index("1/2 final 1") < page.index("Final")
        for bib in range(101, 109):
            assert str(bib) in page
