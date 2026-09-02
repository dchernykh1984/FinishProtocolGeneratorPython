# finish-protocol-generator - agent guide

Python 3.14 + PySide6 desktop app, managed with uv. It generates finish protocols for
offline referee events and can sync them to a cycling website. This file plus the skills
in `.claude/skills/` tell an agent how to work in this repo. Detailed skills:

- `.claude/skills/contributing` - branch, commit, open a PR, drive CI to green.
- `.claude/skills/cycling-site` - how the app reads from and writes to the website.
- `.claude/skills/local-testing` - running tests and Qt/test gotchas.

## Golden rules for commits and PRs

- Commit messages are EXACTLY ONE LINE: a Conventional Commits subject
  (`type(scope): summary`). No body, no blank line, and no `Co-Authored-By` trailer.
- PR descriptions must not contain any Claude/Anthropic attribution: no
  "Generated with Claude Code" footer and no co-author line. Real content only.
- `cz check` (commitizen) runs in CI on every PR and rejects non-conventional subjects.
  Common types: feat, fix, chore, docs, test, refactor, style, ci, build, perf.
- release-please turns merged commits into CHANGELOG entries and version bumps, so the
  subject line is user-facing. Keep it accurate.

## Quality gates (all enforced in CI)

Run before pushing:

- `uv run pre-commit run --all-files` - ruff (lint with autofix), ruff-format, mypy,
  end-of-file and whitespace fixers, and a `no-non-ascii` hook.
- `uv run pytest` - runs with `--cov-fail-under=90`; coverage must stay at or above 90%.

ASCII ONLY: the `no-non-ascii` hook scans python, yaml, markdown, toml, shell and json.
Never add non-ASCII characters (emoji, smart quotes, en/em dashes, Cyrillic, ...) to any
tracked file except `uv.lock` and `CHANGELOG.md`. Write code comments and docs in English.

## Repo facts and gotchas

- Package manager is uv: `uv sync`, `uv run pytest`, `uv run python -m app.main`.
- ruff line length is 88; mypy uses `ignore_missing_imports`; mccabe max complexity 10.
- Coverage config omits `app/main.py` and `app/main_window.py`, but they still have
  behaviour tests. Keep writing tests for new UI logic.
- `data/` holds GOLDEN protocol HTML (`data/*.html`) used by `tests/test_example_data.py`.
  Do not edit golden files as a side effect. The maintainer also keeps live race data in
  the working tree, so `data/` and `fpg_info.txt` are often dirty - never stage them
  unless you intentionally changed them, and if the golden tests fail only because the
  working `data/` is dirty, that is a data issue, not your change.
- `fpg_info.txt` is a line-based config: positional C++ fields first, then tagged
  key/value lines. One physical line per field, so a value containing a newline shifts
  every following field and corrupts the file. Never store multi-line values there.
