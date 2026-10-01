# finish-protocol-generator - agent guide

Python 3.14 + PySide6 desktop app, managed with uv. It generates finish protocols for
offline referee events and can sync them to a cycling website. This file plus the skills
in `.agents/skills/` tell an agent how to work in this repo. Detailed skills:

- `.agents/skills/contributing` - branch, commit, open a PR, drive CI to green.
- `.agents/skills/cycling-site` - how the app reads from and writes to the website.
- `.agents/skills/local-testing` - running tests and Qt/test gotchas.

## Golden rules for commits and PRs

- Commit messages are EXACTLY ONE LINE: a Conventional Commits subject
  (`type(scope): summary`). No body, no blank line, and no `Co-Authored-By` trailer.
- PR descriptions must not contain any assistant attribution: no
  "Generated with an assistant" footer and no co-author line. Real content only.
- `cz check` (commitizen) runs in CI on every PR and rejects non-conventional subjects.
  Common types: feat, fix, chore, docs, test, refactor, style, ci, build, perf.
- release-please turns merged commits into CHANGELOG entries and version bumps, so the
  subject line is user-facing. Keep it accurate.
- **Outward-facing actions require explicit user authorization.** A request to push
  and open a pull request authorizes those actions for the current task. If no such
  authorization was given, show the exact command and wait for consent. Merging,
  tagging, deleting or force-pushing a branch, and cutting a release require their
  own explicit request. Reading (status, log, diff, fetch, `gh ... view`) needs no
  permission.

## Quality gates (all enforced in CI)

Run before pushing:

- `uv run pre-commit run --all-files` - ruff (lint with autofix), ruff-format, mypy,
  end-of-file and whitespace fixers, and a `no-non-ascii` hook.
- `uv run pytest` - runs with `--cov-fail-under=90`; coverage must stay at or above 90%.

ASCII ONLY: the `no-non-ascii` hook scans python, yaml, markdown, toml, shell and json.
Never add non-ASCII characters (emoji, smart quotes, en/em dashes, Cyrillic, ...) to any
tracked file except `uv.lock` and `CHANGELOG.md`. Write code comments and docs in English.

Write files as UTF-8. On Windows a PowerShell redirect, `Set-Content` or `Out-File`
defaults to UTF-16, and the ASCII hook then rejects a file whose text looks perfectly
plain in an editor - the bytes are the problem, not the characters. `file <path>` says
which encoding you actually wrote.

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

## Coding agent context

Codex reads this `AGENTS.md` at startup and discovers skills in `.agents/skills/`.
Read the relevant skill before using its workflow. Claude keeps `CLAUDE.md`,
`.claude/skills/` and its own settings; update both guides and skill copies when a
shared convention changes.

This repository has no custom post-edit Claude hooks to migrate. The existing
Git pre-commit hooks and CI checks work independently of the coding assistant;
use the documented quality gates. No custom Codex hooks are configured here.

Claude permission allowlists and attribution settings are not Codex settings.
Codex uses its own native permissions and approvals. An explicit user request to
push and open a pull request authorizes those actions for that task; never merge,
tag or release unless the user asks for it.
