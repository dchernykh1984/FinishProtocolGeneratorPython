# How results are worked out

Written from the code (`app/calculator.py`, `app/models.py`, `app/protocol_rows.py`,
`app/attempt_calculator.py`, `app/attempt_rules.py`) on 2026-11-23. Where the code does not say
why, this file does not guess. Eliminator Finals is scored its own way:
[eliminator-finals.md](eliminator-finals.md).

## Race types

| Race type | A rider's start | His result |
| --- | --- | --- |
| Mass/Splitted | His group's start time plus his start delay | Laps ridden, then the time of the last one's finish |
| Mass/Splitted (Spiridonov) | As Mass/Splitted | As Mass/Splitted, every time divided by his age coefficient |
| Custom Start | His earliest mark | As Mass/Splitted |
| Number of Tries | Each attempt's own start mark | Attempts counted, then their summed time |
| Eliminator Finals | His heat's start | His place in the finals ladder |

## Laps

Mass/Splitted, its Spiridonov variant and Custom Start:

- From the start on, the rider's next mark later than his previous crossing ends the lap, up to
  the laps of his start line. Every mark but a disqualification counts, from any of his numbers.
- A mark sooner than "Minimal lap time" after the previous crossing is dropped with an ERROR
  ("lap faster than minimal time"); with a "Time limit", so is a mark more than the limit after
  the start ("crossed after time limit").
- A control point mark of the rider's own number between two crossings adds its penalty seconds
  to that lap; with a time limit the lap's crossing is never later than the one before plus the
  limit. A mark before the start is logged as a WARNING.
- In Custom Start the earliest mark is the start, a disqualification mark included, and the
  first lap is ridden from it.

## Finishers, DNF, DNS, DSQ

- A rider who rode all his laps, or who has a `finish` mark, is a finisher; a second `finish`
  mark is a WARNING. Number of Tries decides it by its rules (below). With "Disable DNF (everyone counts as finished)" everyone is, and is ranked
  by the laps he rode.
- One who is not a finisher is DNF once he has started -- his group's start time is known, or in
  Custom Start and Number of Tries he has a mark -- and DNS otherwise.
- A `DSQ` or `DSQ: <reason>` mark in the finish marks or at a control point disqualifies, unless
  "Disable DSQ"; a reason is kept as `finish: <reason>` or `CP <n>: <reason>`. With the start
  check list on and holding any mark, a rider without a mark in it later than his start minus
  the registration period is disqualified whatever "Disable DSQ" says.
- Who is printed: one who is not a finisher only with "Print DNF"; one who rode no lap only with
  "Print DNS", or with "Print DNF" once he has started; a disqualified one only with "Print DSQ".

## The order

A port of the C++ comparison (`_first_better`); one rule is tried after another until two riders
differ:

1. Not disqualified before disqualified, then finishers before the rest.
2. Number of Tries: rule by rule (below); with no rules, more counted attempts, then the smaller
   sum of them; then the number.
3. More laps first.
4. In Custom Start, a rider with a first mark before one without.
5. Two riders with no lap and no control point passed: one who started before one who did not,
   then the smaller start delay, then the number.
6. On the lap in progress, more control points passed in a row.
7. With no point passed on that lap, the earlier finish of the last lap; otherwise the earlier
   time at the last point passed -- both compared to the recorded millisecond.
8. The lower number: as whole numbers when both are, otherwise as text.

## Places and times

- A table's finishers are numbered in its order. Two with the same result to the recorded
  millisecond over the same laps share the first of their places, and the next rider takes his
  own count: 1, 2, 2, 4. In Number of Tries the counted attempts must match as well. The place
  column of a rider who is not a finisher says DNF or DNS, of a disqualified one DSQ.
- A time prints as `HH:MM:SS` with "Digits after decimal" decimals (0-4), with `N day(s)` in front
  past 24 hours and as `UNKNOWN` past 356 days. A half rounds to the even digit, counted from the
  millisecond the chronometer wrote when the time is a recorded one and from the time as it
  stands when it is worked out (a Spiridonov time, a penalty).
- The result is the time from the start to the finish of the last lap ridden; the gap is the
  result minus the table leader's time over the same laps.

## Spiridonov

The coefficient is `(0.02266 a^2 - 1.25437 a + 117.37067) / 100`, `a` this year minus the year of
birth, and 1.0 when the year of birth is not a number. Every crossing time is divided by it and
the rider's additional info shows it to four decimals. With control points the log warns that the
split times will be incorrect.

## Number of Tries

- The laps of a start line are the rider's attempts. Without control points his finish marks
  alternate start, finish; with N control points the finish marks are the starts, points
  1..N-1 the intermediate marks and point N the finishes, and the run stops unless all N streams
  are read.
- A start opens an attempt that ends at the next start. Its finish is the earliest finish mark
  inside that window at least "Minimal lap time" after the start -- without control points, the
  mark paired with the start -- and the penalties of the attempt are added to its time, which a
  time limit caps. An attempt without a finish stays unfinished -- DNF once a
  later start closes it -- and the attempts after it keep their numbers. Disqualification marks
  are no attempt marks but still disqualify.
- The rules ("AttemptRules", JSON): an ordered list of `label`, `attempts`, `attempt_numbers`,
  `sort` (`asc` or `desc`). A rule counts the fastest `attempts` completed attempts among
  `attempt_numbers`, the earlier one winning a tie, and sums them. Riders are compared rule by
  rule: more counted attempts first, then the sum in the rule's direction, then the number. The
  first rule alone gives the printed result and decides who finished; its counted attempts are
  printed bold.
- With no rules (`[]`) every rider's comment holds the legacy rule `N:a,b,...`: the best N of
  the listed attempts. A rider whose comment is not that rule is an ERROR ("invalid
  NumberOfTries format") and counts no attempt.

## Checks

After the protocols are written the log reports:

- riders of one group printed with the same time and counted laps without riding the same
  millisecond (WARNING);
- a number with two crossings closer than "Minimal lap time" -- one crossing recorded twice,
  likely by a second device on the line (ERROR; not in Number of Tries);
- a mark, at the finish or a control point, of a number the start protocol does not have, and a
  number the start protocol has twice (ERROR);
- more crossings than the laps allow (ERROR): laps, one more in Custom Start, twice the
  attempts in Number of Tries without control points;
- with "Check laps difference" and a "Max deviation (%)" p above 0, for a rider with two laps or
  more, a lap longer than his average lap times (1 + p/100) or shorter than it divided by
  (1 + p/100) (ERROR).
