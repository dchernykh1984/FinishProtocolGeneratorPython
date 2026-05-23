"""FTP download and file-merge utilities.

Mirrors the C++ ``downloadFile`` / ``mergeFiles`` / ``similarStrings`` logic.
"""

from __future__ import annotations

import ftplib
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

DOWNLOAD_ACTIONS = ("None", "Download", "Merge", "Merge+Remove")


def _decode_lines(path: Path) -> list[str] | None:
    """Read non-empty lines, auto-detecting encoding (utf-8, cp1251, latin-1).

    Returns None if every encoding attempt raises UnicodeDecodeError so the
    caller can propagate an error instead of silently mangling the data.
    """
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return [
                ln for ln in path.read_text(encoding=enc).splitlines() if ln.strip()
            ]
        except UnicodeDecodeError:
            continue
    return None


def similar_strings(first: str, second: str, only_id: bool) -> bool:
    """Return True if two competitor lines are considered equal.

    When *only_id* is True only the first ``#``-delimited field is compared
    (the competitor number), matching the C++ ``similarStrings`` behaviour.
    """
    if only_id:
        return first.split("#")[0] == second.split("#")[0]
    return first.rstrip("\r\n") == second.rstrip("\r\n")


def _apply_merge(
    raw_to: list[str], raw_from: list[str], merge_by_id: bool
) -> tuple[list[str], int]:
    """Core merge algorithm: returns (result_lines, added_count).

    - fromFile duplicates: last occurrence wins (C++ behaviour).
    - toFile lines superseded by fromFile are dropped.
    - toFile internal duplicates: last occurrence wins.
    """
    unique_from: list[str] = []
    for i, line in enumerate(raw_from):
        if not any(
            similar_strings(line, raw_from[j], merge_by_id)
            for j in range(i + 1, len(raw_from))
        ):
            unique_from.append(line)

    result: list[str] = []
    for i, line in enumerate(raw_to):
        dup_in_to = any(
            similar_strings(line, raw_to[j], merge_by_id)
            for j in range(i + 1, len(raw_to))
        )
        if dup_in_to:
            continue
        if any(similar_strings(line, f, merge_by_id) for f in unique_from):
            continue
        result.append(line)

    added = 0
    for line in unique_from:
        if not any(similar_strings(line, t, merge_by_id) for t in raw_to):
            added += 1
        result.append(line)

    return result, added


def merge_files(to_file: str, from_file: str, merge_by_id: bool) -> int:
    """Merge *from_file* into *to_file*, deduplicating both.

    Reads with encoding auto-detection (utf-8, cp1251, latin-1); always
    writes UTF-8.  Returns the number of lines genuinely added from
    *from_file*, or -1 on I/O or decode error.
    """
    try:
        to_path = Path(to_file)
        from_path = Path(from_file)

        raw_to: list[str] = []
        if to_path.exists():
            decoded_to = _decode_lines(to_path)
            if decoded_to is None:
                return -1
            raw_to = decoded_to

        decoded_from = _decode_lines(from_path)
        if decoded_from is None:
            return -1

        result, added = _apply_merge(raw_to, decoded_from, merge_by_id)
        to_path.write_text(
            "\n".join(result) + ("\n" if result else ""),
            encoding="utf-8",
        )
        return added
    except OSError:
        return -1


def _parse_ftp_url(ftp_path: str) -> tuple[str, int, str]:
    if not ftp_path.startswith(("ftp://", "ftps://")):
        ftp_path = "ftp://" + ftp_path
    parsed = urlparse(ftp_path)
    host = parsed.hostname or ""
    port = parsed.port or 21
    base = parsed.path or "/"
    if not base.endswith("/"):
        base += "/"
    return host, port, base


def download_file(  # pragma: no cover
    ftp_path: str,
    login: str,
    password: str,
    local_path: str,
    merge_required: bool,
    remove_required: bool,
    merge_by_id: bool,
) -> int:
    """Download *local_path*'s filename from the FTP server at *ftp_path*.

    - *merge_required*: merge downloaded content into the existing local file
      instead of overwriting it.
    - *remove_required*: delete the remote file from the server after
      downloading (``Merge+Remove`` action).

    Returns 0 on success, -1 on error.
    """
    if not ftp_path or not local_path:
        return -1

    filename = Path(local_path.replace("\\", "/")).name
    try:
        host, port, base = _parse_ftp_url(ftp_path)
    except Exception:
        return -1

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
    os.close(tmp_fd)  # only the path is needed; close fd now to avoid leaks
    try:
        with ftplib.FTP() as ftp:  # noqa: S321
            ftp.connect(host, port, timeout=10)
            ftp.login(login or "anonymous", password or "")
            remote_path = base + filename
            with Path(tmp_path).open("wb") as f:
                ftp.retrbinary(f"RETR {remote_path}", f.write)

        # Apply locally before touching the remote file.
        if merge_required:
            if merge_files(local_path, tmp_path, merge_by_id) < 0:
                return -1
        else:
            decoded = _decode_lines(Path(tmp_path))
            if decoded is None:
                return -1
            Path(local_path).write_text(
                "\n".join(decoded) + ("\n" if decoded else ""),
                encoding="utf-8",
            )

        # Delete from remote only after local success; propagate errors.
        if remove_required:
            with ftplib.FTP() as ftp:  # noqa: S321
                ftp.connect(host, port, timeout=10)
                ftp.login(login or "anonymous", password or "")
                ftp.delete(remote_path)

        return 0
    except Exception:
        return -1
    finally:
        Path(tmp_path).unlink(missing_ok=True)
