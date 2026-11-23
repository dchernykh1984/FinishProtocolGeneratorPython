# Eliminator Finals

Written from the code (`app/eliminator.py`, `app/eliminator_output.py`,
`app/eliminator_ladders_editor.py`, `app/main_window.py`) on 2026-11-23. Where the code does not
say why, this file does not guess.

## What a finals run reads

- **The ladder file** ("Eliminator ladders file", `ladders.txt` by default): `group#riders per
  heat#rounds#` per line, one ladder per group. Riders per heat is 2 or 4 and rounds at least 1:
  a line with other values is an ERROR and is skipped, a line without a group is skipped, and a
  second ladder for one group is dropped. A ladder seats
  `2^(rounds - 1) x riders per heat` qualifiers.
- **The start protocol**: field 9 is the rider's qualification place, as the seeding protocol
  writes it ([files.md](files.md)).
- **The group times**: one line per heat start, the heat's name and when it started, as the
  chronometer appends it when the heat is picked from its group list and started.
- **The finish marks**, as in a timed race; `finish` and `nextLap` cross the line.
- Settings for the whole meeting: "Small final", "Seeding" ("Split adjacent seeds (UCI)", or
  "Keep adjacent seeds together"; any other name is the UCI one), "Laps per heat", "Minimal lap
  time" and "Digits after decimal". "Disable DSQ" drops the disqualification marks altogether.
- A ladder file, group times or finish marks file that cannot be read is an ERROR and reads as
  empty, since none exists before the first heat; the start protocol has to be there.

## The ladder

- The last round is the final. A heat sends half its riders -- 2 of 4, 1 of 2 -- up to the heat
  above it, and the small final, ridden in the last round, takes the riders the round before the
  final drops. A ladder of one round, or a meeting without "Small final", has none.
- Heat titles: `1/<n> final <k>` for a round of n heats before the last, then `Final` and `Small
  final`. A heat's name in the chronometer's group list is `<group> - <title>`.
- Seeding: qualification places 1 .. the ladder's seats are spread over the first round so that
  every heat's places add up alike. "Split adjacent seeds (UCI)" parts riders who qualified next
  to each other (sixteen riders: 1-8-9-16, 4-5-12-13, 2-7-10-15, 3-6-11-14, as in the UCI
  regulations); "Keep adjacent seeds together" keeps them in one heat (eight riders: 1-2-7-8,
  3-4-5-6). A place beyond the seats does not ride, and two riders with one place are reported --
  one of them loses his seat.
- **The heat list** `heats.txt`, beside the group protocol, is rewritten on every run: every
  heat's name, ladder by ladder and round by round, the small final before the final -- the order
  a meeting rides them, for the chronometer's group list. A path that names a file of the race is
  refused with an ERROR.

## Scoring a heat

- A heat is scored once the heats that feed it are over. A heat with a start line is scored from
  the marks between its start and the start of the next heat of any ladder; the last heat started
  stays open. It is over when every rider in it has crossed or been disqualified, or once the
  next heat has started.
- A rider finishes a heat when he has crossed the line "Laps per heat" times; a crossing sooner
  than "Minimal lap time" is dropped. Riders are placed as they cross, since nobody still on the
  course can finish ahead of them, and those who placed in the first half go up at once.
- A rider without a finish is DNF once the heat's start is recorded and the heat could be
  scored, and DNS while no start of that heat is recorded. A heat that was ridden and has no
  finish mark at all is an ERROR.
- A disqualification mark inside a heat's window disqualifies in that heat. One that falls in no
  window -- a jury decision stamped after the heat -- goes to the last heat of that rider that had
  started by then, and a heat he rode after it is reported. A disqualified rider has no time; his
  reasons stand in his result cell.
- A heat that cannot eliminate anybody -- at most half its seats taken -- and was never started
  goes through in qualification order with no times; its title gets "(<heat not ridden label>)",
  "not ridden" by default, and the log says so, as a WARNING for the final and the small final. A
  heat that can eliminate and has no start yet stays empty.
- Starts: a heat's first start line counts and a repeat is reported. A heat whose start time
  copies the one another heat was recorded with first is treated as not started.
- Places: the final from 1, the small final carrying on after the final's riders (5th in a ladder
  whose final holds four). Two riders of a heat on the same millisecond share a place. Two printed
  with the same time are an ERROR when it decides who goes on or a medal of the final, a WARNING
  otherwise. Marks no heat took, heats still being ridden and more crossings than laps are
  reported.

## The finals protocol

- A group with qualifiers and no ladder stops the run before anything is written: "No ladder
  for: ... Set riders per heat and rounds for each of them in the Eliminator ladders table, then
  generate again."
- It is written to the group protocol file: the page header ([protocols.md](protocols.md)), per
  group "<group label> <group>" and its ladder, one heat table per round left to right with the
  small final beside the final, then the footer.
- A heat table: the place (a number, DNF, DNS or DSQ), the rider columns that are shown --
  number, name, year of birth, team, city, additional info, qualification place ("Show
  qualification place (Eliminator Finals)", empty when the start line has none) -- and the
  result: the time ridden and the gap to the heat's winner, or a disqualified rider's reasons.
- A finals run writes no absolute protocol and sends no live statistics; an Upload of the
  absolute protocol to the site removes it there instead, and the group protocol's document has
  one ladder section per group ([site-exchange.md](site-exchange.md)).

## The ladders table

On the Main tab: a row per group with riders per heat and rounds (up to 5), saved to the ladder
file on every edit. It can add the start protocol's groups that have no row yet, by name only.
It does not save while the ladder file is another file of the race, and names a group whose
value in the file it cannot show.
