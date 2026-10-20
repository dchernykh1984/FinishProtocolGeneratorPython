"""Real file-to-protocol generation for separate attempt timing streams."""

from PySide6.QtWidgets import QApplication

from app.attempt_rules import AttemptRule, rules_json
from app.config import RACE_TYPE_NUMBER_OF_TRIES, RaceConfig
from app.main_window import _GenerateWorker


def test_worker_uses_highest_stream_as_finish_and_writes_only_intermediate_splits(
    tmp_path,
):
    app = QApplication.instance() or QApplication([])
    start = tmp_path / "start.txt"
    groups = tmp_path / "groups.txt"
    start.write_text("1#Name#G#3#1#1990#T#C#Comment#\n", encoding="utf-8")
    groups.write_text("G#0 00:00:00.000#\n", encoding="utf-8")
    for name, seconds in (
        ("results.txt", [1000, 1100, 1200]),
        ("results_1.txt", [1010, 1108, 1205]),
        ("results_2.txt", [1020, 1118, 1215]),
        ("results_3.txt", [1128, 1220]),
    ):
        text = "\n".join(
            f"1#0 00:{int(t // 60):02d}:{int(t % 60):02d}.000#nextLap#" for t in seconds
        )
        (tmp_path / name).write_text(text + "\n", encoding="utf-8")
    cfg = RaceConfig(
        race_type=RACE_TYPE_NUMBER_OF_TRIES,
        attempt_rules_json=rules_json((AttemptRule("R", 1, (2, 3), "asc"),)),
        start_protocol_file=str(start),
        group_time_file=str(groups),
        finish_time_file=str(tmp_path / "results.txt"),
        remote_points_path=str(tmp_path),
        n_remote_points=3,
        group_protocol_file=str(tmp_path / "gr.html"),
        absolute_protocol_file=str(tmp_path / "abs.html"),
    )
    worker = _GenerateWorker(cfg)
    errors, completed = [], []
    worker.error.connect(errors.append)
    worker.finished_ok.connect(lambda: completed.append(True))
    worker.run()
    assert not errors
    assert completed == [True]
    for name in ("gr.html", "abs.html"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "(3 split)" in text
        assert "(4 split)" not in text
        assert "DNF</td>" in text
        assert "<B>00:00:20.0</B>" in text
    app.processEvents()


def test_invalid_rules_fail_before_replacing_protocol_files(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "gr.html"
    path.write_text("previous result", encoding="utf-8")
    cfg = RaceConfig(
        race_type=RACE_TYPE_NUMBER_OF_TRIES,
        attempt_rules_json="[",
        start_protocol_file="data/start.txt",
        group_time_file="data/groups.txt",
        finish_time_file="data/results.txt",
        group_protocol_file=str(path),
        absolute_protocol_file=str(tmp_path / "abs.html"),
    )
    errors = []
    worker = _GenerateWorker(cfg)
    worker.error.connect(errors.append)
    worker.run()
    assert errors and "JSON" in errors[0]
    assert path.read_text(encoding="utf-8") == "previous result"
    assert not (tmp_path / "abs.html").exists()
    app.processEvents()
