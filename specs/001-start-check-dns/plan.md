# Implementation Plan: A rider who missed the start check is DNS, and Disable DNS

**Branch**: `docs/specifications` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

## Summary

One flag on a rider says he missed the start check; the start check list sets it where it used to
disqualify him. The statuses get one order -- finishers, DNF, DNS, DSQ -- read by the comparison
that every table, the site document and the live statistics share. "Disable DNS" is a setting
beside "Disable DNF" and "Disable DSQ", saved as a new tag at the end of `fpg_info.txt`. The
research, the data model, the contract and the validation are short enough to live in this file.

## Technical Context

**Language/Version**: Python 3.14. **Primary Dependencies**: PySide6, nothing new. **Storage**:
`fpg_info.txt`, positional, one new tag at the end. **Testing**: pytest with the 90% coverage
gate, the window's behaviour tests and the golden protocols. **Target Platform**: the portable
desktop builds. **Project Type**: desktop app. **Performance, constraints, scale**: nothing new --
one more yes or no per rider.

## Constitution Check

- I, offline first: nothing about fetching or publishing changes.
- II, shared contracts: the start check list keeps its format, and nothing new is read from the
  start protocol or the chronometers.
- III, old files stay readable: `DisableDNS` goes after `QualificationPlaceLabel`, the last tag; a
  file without it loads with the setting off, and an older version stops reading before it.
- IV, one calculation for every view: the status is decided once, by `place_status` in
  `app/protocol_rows.py`, and the order reads it from there; the HTML, the document and the live
  statistics follow from that.
- V, report, do not guess: the check list's ERROR stays in the log, with or without "Disable DNS".
- VI, a failure is reported: no new way to fail.
- VII, tests: every requirement gets a test, and the golden protocols do not change (SC-004).
- VIII, history: one-line commits, in this pull request.

The design passes every gate; nothing needs justifying under Complexity Tracking.

## Decisions

1. **A flag, not a new value of `finished`.** `missed_start_check` on the rider, while `finished`
   and `disqualified` keep their meaning, so a DNS rider who rode keeps his laps and his time -- the
   maintainer's decision -- without the cells learning a new case. Rejected: dropping his laps, which
   the maintainer ruled out.
2. **The order compares statuses first**, ranked through `place_status`: finisher 0, DNF 1, DNS 2,
   DSQ 3; riders of one status fall through to today's comparison. Rejected: a case per status in
   `_first_better`, which would be a second place that decides a status.
3. **"Disable DNS" is read where the status is decided**: the start check does not set the flag,
   `place_status` calls a rider who did not finish and did not start DNF, and `is_printed` takes
   such a rider for started, so he prints as a DNF row.
4. **Printing**: a rider who missed the start check needs "Print DNS", and "Print DNF" as well
   when he did not finish, as every rider who did not finish needs -- so "Disable DNF", which makes
   everyone a finisher, does not hide him.
5. **The tag**: a load resets the setting before it reads the file, so the key=value format and
   every file written before the tag give off.

## Data model

- `FinishProtocolElement.missed_start_check`: False unless the check list is on and holds marks,
  the rider has none later than his start minus the registration period, and "Disable DNS" is
  off.
- `RaceConfig.disable_dns`: False by default.
- The status, worked out by `place_status`: DSQ when disqualified; otherwise DNS when he missed
  the start check; otherwise, when he did not finish, DNF if he started or "Disable DNS" is on and
  DNS if not; otherwise his place.

## Contract: the race info tag

`DisableDNS` on one line and `1` (on) or `0` (off) on the next, written after
`QualificationPlaceLabel`. A file without it: off.

## Validation

- `uv run pytest`: the new tests cover FR-001 to FR-008, and the golden protocols stay as they
  are.
- In the program: a race with "Use start check list" on and one rider missing from the check
  list; Generate Protocol: he reads DNS with his laps, after the DNF riders. Tick "Disable DNS"
  and generate again: he is placed. Save, restart: the box is still ticked.

## Project Structure

Code: `app/models.py` (the flag), `app/config.py` (the setting), `app/calculator.py` (the start
check, the order), `app/protocol_rows.py` (status, printing, group places), `app/html_writer.py`
(the seeding protocol), `app/file_io.py` and `app/main_window.py` (the tag, the checkbox). Tests:
`tests/test_calculator.py`, `tests/test_protocol_rows.py`, `tests/test_seeding_protocol.py`,
`tests/test_race_info_source_roundtrip.py`. Description: `specs/app/scoring.md`, `files.md`,
`protocols.md`.

## Complexity Tracking

No violations.
