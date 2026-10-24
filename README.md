# finish-protocol-generator

Tool for generating finish protocols for offline referee events.

## Download a ready-made app

Every release ships portable builds, so there is nothing to install and no
Python, uv or git needed. Pick the file for your platform from the
[latest release](https://github.com/dchernykh1984/FinishProtocolGeneratorPython/releases/latest):

| Platform | File |
| --- | --- |
| Windows (Intel/AMD) | `FinishProtocolGenerator-windows-x64.exe` |
| Windows (ARM) | `FinishProtocolGenerator-windows-arm64.exe` |
| macOS (Apple Silicon) | `FinishProtocolGenerator-macos-arm64.zip` |
| Linux (Intel/AMD) | `FinishProtocolGenerator-linux-x86_64` |
| Linux (ARM64) | `FinishProtocolGenerator-linux-aarch64` |

The builds are not code-signed, so every system needs a one-off nudge before the
first launch. Each step below is done once per download, not on every start.

### macOS

Only Apple Silicon (M1 and newer) is supported - there is no Intel build.

Unpack the archive, then clear the quarantine flag that macOS puts on downloaded
files:

```bash
xattr -dr com.apple.quarantine "/path/to/FinishProtocolGenerator.app"
```

After that the app opens with a normal double-click. Without it macOS refuses to
start the app, because it is unsigned.

The flag stays cleared. Copying or moving the app on the same Mac keeps it clear,
so there is no need to repeat this for every copy. It only comes back when the app
arrives from outside again: a fresh download, AirDrop, or unpacking a
newly downloaded archive.

Rather not use a terminal? Ctrl-click the app, choose **Open**, then **Open**
again in the dialog. macOS 15 Sequoia dropped that shortcut - there, go to System
Settings -> Privacy & Security, scroll down to the notice about the blocked app
and press **Open Anyway**.

### Windows

Run the `.exe` directly. SmartScreen warns that the publisher is unknown: choose
**More info**, then **Run anyway**.

### Linux

Make the file executable and run it:

```bash
chmod +x FinishProtocolGenerator-linux-x86_64
./FinishProtocolGenerator-linux-x86_64
```

This is a GUI application, so it needs a graphical session. If it fails to start
with an error about missing Qt libraries, install them:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libxcb-cursor0
```

### Where to keep it

The program reads and writes its files (`fpg_info.txt` and `temp/`) **next to itself**, so give
it a folder of its own rather than a shared downloads directory. On macOS the
files land next to the `.app` bundle, in the folder that contains it.

This is also how you run several events side by side: copy the folder per event,
and each copy keeps its own data. A symlink or a Finder alias will not work for
that - it resolves back to the original, so every "copy" would end up sharing one
set of files. Use real copies.


## Setup

### 1. Download the project

Install Git if you don't have it:

- **macOS:** `brew install git`
- **Linux (Ubuntu / Debian):** `sudo apt install git`
- **Windows:** download from [git-scm.com](https://git-scm.com/downloads) and run the installer

Then clone the repository:

```bash
git clone https://github.com/dchernykh1984/FinishProtocolGeneratorPython.git
cd FinishProtocolGeneratorPython
```

All subsequent commands should be run from the `FinishProtocolGeneratorPython` folder.

### 2. Install Python 3.14

This project requires **Python 3.14**; `uv` installs a matching interpreter automatically, but you can also install it yourself as shown below.

**macOS**

```bash
brew install python@3.14
```

If you don't have Homebrew yet, install it first from [brew.sh](https://brew.sh).

**Linux (Ubuntu / Debian)**

The system `python3` package is usually not 3.14. Install it via the deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14 python3.14-venv
```

**Windows**

Download the **Python 3.14** installer from [python.org/downloads](https://www.python.org/downloads/) and run it. On the first screen, check **"Add Python to PATH"** before clicking Install.

Verify the installation in a terminal:

- **macOS / Linux:** `python3.14 --version`
- **Windows:** `py -3.14 --version`

The output should start with `Python 3.14`.

### 3. Install uv

**macOS / Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows**

Open **PowerShell** and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal afterwards so `uv` is on your `PATH`.

### 4. Create virtual environment and install dependencies

```bash
uv sync
```

### 5. Set up pre-commit hooks

```bash
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

After that pre-commit hooks will run automatically on every commit.

To run all checks manually across all files:

```bash
uv run pre-commit run --all-files
```

## Running the application

```bash
uv run python -m app.main
```

> **Note:** use `-m app.main`, not `python app/main.py`. The `-m` flag adds the
> project root to `sys.path` so that the `app` package is importable.

## Number of Tries

Select **Number of Tries** on the Main tab to show the scoring-rule editor below
**Race type**. Rules apply to the whole event. The numeric lap count in the start
protocol remains the number of attempts available to each competitor.

Each rule has a descriptive label, the number of best attempts to sum, eligible
attempt numbers (comma-separated, starting at 1), and an `asc` or `desc` sort order.
The first rule defines the result. Further rules only break ties, in list order;
the final tie-break is the competitor number. `desc` reverses the comparison, but
still selects the fastest eligible attempts. Missing results rank after completed
results in either direction. A competitor has a result when enough eligible
attempts for the first rule are complete, even if another attempt was not finished.
Time gaps follow the first rule's sort direction, so a gap to the competitor ahead
stays positive for both `asc` and `desc`.

For example, the best of attempts 2 and 3, with reverse qualification time as a
tie-break, is saved as one JSON line under the `AttemptRules` config tag:

```json
[{"label":"Result","attempts":1,"attempt_numbers":[2,3],"sort":"asc"},{"label":"Qualification","attempts":1,"attempt_numbers":[1],"sort":"desc"}]
```

Before a counted result exists, qualification orders the competitors. Once attempt
2 produces different results, the first rule determines their order. This does not
fix the qualification order for all later starts. Only attempts actually included
in the first rule's current result are printed in bold; equal times select the
earlier attempt. An empty rule list keeps legacy `N:1,2,3` rules in Additional info.

Invalid or unfinished rule edits block generation and explicit config saves. On
exit, choose to stay and correct the edits or discard them and save the last valid
rules along with all other settings. If the loaded race has no valid rules, exit
uses an empty list; it never restores rules from a previously loaded race.

With **Control points = 0**, one stream alternates start, finish, start, finish.
If **Minimal time for lap** rejects a finish, that attempt stays unfinished and the
next pair keeps its number. This also applies to legacy Additional info rules;
older versions could incorrectly consume the next start as the rejected finish.
With **Control points = N > 0**, stream 0 contains starts, streams 1 through N-1
contain intermediate crossings, and stream N contains finishes. Every start opens
an attempt window ending at the next start; the last window stays open. The first
valid finish in that window completes the attempt. Intermediate crossings are
matched in point order inside the window and before the finish. Missing crossings
do not invalidate an available finish time; unknown segments are shown as
`UNKNOWN` or `ERR`. A missing finish keeps that attempt's number, so later attempts
are never shifted into its place. Closed unfinished attempts show `DNF` in their
own columns. Enable **Show lap times** to see attempts and intermediate segments.

## Cycling-site integration

The application can upload finish protocols directly to the cycling-site API.

1. Open **Settings -> HTTP** in the application.
2. Enter the site URL (e.g. `https://cycling.codered.cloud`).
3. Enter the upload token - find it on the competition detail page when logged
   in as an organizer or admin.

After generating a protocol, the **Upload** action sends it to
`POST /api/v1/protocols/upload/` with the competition token. **Send protocols to the
site as** chooses what goes: `HTML + Data` (default) sends the HTML file and the
protocol as structured data, which the site shows in its own look on phones and
desktops; `HTML` sends the file only, as before; `Data` sends the data only. Local HTML
files and their FTP upload do not change. **Protocol language** tells the site which
language the protocol's labels are in.

The data leaves out what the site's event page already shows -- the date, the place, the
course and the sponsors' logos -- and keeps the weather above the tables and the officials
below them. Each column carries how much it matters, so a screen too narrow for all of them
drops extra info first, then the year of birth, city, team, laps and number, and the start
delay last; a lap's statistics sit under its time behind their switch, as in the HTML. Upload
data only to a site that understands it (cycling-site after its #375): an older site refuses
it and the HTML is published instead.

## Live race statistics (for the Garmin data field)

When **Send group statistics** and/or **Send absolute statistics** are enabled in
**Settings -> HTTP**, every protocol regeneration also pushes a per-competitor live-standings
snapshot to `POST /api/v1/live-stats/`. A Garmin Connect IQ data field then reads one rider's
stats publicly via `GET /api/v1/live-stats/{competition_id}/{bib}` and shows them mid-race.

Each competitor's snapshot is a plain `key -> string` dictionary. Everything -- **including the
place** -- is derived from **lap-finish crossings only**, so a control-point timekeeper who
misses a mark can never move a rider's place or gap. Deliberate judge decisions taken at a
control point still count, because they do not depend on a crossing being seen: a **time
penalty** is folded into the lap-finish times, and a **DSQ** mark disqualifies the rider.
(The printed/online protocol keeps its own ordering, which does use control-point progress as
a tiebreak -- only the data broadcast to the bike computer ignores it.)
A key is **omitted** when it does not apply -- the watch
simply shows nothing for a missing key. Keys come in `_group` / `_abs` pairs (within the rider's
group vs. the whole race), plus `laps`.

| Field | Meaning |
|-------|---------|
| `place_group` / `place_abs` | Current place in the group / overall, as a number, or `"DSQ"` for a disqualified rider (no `DNF`/`DNS` labels; those still get a number). |
| `qty_group` / `qty_abs` | Number of competitors in the group / whole race, counting everyone with a bib (incl. DSQ, DNS, DNF). |
| `gap_prev_group` / `gap_prev_abs` | Time behind the rider one place ahead, positive because they are ahead of you, e.g. `"+0:12"`. Omitted for the leader. |
| `gap_next_group` / `gap_next_abs` | Time the rider one place behind trails you, negative because they are behind you, e.g. `"-0:45"`. Omitted for the last competitor. |
| `gap_leader_group` / `gap_leader_abs` | Time behind the group / overall leader, e.g. `"+2:05"`. Omitted for the leader. |
| `gap_prev_group_delta` / `gap_prev_abs_delta` | How the gap to the rider ahead changed over your last lap: `"+..."` it grew, `"-..."` it shrank. Omitted with fewer than two shared laps. |
| `gap_next_group_delta` / `gap_next_abs_delta` | How the gap to the rider behind changed over the last lap (`+` grew, `-` shrank). |
| `gap_leader_group_delta` / `gap_leader_abs_delta` | How the gap to the leader changed over the last lap (`+` grew, `-` shrank). |
| `gap_prev_pack_abs` / `gap_next_pack_abs` | Signed time to the nearest member of the distinct participant pack ahead / behind. Your own pack is skipped. |
| `qty_prev_pack_abs` / `qty_next_pack_abs` | Number of competitors in that neighbouring pack, including a pack of one. |
| `laps` | Completed vs. required laps, e.g. `"3/7"`. |

Notes:

- **Participant packs are absolute statistics only.** The HTTP tab's **Participant pack
  max gap (seconds)** setting defaults to **10** and is saved with race info. A pack is
  a chain of consecutive ranked riders whose unrounded common-lap gaps are at most this
  threshold, regardless of the total spread or number of riders. Zero joins only ties.
  DSQ riders and riders without a measured lap are excluded. Missing neighbouring packs
  or uncomputable/reversed common-lap gaps omit both the gap and size keys.
- **All values are strings.** Times are `"M:SS"` (or `"H:MM:SS"` past an hour), always
  carrying a leading sign: a rider ahead of you is `+`, a rider behind you is `-`.
- **Gaps and their deltas use lap-finish crossings.** A gap is measured at the last lap **both**
  riders finished, so it stays a real time even when riders are a lap apart. A delta is that gap
  now minus the gap one lap earlier.
- **DSQ** riders show `place_* = "DSQ"`, keep `qty_*` and `laps`, and have no gaps.
- The site stores the dictionary **opaquely** (it does not know the individual keys), so new
  stats can be added here without any site change.

## Contributing

Before requesting a review, make sure the CI pipeline passes on your pull request. Once the pipeline is green, request a review from [@dchernykh1984](https://github.com/dchernykh1984).
