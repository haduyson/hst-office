# SPDX-License-Identifier: AGPL-3.0-only
"""Five-second wall-clock request deadline, including DNS; kill and reap the private HTTPS helper."""
import json
from pathlib import Path
import subprocess
import sys
import time

from .banner_schema import MAX_IMAGE
from .banner_urls import https_url
from .update_logic import version_key

TIMEOUT = 5


def interpreter():
    """Use this runtime's Python, including the embedded Windows/macOS office layout; no PATH lookup."""
    candidates = [getattr(sys, "_base_executable", ""), sys.executable,
                  str(Path(sys.prefix) / "bin/python3"), str(Path(sys.prefix) / "python.exe")]
    for name in candidates:
        path = Path(name)
        if path.name.lower().startswith("python") and path.is_file():
            return str(path.resolve())
    raise OSError("banner Python helper unavailable")


def fetch(url, limit, version, proxy=None):
    if not https_url(url) or not isinstance(limit, int) or not 0 < limit <= MAX_IMAGE:
        raise ValueError("invalid banner request")
    version_key(version)
    payload = json.dumps(dict(url=url, limit=limit, version=version, proxy=proxy)).encode()
    if len(payload) > 16384:
        raise ValueError("banner request too large")
    deadline = time.monotonic() + TIMEOUT
    options = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL,
               "shell": False, "close_fds": True}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    # -I/-S excludes user site and environment imports. The installed helper adds only its own package.
    with subprocess.Popen([interpreter(), "-I", "-S", str(Path(__file__).with_name("banner_http.py"))], **options) as proc:
        try:
            data, _ = proc.communicate(payload, timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.communicate()
            raise TimeoutError("banner request deadline") from exc
        if time.monotonic() >= deadline:
            raise TimeoutError("banner request deadline")
        if proc.returncode or len(data) > limit:
            raise ValueError("banner response refused")
    return data
