"""Eliminator Finals through the real generation worker.

The point of these is the switch of meaning: in this mode groups.txt describes
ladders, the start protocol carries qualification places and the finish file holds
heat results, so none of the timing pipeline may run.
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
_RESULTS = "101#105#104#108#\n102#106#103#107#\n"


def _cfg(tmp_path: Path, **kwargs: object) -> RaceConfig:
    (tmp_path / "start.txt").write_text(_START, encoding="utf-8")
    (tmp_path / "groups.txt").write_text(_LADDERS, encoding="utf-8")
    (tmp_path / "results.txt").write_text(_RESULTS, encoding="utf-8")
    cfg = RaceConfig()
    cfg.race_type = RACE_TYPE_ELIMINATOR_FINALS
    cfg.start_protocol_file = str(tmp_path / "start.txt")
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
    def test_it_is_no_longer_refused(self, tmp_path: Path) -> None:
        _messages, errors = _run(_cfg(tmp_path))
        assert errors == []

    def test_the_group_protocol_holds_the_ladder(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _run(cfg)
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        assert "Final" in page and "Small final" in page
        # The two heats were ridden, so their finishing order is on the page.
        assert "101" in page and "108" in page

    def test_no_absolute_protocol_is_written(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        _run(cfg)
        assert not Path(cfg.absolute_protocol_file).exists()

    def test_the_run_reports_what_it_read(self, tmp_path: Path) -> None:
        messages, _errors = _run(_cfg(tmp_path))
        assert "  1 ladder(s) loaded" in messages
        assert "  8 competitors loaded" in messages
        assert "  2 heat result(s) loaded" in messages


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
        # After _cfg, which lays down the ladder fixtures this race must not use.
        Path(cfg.group_time_file).write_text("Men#0 10:00:00.000#\n", encoding="utf-8")
        Path(cfg.start_protocol_file).write_text(
            "101#Rider#Men#1#1#1990#T#C##0 00:00:00.000#\n", encoding="utf-8"
        )
        Path(cfg.finish_time_file).write_text("", encoding="utf-8")
        _run(cfg)
        assert sent


class TestProblemsAreReported:
    def test_an_unsupported_heat_size_is_logged(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        Path(cfg.group_time_file).write_text("Men#8#2#\n", encoding="utf-8")
        messages, errors = _run(cfg)
        assert errors == []
        assert any("only 2 and 4 are supported" in m for m in messages)

    def test_a_result_nobody_is_waiting_for_is_logged(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        Path(cfg.finish_time_file).write_text("999#998#\n", encoding="utf-8")
        messages, _errors = _run(cfg)
        assert any("no heat is waiting" in m for m in messages)

    def test_a_missing_file_is_reported_rather_than_crashing(
        self, tmp_path: Path
    ) -> None:
        cfg = _cfg(tmp_path)
        cfg.group_protocol_file = str(tmp_path / "nowhere" / "group.html")
        _messages, errors = _run(cfg)
        assert len(errors) == 1


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
def test_a_ladder_of_any_depth_generates(tmp_path: Path, rounds: int) -> None:
    cfg = _cfg(tmp_path)
    Path(cfg.group_time_file).write_text(f"Men#4#{rounds}#\n", encoding="utf-8")
    _messages, errors = _run(cfg)
    assert errors == []
    assert Path(cfg.group_protocol_file).exists()


class TestQualificationFeedsTheFinals:
    """The pair has to work as one: qualification seeds the ladder.

    Eliminator Qualification writes a start-protocol file whose last field is the
    place each rider took. That file is what the finals mode reads places from, so
    the two modes only line up if the round trip does.
    """

    def _qualify(self, tmp_path: Path) -> Path:
        start = "\n".join(
            f"{100 + i}#Rider {i}#Men#1#1#1990#Team#City##0 00:00:00.000#"
            for i in range(1, 9)
        )
        # Slower bibs finish later, so the qualification order is 108 .. 101.
        finishes = "\n".join(
            f"{100 + i}#0 10:0:{10 - i}.000#finish#" for i in range(1, 9)
        )
        (tmp_path / "q_start.txt").write_text(start, encoding="utf-8")
        (tmp_path / "q_groups.txt").write_text(
            "Men#0 10:00:00.000#\n", encoding="utf-8"
        )
        (tmp_path / "q_results.txt").write_text(finishes, encoding="utf-8")
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

    def test_the_seeding_file_seeds_the_ladder(self, tmp_path: Path) -> None:
        seeding = self._qualify(tmp_path)
        cfg = _cfg(tmp_path)
        cfg.start_protocol_file = str(seeding)
        Path(cfg.finish_time_file).write_text("", encoding="utf-8")
        _messages, errors = _run(cfg)
        assert errors == []
        page = Path(cfg.group_protocol_file).read_text(encoding="utf-8")
        # The fastest qualifier meets the fourth, eighth and fifth, as the C++
        # bracket paired them.
        assert page.index("1/2 final 1") < page.index("Final")
        for bib in range(101, 109):
            assert str(bib) in page
