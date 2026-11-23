<!--
Sync Impact Report
- Version: none -> 1.0.0 (first constitution, written with the description of the generator as
  it works today in specs/app/).
- Principles: I-VI drawn from the code and its comments (app/main_window.py, app/calculator.py,
  app/protocol_rows.py, app/eliminator.py, app/file_io.py, app/http_io.py), VII-VIII from
  CLAUDE.md / AGENTS.md and the skills under .claude/skills and .agents/skills, which stay the
  detailed runtime guidance. Merging by rebase, never squashed, is the maintainer's standing rule.
  Development Workflow and Governance are the ones StartProtocolMakerPython and
  WindowsChronometerPython follow.
- Templates: plan-template.md's "Constitution Check" gate reads these principles; no template
  needed changes.
-->

# Finish Protocol Generator Constitution

Finish Protocol Generator is the tool a race referee uses to turn a start protocol and the marks
of the chronometers into finish protocols: places, times, laps, gaps and statuses per group and
overall, or the ladders of an Eliminator Finals, and what is published from them. It runs on the
referee's own computer at the finish, often without a reliable network, and is run again and
again while the race is on.

## Core Principles

### I. Offline first

A protocol is built from the files next to the program and from nothing else. The cycling site
and an FTP server are sources the referee may choose for a stream: each is fetched into the
stream's local file before the run, and a fetch that fails leaves that file as it was while the
run goes on with what is on disk. Publishing is the last step of a run; a failed upload costs the
publication, never the protocol.

### II. The input files are shared contracts

The generator reads what other programs write: the start protocol line of StartProtocolMaker
(`number#name#group#laps#stage#year_of_birth#team#city#comment#time_shift#`, fields 0-9 read by
index, anything after them ignored), the group start lines and the crossing lines of the
chronometers (`group#time#`, `number#time#action#`), and the same lines as the site hands them
back. It writes into those files only where the referee chose to download or merge into them, and
a file it makes itself -- the seeding protocol, the heat list, the ladder table -- is refused a
path that names one of them.

### III. Old files stay readable

`fpg_info.txt` keeps the C++ generator's positional format: one field per physical line, the C++
fields first, then the Python-only tags in the order they are written, a new tag always appended
last, because a version stops reading at the first tag it does not know. A value never carries a
line break; one that arrives with it is folded into a space. A file an earlier version wrote --
the key=value format included -- loads, and retired settings migrate (the upload checkboxes, the
Eliminator Qualification race type). A file whose fields no longer line up is reported when it is
loaded and is not overwritten without the referee's yes.

### IV. One calculation for every view

What a protocol says about a competitor -- printed or not, place or status, result, gap, lap and
attempt cells, splits, lap ranks -- is worked out once, in `app/protocol_rows.py`, and read by the
HTML protocols and the structured document sent to the site alike. No value is computed in one of
them only. The live statistics are the one deliberate exception: they rank from lap finishes
alone, with the protocol's own comparison, so that a missed control point mark cannot move a live
place or gap.

### V. Report, do not guess

What the data cannot settle is said in the run log and left to the referee: two devices writing
one finish line, two riders printed with the same time without riding it, a heat start recorded
twice, a mark no heat accounts for. In a protocol, results equal to the recorded millisecond are a
dead heat and share a place; any other difference ranks them. A finals protocol that would be wrong -- a group
with qualifiers and no ladder -- is not written at all.

### VI. A failure is reported, not fatal

A fetch, an upload, a delete, or a document that cannot be built or that the site refuses is
logged and the rest of the run goes on; refused data falls back to publishing the HTML. Of a
run's failures only one that stops the run itself is shown in a dialog. Background work is
stopped before the window closes, and the settings are saved on exit.

### VII. Behaviour is proven by tests

A behaviour change ships with a test that fails without it. `app/main.py` and
`app/main_window.py` are excluded from coverage, so a window change needs a behaviour test of
its own; the 90% coverage gate covers the rest. The golden protocols (`data/*.html`,
`tests/fixtures/golden/`) pin the HTML byte for byte and change only when the HTML is meant to.
Tests use placeholder tokens, never a real competition's.

### VIII. Plain, attributable history

Files are ASCII, but for `uv.lock`, `CHANGELOG.md` and Spec Kit's generated files. Commits follow
Conventional Commits in one line with no trailers, because release-please builds the changelog
from them. Work is published under the owner's name with no AI credit anywhere. Every change goes
through a pull request from a branch off `origin/main`, merged by rebase, never squashed.

## Constraints

- Python 3.14 and PySide6, run through `uv`; HTTP through the standard library (10 seconds to
  fetch a stream, 30 seconds to upload or delete), no HTTP client dependency; FTP through
  `ftplib`, plain `ftp://` only.
- Portable builds for Windows (x64, ARM64), macOS (Apple Silicon) and Linux (x86_64, ARM64);
  the program keeps its files next to itself, so one copy of the folder serves one event.
- The site's upload token is a per-competition secret: it is kept in `fpg_info.txt` and never
  logged, printed or committed.

## Development Workflow

- A feature that changes a file format, the site exchange or what the referee sees -- the
  protocols included -- gets a specification in `specs/<NNN>-<short-name>/` made with the Spec
  Kit skills (`/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`). The
  maintainer reviews the specification and the plan before implementation starts. A change
  driven by a cycling-site issue names that issue in its specification.
- `specs/app/` describes the program as it works today. A change that alters described
  behaviour updates it in the same pull request.
- A bug fix or a small change needs no specification of its own.

## Governance

This constitution states the principles; `CLAUDE.md`, `AGENTS.md` and the skills they list hold
the detail and are kept consistent with it. The maintainer amends it through a pull request that
bumps the version -- MAJOR for a principle removed or redefined, MINOR for one added or
materially expanded, PATCH for wording -- and updates the Last Amended date.

**Version**: 1.0.0 | **Ratified**: 2026-11-23 | **Last Amended**: 2026-11-23
