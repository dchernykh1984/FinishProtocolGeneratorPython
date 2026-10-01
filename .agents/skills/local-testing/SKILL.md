---
name: local-testing
description: How to run and write tests for this PySide6 app, including headless Qt and MainWindow test patterns. Use when adding or running tests or debugging test failures.
---

# Local testing

- Run all tests: `uv run pytest` (parallel via xdist, coverage gate 90%). One file:
  `uv run pytest tests/test_x.py`. Coverage-below-90 warnings when running a subset are
  expected - judge a subset by pass/fail, and run the full suite before pushing.
- Qt runs headless: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` before any
  PySide import. In a test module reuse the app:
  `_app = QApplication.instance() or QApplication(sys.argv)`.
- MainWindow isolation: `MainWindow.__init__` calls `_try_auto_load()`, which reads the
  on-disk `fpg_info.txt` from the app path. That makes raw tests depend on machine state
  (and can even start an auto-refresh timer). Neutralize it with an autouse fixture:

  ```python
  @pytest.fixture(autouse=True)
  def _no_auto_load(monkeypatch):
      monkeypatch.setattr(MainWindow, "_try_auto_load", lambda self: None)
  ```

- Round-trip config tests use the real `MainWindow._save_race_info_to_path` and
  `_load_race_info_from_path` against a temp file. A stable config loads and re-saves
  identically.
- When faking a QThread-like object, its methods mirror Qt's camelCase API (e.g.
  `isRunning`), so add `# noqa: N802` on those defs to satisfy ruff pep8-naming.
- Coverage omits `app/main.py` and `app/main_window.py`, but still add behaviour tests
  for UI logic by driving the real methods (`closeEvent`, `_on_*`, save/load).
- Golden data: `tests/test_example_data.py` compares against `data/*.html`. Do not edit
  those golden files to make a test pass. If they fail only because the working `data/`
  is dirty with the maintainer's live race data, that is unrelated to your change -
  check against a clean `data/` before investigating.
