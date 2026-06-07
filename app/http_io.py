"""HTTP multipart upload for protocol files."""

from __future__ import annotations

import urllib.error
import urllib.request
import uuid
from pathlib import Path


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

    upload_url = site_url.rstrip("/") + "/api/protocols/upload/"

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
            _field("upload_token", upload_token),
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
            if resp.status != 200:
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
