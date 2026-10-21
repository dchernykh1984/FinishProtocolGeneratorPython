---
name: number-of-tries
description: Diagnose or change Number of Tries scoring rules, attempt timing windows, configuration and protocol output in this generator.
---

# Number of Tries

## Scoring contract

- Rules belong to the event's generator config, not the website, group or participant.
  The numeric lap count in each start-protocol row still limits available attempts.
- `RaceConfig.attempt_rules_json` is an ordered JSON array saved under `AttemptRules`
  as one physical line in `fpg_info.txt`. Use `parse_attempt_rules()` and `rules_json()`
  from `app/attempt_rules.py`; labels and escaped newlines must survive round trips.
- Each rule has `label`, `attempts`, `attempt_numbers` and `sort`. Labels only explain
  the rule. Attempt numbers are unique positive integers, starting at 1; the count
  cannot exceed the eligible list length. `sort` is `asc` or `desc`.
- Sum the fastest completed eligible attempts regardless of sort direction. Compare
  rules in array order, first by counted attempts (more is better), then by their sum
  in the rule's direction. Fall back to numeric bib order when all rules tie.
- The first rule alone defines the displayed result and completion status. A failed
  excluded attempt does not cause overall DNF if enough primary attempts are complete.
  Later rules only break ties; qualification does not freeze later start order.
- Bold only attempts actually selected by the first rule. Equal times select the
  earlier attempt. Gaps use the first rule's direction; the rider ahead is positive
  in live stats even for a descending primary rule.
- An empty array retains legacy `N:1,2,3` rules in participant Additional info.

Example: best of attempts 2 and 3, with reverse qualification as a tie-break:

```json
[{"label":"Result","attempts":1,"attempt_numbers":[2,3],"sort":"asc"},{"label":"Qualification","attempts":1,"attempt_numbers":[1],"sort":"desc"}]
```

## Timing contract

- With Control points = 0, the main stream alternates start, finish, start, finish.
  A finish rejected by `minimal_time_for_lap` leaves that slot unfinished, including
  with legacy Additional info rules. Never borrow the next start as its finish;
  older versions could merge attempts this way. Keep later pair numbers intact.
- With N > 0, stream 0 contains starts, streams 1..N-1 contain intermediate marks,
  and stream N contains finishes. Each start opens a window ending at the next start;
  the last window stays open. Choose the earliest valid finish inside that window.
- Match intermediate points in chronological point order before the finish. Missing
  points do not invalidate a finish time; unknown segments render as UNKNOWN or ERR.
- Keep attempt slots when a finish is missing. Never use completed-attempt count as
  an array index or renumber later attempts. A closed unfinished slot displays DNF.
- `attempt_starts`, `attempt_finishes`, `attempt_closed` and `attempts_seen` track slots;
  `n_laps_finished` counts completed attempts. Use `lap_completed()`, `lap_started()`,
  `visible_laps()` and `has_started()` in consumers. A start timestamp of 0 is valid.
- Ignore DSQ marks for attempt matching while still applying disqualification rules.
  Preserve every penalty decision, including decisions sharing a crossing timestamp;
  time-matching deduplication must not discard penalties or their escaped explanations.
- Use `RaceConfig.intermediate_point_count(len(remote_points))` in calculation and
  HTML generation: the terminal attempt finish stream is not an intermediate point.

## Boundaries and regression checks

- Keep the rule editor directly below Race type, visible only for Number of Tries.
  Invalid active rules block generation and explicit saves. On exit, offer to stay
  with the draft or discard it and save the last valid rules plus other settings.
  Without a valid rule in the loaded race, fall back to `[]`; never restore rules
  from a previously loaded race. Log discarded edits as a warning.
- In other modes, preserve valid inactive rules, but reset invalid ones to `[]`
  without blocking config load, save or exit. Log each reset as a warning, without
  a modal dialog; subsequent saves of the cleared value must not warn again.
  Do not decode JSON escapes as config line breaks in the key/value loader.
- `skip_first_lap_effective()` also includes Custom Start. Restrict attempt-specific
  changes to Number of Tries; Custom Start keeps its legacy earliest-crossing behavior,
  including an earlier DSQ mark even when Disable DSQ is enabled.
- Core code: `app/attempt_rules.py`, `app/attempt_calculator.py`,
  `app/attempt_rules_editor.py`, `app/models.py`, `app/calculator.py`.
- Verify both group and absolute HTML, live stats, both config formats and unchanged
  behavior in other race modes. Relevant tests: `tests/test_attempt_*.py`,
  `tests/test_calculator.py`, `tests/test_html_writer.py`, `tests/test_live_stats.py`
  and the untouched `tests/test_example_data.py` golden fixtures.
