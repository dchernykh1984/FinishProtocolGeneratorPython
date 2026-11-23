# What the protocols show

Written from the code (`app/html_writer.py`, `app/protocol_rows.py`, `app/protocol_document.py`)
on 2026-11-23. Where the code does not say why, this file does not guess. The Eliminator Finals
protocol is in [eliminator-finals.md](eliminator-finals.md).

## The page

- HTML in UTF-8, titled "Protocol <race name>". At the top: the sponsor as written (HTML
  allowed), the race name, "<date>, <place>" when both are set, "<track label>: <track
  conditions>" and "<weather label>: <weather>", each only when set.
- At the bottom, right-aligned and each only when set: "<organizer label>: <organizer>",
  "<referee label>: <main referee>", "<secretary label>: <additional referee>"; then the bottom
  text as written.
- The styles come from the styles template ([files.md](files.md)); "Stretch table to page width"
  widens the tables to the page.

## The group protocol (`gr.html`)

- A table per line of the group times file ([files.md](files.md)), headed "<group label>
  <group>", with that group's riders in the order of [scoring.md](scoring.md).
- Columns, each behind its "Show ..." setting and headed by its label, in this order: place,
  number, name, year of birth, team, city, one column per lap, the result, additional info,
  start time.
  - **Place**: the place, or DNF, DNS, DSQ.
  - **Number**: a line of N stages lists all N numbers, one under the other.
  - **Lap** "<lap label> <n>", with the lap additional info label under it when "Show lap finish
    cumulative time" is on: the lap's time; for a stage line the number that rode it, in
    brackets; with that setting the time since the start, in brackets. A lap in progress is
    empty, or `UNKNOWN` once a control point of it is passed.
  - **Result**: the time; the gap to the table's leader in brackets ("Show time difference");
    the laps ridden in brackets ("Show number of finished laps"). A disqualified rider's
    reasons take its place, one per line.
  - **Start time**: the start delay; in Custom Start and Number of Tries the first mark with its
    date, or `NOT STARTED`.
- Up to two more rows per rider sit under the lap columns, so they too need "Show lap times".
  With "Show lap stats button": each completed
  lap's gap to the fastest rider of the group on that lap (of everyone, in the absolute
  protocol) and its rank there, bold for the fastest, and
  with "Show lap finish cumulative time" the same for the time since the start. With control
  points: one cell per segment of each lap -- start to point 1, ..., last point to the finish --
  holding its time, `ERR` when the point before it was missed, or `UNKNOWN` when its own point
  was missed on a completed lap or a lap that has passed another point.
- Lap columns, which need "Show lap times": with "Hide empty lap columns" as many as anyone of
  the table has ridden -- in a group table a lap in progress counts once a control point of it
  is passed -- otherwise as many as the first rider of the table with at least one lap has. A
  table has none when
  its riders have one lap, the finish time is shown and there are no control points.
- "Show intermediate splits button" (with control points) and "Show lap stats button", with
  "Show lap times", put a button above the tables that shows and hides those rows; their labels
  default to "Show/Hide CP Splits By Lap" and "Show/Hide Additional Statistics By Lap".

## Number of Tries in a table

- A lap column is an attempt. The attempts the first rule counts are bold, and each attempt's
  penalties follow its time as `<action>:<seconds>sec`. A closed attempt without a finish says
  `DNF`.

## The absolute protocol (`abs.html`)

- One table, headed by "Absolute protocol title" ("Overall results" by default), of every rider
  in one order. The same columns as a group table with the group after the year of birth, which
  gives a finisher's place in his group in brackets; as many lap columns as the most laps anyone
  has, or with "Hide empty lap columns" as the most laps anyone has ridden.
- Eliminator Finals writes none.

## The site document

- When protocols are sent to the site as "HTML + Data" or "Data", each one is also built as a
  document of the site's schema 1 (`tests/fixtures/protocol-document-v1.json` is a copy of the
  site's): the same tables, columns and cells as the HTML, from the same calculations in
  `app/protocol_rows.py`.
- It holds the generator's name and version, the race name as its title, the protocol language
  when it is a code the site understands (two or three letters, optionally a dash and two to
  eight letters or digits), the header and footer lines, the groups, the toggles of the two
  buttons, and the tables. A group's id is its name; a name longer than 100 characters, or one
  ending like a hashed id, becomes its first characters, `~` and eight hex digits of its SHA-1.
  Each column carries a priority that tells a narrow screen what it may hide.
- A document is built only when it will be sent -- a site URL and an Upload action -- and a
  build that fails is a WARNING: the HTML goes alone ([site-exchange.md](site-exchange.md)).
