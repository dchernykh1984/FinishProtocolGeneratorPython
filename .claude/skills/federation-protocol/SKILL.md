---
name: federation-protocol
description: Build a cycling federation's results protocol PDF - final places per group plus the qualification - from this generator's qualification and Eliminator Finals runs, in the layout of the federation's own template; ordering rules, layout, data mapping and how to verify every field.
---

# Federation results protocol (PDF)

A federation wants an event's results on its own paper: a scanned template protocol
from an earlier event shows the layout. This skill turns the generator's two runs of
the day - a qualification (Custom Start time trial) and the Eliminator Finals - into
that PDF, then reads the PDF back and checks every field against the race data.

The scripts live once, in `.claude/skills/federation-protocol/scripts/`.

## Flow

1. Get the template protocol and the generator folders of both runs (the folders
   holding each run's `fpg_info.txt` and the group protocol it wrote).
2. If the protocols were published, make sure the local files are the published ones
   (see "Published copy" below).
3. `uv run python .claude/skills/federation-protocol/scripts/collect.py QUAL_DIR FINALS_DIR data.json`
   - It stops rather than guess when a run's `fpg_info.txt` is in the old key=value
     format or does not line up; a protocol has no header row its labels match; the
     runs disagree on the groups (one renamed between them, or a group with no
     finals: ask how to place it) or a finalist is missing from his group's
     qualification; scoring the marks again does not give every published time.
4. Copy `event-template.json` outside the repo and fill it in: the words come from
   the template and the organizer, never from guesses (see "Ask, do not invent").
5. `uv run --with reportlab==4.4.4 python .claude/skills/federation-protocol/scripts/render.py data.json event.json OUT_DIR`
6. `uv run --with pdfplumber==0.11.7 python .claude/skills/federation-protocol/scripts/verify.py data.json event.json OUT_DIR`
   - Exit 0 or the PDF is not done. Besides the places, it checks that every rider
     of a group is listed exactly once - which holds whatever the rules say, so a
     rule wrong in both implementations cannot drop a rider unseen.
   - After changing a rule, plant an error and watch it fail: a check that cannot
     fail proves nothing.
7. Look at every page (`pdftoppm -r 70 -png FILE page`): wrapped cells, a table
   split oddly, signatures alone on a page.
8. When the organizer asks for a change, keep the delivered files and write the next
   version beside them (`... v2.pdf`, `... v3.pdf`).

## Layout (the federation's template)

- A4, Times New Roman, no signatures or stamps drawn.
- Letterhead lines, bold and centered; the title, bold and centered; then one line
  with the date (`DD.MM.YYYY`) at the left and the place at the right, both bold.
- One table of final places per group, six columns and no column headings: place,
  number, name, birth date (`DD.MM.YYYY`), team, coach. The first row is grey and
  holds only the group's name, in the third cell.
- The judge and the secretary under the last table: caption at the left, name at
  the right, bold.
- A new page with the qualification heading, then one table - the same grey group
  rows, stacked without a gap - of place, number, name, birth date, time, coach; the
  signatures again.
- Groups youngest first, boys before girls, juniors last, as on the template. One
  event may be printed as several protocols (`parts`), each with its own title and
  groups - only when the organizer asks for it.
- The title follows the template's pattern: what the event is, the discipline, then
  "among" the categories with their birth years.

## Final places (one group)

In order, numbered as shown; `standings.py` is the implementation and
`tests/test_federation_standings.py` pins every rule.

1. Finishers of the final, in the order they finished, then finishers of the small
   final - numbered straight on. A rider of the final who did not finish lets the
   small final's winner move up (1, 2, 3, 4, 5, ...). Riders a heat placed equal keep
   their shared place, and the next rider takes his own count: 1, 2, 2, 4.
2. A final or small final that was not held - every rider in it DNS, the heat never
   started - or a meeting that rides no small final at all: the riders it held, or
   would have held (the semi-finalists who finished and did not go through), by
   qualification place, straight on. They did not fail to start a heat that never
   ran, so they are not DNS. A heat that started and that nobody finished was held:
   its riders are DNF and fall under rule 3. A heat the generator prints as not
   ridden already places its riders in qualification order - the same thing.
3. Everyone who did not finish or did not start a heat of the finals (semi-final,
   final or small final - the chronometer cannot tell the two apart there) takes
   the last place a finalist can take: 8 in a ladder of 8, 4 in a final of 4,
   shared, in qualification order. Places in between stay empty (1, 2, 3, 4, 5, 8, 8).
4. Riders who did not make the finals: straight after the last place a finalist
   took, in qualification order. A disqualified finalist frees his place: 1-7, then
   the first non-finalist is 8th.
5. Riders with no qualification result: DNF, then DNS, in the place column.
6. Disqualified riders, in a heat or in the qualification: DSQ, always last.

Ladders deeper than semi-finals (`1/4 final` and earlier) are refused: no rule places
the riders who went out there yet, so ask the organizer rather than guess.

Compared with UCI 4.2.12 (XCE final classification): final, then small final, then
DNF/DNS of the semi-finals; a DNF/DNS in the first round of the main event and a DSQ
are listed without a place; riders after a DSQ move up within their own phase only;
DNF ranks before DNS, several of them by number (in UCI the main-event numbers follow
the qualification). The federation differs on purpose: every finals DNF/DNS shares the
last finals place, and riders who did not qualify are listed - UCI leaves them out.
UCI does not cover a small final that was not held.

## Qualification table

As the published qualification protocol: its places and order, DNF and DNS at the end
with the mark in the place column. Places differ whenever the recorded times differ
at the thousandth, so two riders can show the same hundredths and different places.

## Data mapping

- Team and coach: the generator's team field split at its first `" - "`.
- Birth date: the generator's additional info (`YYYY-MM-DD`) as `DD.MM.YYYY`;
  anything else is printed as it stands.
- Time: `M:SS:hh` (`0:41:08`). The published protocol may print tenths only, so
  `collect.py` scores the qualification marks again with the generator's own
  calculator and rounds with its `format_time` - a half goes to the even digit, on
  the recorded millisecond - and refuses to go on if that scoring does not
  reproduce every published time at the published precision. It carries over only
  the timing settings (race type, minimal lap, time limit, digits), so a run that
  used a start check list or switched DNF off is reported, not silently re-scored.
- Columns are found by their headings, through the labels in each run's
  `fpg_info.txt`; a setting the file has no line for reads as the generator's default.
- Group names: as in the data; `group_titles` maps one to the template's name for it.
- `corrections`: substring fixes applied to names, teams and coaches in the PDF only,
  never to the race data - and only those the organizer approved. Two coaches with one
  surname and different initials can be two people.

## Ask, do not invent

Collect every open point in one numbered plain-text message the user can forward to
the organizer, each with the riders it affects by number and name. Typical ones: the
title wording; the letterhead and the place line; who signs as judge and secretary;
whether the event is split into separate protocols, and how; a rule the list above
does not settle; any correction to names or coaches. Short questions read better
than long ones - one line each when the user asks for it.

## Published copy

The site serves a protocol only for an approved, visible event the reader may see,
so anonymous requests get 404 - work from the local files then. Its link carries
`?v=<file_hash>`: `sha256(html)` for an HTML-only upload, otherwise
`sha256(b"html\0" + html + b"\0document\0" + document)` where `document` is the JSON
the generator sent, `json.dumps(doc, ensure_ascii=False).encode()`. Rebuilding that
document from a copy of the run and matching the hash proves the local files are the
published ones byte for byte.

## Gotchas

- `fpg_info.txt` holds the site's upload token: read it in memory with
  `app.file_io.load_config_file`, never copy it or print it.
- The repository is ASCII only. The filled-in event file has Cyrillic, so it lives
  outside the repository (the race folder or `tmp/`); the template has placeholders.
- The font must carry the Kazakh letters names use (U+049A, U+04AF, U+04D9, U+04B1,
  U+04A3). Times New Roman does; `render.py` falls back to Liberation Serif.
- A cell that wraps reads back as two words: a place mark split into "DN" / "Q" is a
  layout bug, and `verify.py` reports it. Column widths are measured, not guessed.
- Each group's table is kept together on one page, and the signatures stay with the
  last table.
