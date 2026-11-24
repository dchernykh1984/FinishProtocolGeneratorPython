# The cycling site and FTP

Written from the code (`app/http_io.py`, `app/ftp_io.py`, `app/live_stats.py`,
`app/main_window.py`, `app/config.py`) on 2026-11-23. Where the code does not say why, this file
does not guess. A run always builds its protocols from the local files
([generator.md](generator.md)); this is how those files are fetched and the protocols published.

## Settings

- HTTP tab: "Site URL" and "Upload token" (shown masked; the competition's secret), a source per
  stream -- start list, group times, finish times, remote points: "Use local data" or "Get data
  from site" -- an action per protocol after a run -- "Nothing", "Upload" or "Delete" -- "Upload
  as live (polling active on site)", "Stage label (optional)", "Protocol section on the site"
  (1, the event's own, by default), "Send protocols to the site as" ("HTML + Data", "HTML",
  "Data"), "Protocol language", the two live statistics switches and "Participant pack max gap
  (seconds)".
- A stored action or format that is not one of the known values reads as "Nothing" or as "HTML +
  Data", and a section outside 1 .. 2147483647 as 1.

## Fetching a stream

- `GET <site>/api/v1/start-list/?competition_token=<token>`, and likewise `group-times`,
  `finish-times` and `remote-points`, with a 10 second timeout. The answer lists `devices`, each
  with its `items` -- the lines that device uploaded -- and the lines are joined in the order
  the site lists the devices. `remote-points` lists `points`, each a `point_number` with its
  `items`.
- The lines replace the stream's local file, in UTF-8 with a line break after each. Point n goes
  to `<control point folder>/results_<n>.txt` for n = 1 .. the control point count, a point the
  site does not list as an empty file; with no count or no folder the points are skipped.
- The log says why and the local file stays as it was when there is no site URL or token, the
  URL does not start with `http://` or `https://`, the site cannot be reached or answers with an
  HTTP error, does not answer within the 10 seconds or drops the connection after taking the
  request, or answers with anything but a JSON object of lines -- not JSON, not an object, one
  without its `devices` or `points`, a point without its number, items that are not lines.
- Should anything else stop the download step, it is an ERROR in the log as well, and the run
  goes on with the local files.
- A stream fetched from the site is not also downloaded by FTP: a configured FTP download for it
  is an ERROR about the conflict, and the site's data is used.

## Publishing a protocol

- **Upload**: `POST <site>/api/v1/protocols/upload/`, multipart, 30 second timeout, with
  `competition_token`, `protocol_type` (`group` or `absolute`), `is_live` (`true` / `false`),
  `stage_label`, `section`, and by the format the HTML file as `html_file` and the document
  ([protocols.md](protocols.md)) as `document` (`protocol.json`). Any 2xx answer is a success; a
  `document_error` in it is a WARNING that the site shows the HTML.
- "Data" that the site refuses with a 400 is a WARNING, and the HTML is uploaded instead. "Data"
  whose document could not be built sends the HTML.
- **Delete**: `POST <site>/api/v1/protocols/delete/`, form-encoded, with `competition_token`,
  `protocol_type` and `section`. Deleting a protocol that is not there succeeds.
- "Nothing" leaves the site alone. Without a site URL nothing is published. A failure is an
  ERROR at the end of the run's log.
- In Eliminator Finals an Upload of the absolute protocol is a Delete, since a finals run writes
  none.

## Live statistics

- With "Send group statistics" or "Send absolute statistics" on and a site URL set, every run
  but a finals one `POST`s `{"competition_token": ..., "stats": {<number>: {<key>: <value>}}}`
  as JSON to `<site>/api/v1/live-stats/`; the snapshot replaces the previous one, and the site
  answers with the count it stored.
- Every value comes from lap finishes only, never from control points, so a missed control point
  mark cannot move a place or a gap; a penalty is already in the lap times and a DSQ mark
  disqualifies. The riders are ranked with the protocol's comparison without its control points
  and numbered 1, 2, 3 -- a dead heat is not shared -- and a disqualified rider's place is
  `DSQ`, outside the numbering. Keys, each with the suffix `_group` or `_abs` of its switch:
  `place` (a number or `DSQ`), `qty` (the riders of the scope), `gap_prev`, `gap_next` and
  `gap_leader`, the same three again with `_delta` after the suffix (how the gap changed over
  the last lap); for the whole race the participant packs, `gap_prev_pack_abs`,
  `gap_next_pack_abs`, `qty_prev_pack_abs` and `qty_next_pack_abs`; and `laps` as
  `<done>/<total>`.
- A gap is taken at the last lap finish both riders completed -- in Number of Tries it is the
  difference of their results, in the first rule's direction -- and is signed for the reader: a
  rider ahead is `+`, one behind `-`; it prints as `M:SS` (`H:MM:SS` past an hour) with the
  protocol's decimals. Riders whose gap is at most the pack gap are one pack.

## FTP

- FTP tab: "FTP address", "Login", "Password" (masked), an action per stream -- start list,
  group times, finish times, remote points -- "None", "Download", "Merge" or "Merge+Remove",
  "Merge by competitor number (ID) only", and the two "Upload ... Protocol after generate"
  switches. The start check list has an action of its own on the Main tab.
- `ftp://` only; `ftps://` is refused. Port 21 unless the address names one; anonymous login
  without a login; a 10 second connection timeout. A file is `<address path>/<local file name>`.
- "Download" replaces the local file with the remote one, rewritten in UTF-8. "Merge" adds the
  remote lines to the local file: the remote file's last copy of a line wins and replaces the
  local copies, by the whole line or, for the start list with "Merge by competitor number (ID)
  only", by the number. "Merge+Remove" also deletes the remote file once the local one is
  written.
- Downloads run before a run, or alone with the FTP tab's "Download" button. After a run the
  group protocol, and the absolute one except in Eliminator Finals, are uploaded when their
  switches are on.
