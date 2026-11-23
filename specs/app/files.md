# The files the generator reads and writes

Written from the code (`app/file_io.py`, `app/models.py`, `app/main_window.py`,
`app/html_writer.py`, `app/config.py`) on 2026-11-23. Where the code does not say why, this
file does not guess.

## Reading

- Every input file is read as UTF-8, or else cp1251, or else Latin-1, and its blank lines are
  skipped. Fields are separated by `#` and read by index; a field the line does not have reads
  as empty.
- A time is `D HH:MM:SS.fff` -- days since 1970-01-01, then the time of day -- or `HH:MM:SS.fff`,
  with any number of decimals or none; the seconds may be left out (`HH:MM`). Empty or `0` is no
  time. A time that cannot be read ends the run with an error ([generator.md](generator.md)).

## The start protocol (`start.txt`)

One line per competitor, as StartProtocolMaker writes it. Fields 0-9 are read; anything after
them is ignored.

| Index | Field | How the generator reads it |
| --- | --- | --- |
| 0 | number | The competitor's id, compared as text; read as a whole number too, for stage riders |
| 1 | name | |
| 2 | group | |
| 3 | laps | Laps, or attempts, to ride; empty, 0 or not a number is 1 |
| 4 | stages | With N > 1 the marks of the numbers `number` .. `number + N - 1` all count for the line; empty, 0 or not a number is 1 |
| 5 | year of birth | Printed; the age of the Spiridonov coefficient |
| 6 | team | |
| 7 | city | |
| 8 | comment | The "Additional info" column; `N:a,b,...` is a legacy Number of Tries rule |
| 9 | time shift | The start delay after the group's start; in Eliminator Finals the qualification place, a whole number |

## The group times (`groups.txt`)

- `group#time#` per line, as the chronometer appends it when a group starts.
- A group's first line is its start. Every line gives the protocol a table, in the order of the
  file, so a group listed twice is printed twice. The groups of the start protocol that the file
  does not list follow, with no start time.
- In Eliminator Finals a line is a heat ([eliminator-finals.md](eliminator-finals.md)).

## The finish marks (`results.txt`) and the control points

- `number#time#action#` per mark, as the chronometers write it. A fourth field that reads as a
  number is a penalty in seconds.
- Actions: `finish` and `nextLap` cross the line, `nextStage` is a stage change, `DSQ` or
  `DSQ: <reason>` disqualifies. In the timed race types every mark that is not a disqualification
  counts as a crossing of the line ([scoring.md](scoring.md)).
- Control points: with "Control points" N > 0 and a "Path prefix" folder, point n is read from
  `<folder>/results_<n>.txt`, n = 1..N, in the same format.
- The start check list, when "Use start check list" is ticked, is a file of the same format. A
  positional race info file does not store its path: loading one that has the check list on
  sets `temp/results_start.txt`, where the C++ generator kept it.

## The race info file (`fpg_info.txt`)

The C++ generator's positional format, extended at the end. One field per physical line; a tag
line says that the optional block after it is present, and a block whose tag is missing reads
as switched off, with its label empty.

1. Thirteen fixed lines: sponsor, race name, date, place, weather, main referee, additional
   referee, organizer, track conditions, minimal lap time, time limit, digits after the decimal
   point, race type.
2. The C++ blocks, in this order: `Info` + label; `RefreshProtocol` + interval in milliseconds;
   then always the referee and secretary labels; `ID`, `Name`, `Age`, `Team`, `City`, each +
   label; `Laps` with `Lap Name` + label, `Lap Finish Info` + label, `Lap Finish`, `Hide Empty
   Columns`; `Buttons`; `All Buttons`; `UploadGroups`; `UploadAbsolute`; `SendGroupStatistics`;
   `SendAbsoluteStatistics`; then always the four FTP actions (start list, group times, finish
   times, control points) and the FTP address, login and password; `Finish` with `Time
   Difference` and `Number Of Laps Finished`; `Group`, `Place`, `TimeShift`, each + label;
   `Stratch`; `Print DNF`; `Print DNS`; `Print DSQ`; then always the five file paths (start
   protocol, group times, finish times, group protocol, absolute protocol), the control point
   folder and the control point count; `Disable DNF`; `Disable DSQ`; `Use File Logger`; `Use
   Interface Logger`; `Err and Wrn only`; `Laps Difference Erroros` + percentage;
   `UseStartCheckList` + check list action + registration period; then always the bottom text,
   the last field the C++ generator reads. `Stratch` and `Erroros` are the C++ spellings.
