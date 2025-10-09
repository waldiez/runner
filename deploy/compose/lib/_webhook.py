# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.


"""Webhook for notifying about operation."""

import json
import os
import socket
from urllib.request import Request, urlopen

from ._common import utc_now


def _split_headers(raw: str | None) -> list[tuple[str, str]]:
    # Accept comma- or newline-separated "Key: Value" pairs
    if not raw:
        return []
    # Replace commas with newlines, then split lines
    lines = [ln.strip() for ln in raw.replace(",", "\n").splitlines()]
    headers: list[tuple[str, str]] = []
    for ln in lines:
        if not ln:
            continue
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        headers.append((k.strip(), v.strip()))
    return headers


def notify(
    webhook_url: str | None,
    status: str,
    message: str,
    backup_name: str,
    headers: str | None = None,
) -> None:
    """Make a webhook request to notify the operation status.

    Parameters
    ----------
    webhook_url : str | None
        The webhook url.
    status : str
        The operation status (success|failure)
    message : str
        The message to send.
    backup_name : str
        The name of the backup that was created or restored.
    headers : str | None = None
        Extra additional headers for the request.
    """
    if not webhook_url:
        return
    payload: dict[str, str] = {
        "status": status,
        "backup_name": backup_name,
        "timestamp": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": message,
        "hostname": (
            os.uname().nodename  # pyright: ignore
            if hasattr(os, "uname")
            else socket.gethostname()
        ),
    }
    data = json.dumps(payload).encode("utf-8")
    hdr: list[tuple[str, str]] = [
        ("Content-Type", "application/json"),
        *_split_headers(headers),
    ]
    try:
        req = Request(  # nosemgrep  # nosec
            webhook_url,
            data=data,
            headers=dict(hdr),
            method="POST",
        )
        with urlopen(req, timeout=10):  # nosemgrep # nosec
            pass
    except Exception:  # pylint: disable=broad-exception-caught
        # best effort only
        pass
