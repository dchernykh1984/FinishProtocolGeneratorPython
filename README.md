# finish-protocol-generator

Tool for generating finish protocols for offline referee events.

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

## Cycling-site integration

The application can upload finish protocols directly to the cycling-site API.

1. Open **Settings -> HTTP** in the application.
2. Enter the site URL (e.g. `https://cycling.codered.cloud`).
3. Enter the upload token - find it on the competition detail page when logged
   in as an organizer or admin.

After generating a protocol, the **Upload** button sends it to
`POST /api/v1/protocols/upload/` as a multipart HTML file with the competition
token. The site stores the protocol and makes it visible on the competition page.

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
| `laps` | Completed vs. required laps, e.g. `"3/7"`. |

Notes:

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