3. Tag and value pairs only this generator reads, in this order: `FinishTimeLabel`,
   `TimeDifferenceLabel`, `NFinishedLapsLabel` (each written when its column is on),
   `TemplateFile`, `ButtonsLabel` and `AllButtonsLabel` (these two when their buttons are on),
   `LapRankLabel`, `LapFinishRankLabel`, `WeatherLabel`, `TrackLabel`, `OrganizerLabel`,
   `OverallResultsLabel`, `HttpSiteUrl`, `HttpUploadToken`, `StartListSource`,
   `GroupTimesSource`, `FinishTimesSource`, `RemotePointsSource`, `HttpIsLive`,
   `HttpStageLabel`, `HttpGroupsAction`, `HttpAbsoluteAction`, `PackGapSeconds`,
   `AttemptRules`, `HttpProtocolFormat`, `ProtocolLanguage`, `WriteSeedingProtocol`,
   `SeedingProtocolFile`, `HttpSection`, `EliminatorLadderFile`, `NotRiddenLabel`,
   `EliminatorSmallFinal`, `EliminatorSeeding`, `EliminatorLaps`, `ShowQualificationPlace`,
   `QualificationPlaceLabel`.

- Tags are read in the order they are written and a version stops at the first one it does not
  know, so a new tag goes last. The reader still takes the retired `HttpCompetitionId` and
  `HttpProtocolType` (and drops their values) and `UploadHttpGroups` / `UploadHttpAbsolute`,
  which migrate to the per-protocol actions: neither on is Nothing for both, otherwise the one on
  is Upload and the other Delete.
- The C++ names of the race types ("Mass Start or Splitted Start", and the same "with
  Spiridonov's coefficients") are read as Mass/Splitted and its Spiridonov variant; the retired
  "Eliminator Qualification" becomes Mass/Splitted with the seeding protocol on.
- The file is written as UTF-8 with a line break after every field; a line break inside a value
  is folded into a space, on the way into the field and again when the file is written.
- **A damaged file.** The race type and the four FTP actions take known values only, so another
  value there means the lines no longer line up -- most likely a value that once held a line
  break. Loading such a file shows "Race info file damaged" with the fields that are off, and
  saving over it asks first ("Overwrite damaged race info file?", No by default).
- **The key=value format.** A file whose first non-blank line is `# FPG Race Info` holds
  `Key=Value` lines; an `\n` in a value is a line break, folded on load, except in
  `AttemptRules`. It is read and never written: a save writes the positional format.

## The styles template (`template.html`)

Eleven lines of HTML, in the C++ order: table style, header row style, even row style, odd row
style, group name style, additional text styles (header row, then rows), top text style,
additional info styles (header row, then rows), and a style sheet for the page. Missing lines are
empty; a template that cannot be read gives the built-in styles.

## What it writes

- The group and absolute protocols: [protocols.md](protocols.md). The finals protocol, the heat
  list and the ladder file: [eliminator-finals.md](eliminator-finals.md). The streams fetched
  into their local files: [site-exchange.md](site-exchange.md).
- **The seeding protocol**, when "Seeding protocol for the finals" is ticked and the race type is
  not Eliminator Finals: a start protocol of the finishers who were not disqualified.
  - Group by group for every line of the group times file, so a group listed twice is written
    twice, then the start protocol's groups the file does not list; within a group in finishing
    order.
  - Field 9 is the place in the group: 1, 2, 3, a dead heat not shared. Fields 0-8 are as the
    generator read them: laps and stages that were empty, 0 or not a number come out as 1, and in
    Spiridonov the comment is the coefficient.
  - It goes to its own path, or beside the group protocol as `<group protocol>.txt` when that is
    empty, in UTF-8. A path that names a file of the race (start protocol, group times, finish
    times, start check list, group or absolute protocol, styles template, ladder file) is refused
    with an ERROR, and the protocols are written all the same; a folder that is not there is
    made.
- **The log file** `temp/fpg<N>.txt`, N the first number not yet used, when "Write log to file"
  is on.
- **`fpg_info.txt`** on exit, next to the program; "Save Race Info to file..." writes the same
  format wherever it is pointed.
