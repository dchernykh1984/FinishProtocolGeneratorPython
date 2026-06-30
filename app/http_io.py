"""HTTP I/O with the cycling-site API: protocol upload and start-list download."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def fetch_start_list(site_url: str, token: str) -> list[str]:
    """Fetch every device's start list for a competition and merge them into one list.

    The site stores a separate list per ``device_id`` (each StartProtocolMaker uploads
    its own); the merge here concatenates them in device-id order -- the generator-side
    combination the protocol is then built from.

    Args:
        site_url: Base URL of the site, e.g. "https://example.com".
        token: Upload token (UUID) from the competition detail page.

    Returns:
        The merged start-protocol lines (one per competitor).

    Raises:
        ValueError: On HTTP error, network error, or invalid JSON response.
    """
    url = (
        site_url.rstrip("/")
        + "/api/v1/start-list/?"
        + urllib.parse.urlencode({"competition_token": token})
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Connection error: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid response: {exc}") from exc

    devices = data.get("devices", [])
    return [line for device in devices for line in device.get("items", [])]


def _fetch_stream(site_url: str, token: str, endpoint: str) -> list[str]:
    """Fetch a per-device timing stream (group/finish), merged in device-id order."""
    url = (
        site_url.rstrip("/")
        + f"/api/v1/{endpoint}/?"
        + urllib.parse.urlencode({"competition_token": token})
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Connection error: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid response: {exc}") from exc
    devices = data.get("devices", [])
    return [line for device in devices for line in device.get("items", [])]


def fetch_group_times(site_url: str, token: str) -> list[str]:
    """Fetch every device's group-start times for a competition, merged."""
    return _fetch_stream(site_url, token, "group-times")


def fetch_finish_times(site_url: str, token: str) -> list[str]:
    """Fetch every device's finish (point 0) times for a competition, merged."""
    return _fetch_stream(site_url, token, "finish-times")


def fetch_remote_points(site_url: str, token: str) -> dict[int, list[str]]:
    """Fetch remote control points as ``{point_number: merged_lines}``.

    Lines for the same point from different devices are already merged server-side.
    """
    url = (
        site_url.rstrip("/")
        + "/api/v1/remote-points/?"
        + urllib.parse.urlencode({"competition_token": token})
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Connection error: {exc.reason}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid response: {exc}") from exc
    return {
        int(p["point_number"]): list(p.get("items", [])) for p in data.get("points", [])
    }


def upload_protocol(  # noqa: C901
    site_url: str,
    upload_token: str,
    protocol_type: str,
    local_path: str,
    is_live: bool = True,
    stage_label: str = "",
    errors_out: list[str] | None = None,
) -> int:
    """Upload a protocol HTML file to the cycling-site web API via HTTP POST.

    Returns 0 on success, -1 on error. Appends a human-readable message to
    *errors_out* on failure when provided.
    """
    if not site_url or not local_path:
        if errors_out is not None:
            errors_out.append("HTTP site URL or local file path is empty")
        return -1

    local = Path(local_path)
    if not local.exists():
        if errors_out is not None:
            errors_out.append(f"File not found: {local_path}")
        return -1

    upload_url = site_url.rstrip("/") + "/api/v1/protocols/upload/"

    try:
        content = local.read_bytes()
        filename = local.name
        boundary = uuid.uuid4().hex

        def _field(name: str, value: str) -> bytes:
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()

        parts: list[bytes] = [
            _field("competition_token", upload_token),
            _field("protocol_type", protocol_type),
            _field("is_live", "true" if is_live else "false"),
            _field("stage_label", stage_label),
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="html_file";'
                f' filename="{filename}"\r\n'
                "Content-Type: text/html\r\n\r\n"
            ).encode()
            + content
            + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        body = b"".join(parts)

        req = urllib.request.Request(  # noqa: S310
            upload_url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            if not (200 <= resp.status < 300):
                if errors_out is not None:
                    errors_out.append(
                        f"HTTP upload to {upload_url} failed: status {resp.status}"
                    )
                return -1
        return 0

    except urllib.error.HTTPError as exc:
        if errors_out is not None:
            errors_out.append(
                f"HTTP upload to {upload_url} failed: {exc.code} {exc.reason}"
            )
        return -1
    except Exception as exc:
        if errors_out is not None:
            errors_out.append(f"HTTP upload to {upload_url} failed: {exc}")
        return -1
