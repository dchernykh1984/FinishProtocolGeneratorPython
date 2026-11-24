# Tasks: A rider who missed the start check is DNS, and Disable DNS

**Input**: [spec.md](spec.md), [plan.md](plan.md). Every task ships with its tests; the golden
protocols must not change (SC-004).

## Phase 1: Foundational

- [ ] T001 Add `missed_start_check` (False by default) to `FinishProtocolElement` in
  `app/models.py`, and `disable_dns` (False by default) to `RaceConfig` in `app/config.py`

## Phase 2: User Story 1 - A rider who missed the start check is DNS (P1)

**Independent test**: a group of a finisher, a DNF, a rider who rode without a check mark and a
DSQ reads 1, DNF, DNS with his laps and time, DSQ.

- [x] T002 [US1] The start check list sets `missed_start_check` where it disqualified, the ERROR
  kept, in `app/calculator.py`; tests in `tests/test_calculator.py`
- [x] T003 [US1] `place_status` says DNS for a rider who missed the start check and is not
  disqualified, in `app/protocol_rows.py`; tests in `tests/test_protocol_rows.py`
- [x] T004 [US1] `_first_better` ranks the statuses first -- finisher, DNF, DNS, DSQ, through
  `place_status` -- and keeps today's comparison inside a status, in `app/calculator.py`; tests in
  `tests/test_calculator.py`
- [x] T005 [US1] Such a rider is printed only with "Print DNF" and "Print DNS", takes no group
  place and is left out of the shared time warning, in `app/protocol_rows.py` and
  `app/calculator.py`; tests in `tests/test_protocol_rows.py`
- [x] T006 [P] [US1] The seeding protocol leaves him out, in `app/html_writer.py`; test in
  `tests/test_seeding_protocol.py`
- [x] T007 [US1] `specs/app/scoring.md` and `specs/app/protocols.md` describe the DNS of the start
  check and the order of the statuses

## Phase 3: User Story 2 - Disable DNS (P2)

**Independent test**: with the setting on, the rider without a check mark is placed by his
result, a rider who never started reads DNF, and the setting survives a save and a restart.

- [ ] T008 [US2] With "Disable DNS" the start check sets no flag, and `place_status` and
  `is_printed` take a rider who did not start for started, in `app/calculator.py` and
  `app/protocol_rows.py`; tests in `tests/test_calculator.py` and `tests/test_protocol_rows.py`
- [ ] T009 [US2] The `DisableDNS` tag after `QualificationPlaceLabel`: read in `app/file_io.py`,
  reset before a load and written in `app/main_window.py`; tests in
  `tests/test_race_info_source_roundtrip.py`
- [ ] T010 [US2] The checkbox "Disable DNS (everyone counts as started)" between "Disable DNF"
  and "Disable DSQ" on the Options tab, in `app/main_window.py`; a window test in
  `tests/test_race_info_source_roundtrip.py`
- [ ] T011 [US2] `specs/app/scoring.md` and `specs/app/files.md` describe "Disable DNS" and its tag

## Phase 4: Polish

- [ ] T012 `uv run pre-commit run --all-files` and `uv run pytest` pass, the golden protocols are
  unchanged, and `spec.md` says it is implemented in this pull request

## Dependencies

T001 comes first. User Story 2 builds on User Story 1's `place_status` and `is_printed`, so it
follows it; inside User Story 1, T006 can go beside T005.

## Implementation strategy

User Story 1 alone is the useful part: a missed start check stops disqualifying. User Story 2
adds the switch and its saved setting on top.
