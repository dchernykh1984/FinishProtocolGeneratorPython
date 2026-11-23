# The generator as it works today

Written from the code (`app/main_window.py`, `app/paths.py`, `app/time_trial.py`,
`app/time_trial_window.py`) on 2026-11-23. Where the code does not say why, this file does not
guess. What a run reads and writes is in [files.md](files.md), how it scores in
[scoring.md](scoring.md), what it prints in [protocols.md](protocols.md), the finals in
[eliminator-finals.md](eliminator-finals.md) and the network in
[site-exchange.md](site-exchange.md).

## Where it keeps its files

- The program reads and writes next to itself: a portable build uses the folder that holds the
  executable -- on macOS the folder that holds the `.app` -- and a development run uses the
  working directory (`app/paths.py`). A relative path in the settings hangs off that folder, so
  a copy of the folder per event keeps each event's files apart.
- At start the program loads `fpg_info.txt` from that folder when there is one. On exit it saves
  the settings back to it.

## The window

- Tabs: **Main** (race type, the input and output files, control points, the start check list,
  the settings of Number of Tries and of the finals, Generate Protocol, Open Time Trial Window),
  **Race Info** (the texts of the protocol's header and footer, digits after the decimal point,
  loading and saving a race info file), **Columns**, **Options**, **FTP**, **HTTP** and **Log**.
- A text field bound to a setting folds a line break pasted into it into a space as it is typed
  and shows what will be stored: a value of the race info file stays on one line.
- The attempt rule editor shows below Race type, for Number of Tries only.

## A run

**Generate Protocol** starts a run, and so does the auto-refresh timer ("Auto-refresh protocol",
every "Interval (sec)"). A run does not start while another run or a download is still going,
nor in Number of Tries while the attempt rules are invalid, nor when an FTP download action is
set and the FTP address is empty; the last two say why in a dialog.

1. The HTML styles template is loaded -- a missing or unreadable one gives the built-in styles
   -- the log is cleared, and with "Write log to file" a new file `temp/fpg<N>.txt` is started.
2. **Downloads**, when a stream's source is the site or an FTP download action is set for it:
   the site's streams first, then the FTP downloads ([site-exchange.md](site-exchange.md)). A
   stream set to both takes the site's data and logs an ERROR about the conflict. A failed
   download logs an ERROR, the run ends the step with "WARNING: some downloads failed;
   continuing with local files." and goes on.
3. **Generation**: the input files are read ([files.md](files.md)), the protocol is worked out
   and sorted ([scoring.md](scoring.md)), the group protocol -- with the seeding protocol when
   it is on -- and the absolute protocol are written ([protocols.md](protocols.md)), the checks
   are logged and the protocols are published. Eliminator Finals runs steps of its own
   ([eliminator-finals.md](eliminator-finals.md)).
4. The log ends with "Done." or with the errors of the publishing.

An exception in step 3 -- an input file that does not exist, among others -- ends the run with
an ERROR in the log and a dialog. Every other failure is a line in the log, but for the fetches
from the site that are not caught ([site-exchange.md](site-exchange.md)).

## The log

- A run's messages go to the window ("Show log in window") and to the log file ("Write log to
  file"); "Errors and warnings only" keeps the lines that contain "error" or "warning", in any
  case.
- "Search" selects the next line of the window's log that contains the text, without regard to
  case, and says "No matches found." when there is none.

## The start board

- "Open Time Trial Window" opens the start board, a separate window kept until exit: the clock,
  the countdown to the next start, the next rider and the one after, and the rider who started
  last, scaled to the window. Its captions are in Russian.
- Every run but a finals one rebuilds its schedule as soon as the start protocol and the group
  times are read, so a later failure still refreshes it: a rider starts at his group's start
  time plus his start delay, earliest first and equal times by number; a rider whose group has
  no start time is left out.

## Exit

- "Are you sure to exit?" In Number of Tries with invalid rule edits, the question says they
  will be discarded: the last valid rules, or none, are kept.
- On Yes the start board closes, the auto-refresh timer stops, a running download and a running
  generation each get 5 seconds to end, one after the other, before they are terminated, and the
  settings are saved to `fpg_info.txt` next to the program.
