---
name: cycling-site
description: How this app reads from and writes to the cycling website - start lists, timing data, protocol upload/delete, and live stats. Use when working on HTTP sync or the live-stats feature. Contains no secrets.
---

# Cycling-site integration

The site is a REST API configured per race under Settings -> HTTP: a base site URL and
an upload token. The token is a SECRET tied to the competition (found on the competition
detail page when logged in) - never hardcode, log, or commit it. Networking code is in
`app/http_io.py`; UI wiring and worker threads are in `app/main_window.py`.

## Endpoints (base = the configured site URL)

- `GET  /api/v1/start-list/?...`     fetch the merged start list
- `GET  /api/v1/group-times/?...`    fetch group start times
- `GET  /api/v1/finish-times/?...`   fetch finish crossings
- `GET  /api/v1/remote-points/?...`  fetch intermediate control-point crossings
- `POST /api/v1/protocols/upload/`   multipart HTML upload of one protocol (+ token)
- `POST /api/v1/protocols/delete/`   remove a protocol (idempotent)
- `POST /api/v1/live-stats/`         push per-competitor live standings
- `GET  /api/v1/live-stats/{competition_id}/{bib}`  public read for the Garmin field

## Input sources

Each stream (start list / group times / finish times / remote points) has a source:
"Use local data" or "Get data from site". When set to site, the app fetches that stream
and writes it into the local file before generating, so generation always reads from
disk. A failed fetch leaves the local file untouched and generation continues with
whatever is on disk.

## Publishing and editing protocols

Groups and absolute protocols each have an independent HTTP action: Nothing, Upload, or
Delete. Any stored value that is not exactly `Upload` or `Delete` is treated as
`Nothing` (safe default). There is no separate edit call: re-uploading with the same
competition token overwrites the stored protocol; `delete` removes it.

## Live stats (Garmin data field)

When "Send group statistics" / "Send absolute statistics" is on, every regeneration also
POSTs a `bib -> {key: value}` snapshot (place, qty, gap_prev/gap_next/gap_leader, their
per-lap deltas, laps) to `/live-stats/`. The site stores the dict opaquely, so new keys
can be added on this side with no site change. Gap sign is from the reader's point of
view: a rider ahead of you is `+`, a rider behind you is `-`; the delta keeps its own
meaning (`+` grew, `-` shrank).

## Network gotcha

`urlopen(timeout=...)` does NOT bound DNS resolution (`getaddrinfo`). A stuck lookup can
keep an upload worker running indefinitely. The UI must stop and wait its QThread workers
on close (`closeEvent` -> `_stop_workers`), otherwise Qt destroys a still-running QThread
during teardown and aborts the process with "QThread: Destroyed while thread is still
running".
