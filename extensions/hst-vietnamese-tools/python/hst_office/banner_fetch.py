# SPDX-License-Identifier: AGPL-3.0-only
"""Five-second wall-clock request deadline, including DNS; kill and reap the private HTTPS helper."""
import json
from pathlib import Path
import subprocess
import sys
import time

from .banner_schema import MAX_IMAGE
from .banner_urls import https_url, test_url
from .update_logic import version_key

TIMEOUT = 5
PROBE_TIMEOUT = 1.5
MAX_POST = 8192  # display report body (banner_impressions_report)


def interpreter():
    """Use this runtime's Python, including the embedded Windows/macOS office layout; no PATH lookup."""
    candidates = [getattr(sys, "_base_executable", ""), sys.executable,
                  str(Path(sys.prefix) / "bin/python3"), str(Path(sys.prefix) / "python.exe")]
    for name in candidates:
        path = Path(name)
        if path.name.lower().startswith("python") and path.is_file():
            return str(path.resolve())
    raise OSError("banner Python helper unavailable")


def _run(payload, timeout, helper="banner_http.py"):
    """Bytes the private helper wrote before the wall-clock deadline; it is killed and reaped at expiry.

    `helper` is a sibling module of this package: banner_http.py, or error_report_http.py for an error report."""
    deadline = time.monotonic() + timeout
    options = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL,
               "shell": False, "close_fds": True}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    # -I/-S excludes user site and environment imports. The installed helper adds only its own package.
    with subprocess.Popen([interpreter(), "-I", "-S", str(Path(__file__).with_name(helper))], **options) as proc:
        try:
            data, _ = proc.communicate(payload, timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.communicate()
            raise TimeoutError("banner request deadline") from exc
        if time.monotonic() >= deadline:
            raise TimeoutError("banner request deadline")
        if proc.returncode:
            raise ValueError("banner response refused")
    return data


def fetch(url, limit, version, proxy=None, allow_test=False):
    """allow_test (test-stamped packages only): plain HTTP to the local test server, without a proxy."""
    allow_test = allow_test is True
    if not (https_url(url) or (allow_test and test_url(url))) or not isinstance(limit, int) or not 0 < limit <= MAX_IMAGE:
        raise ValueError("invalid banner request")
    version_key(version)
    args = dict(url=url, limit=limit, version=version, proxy=proxy)
    if allow_test:
        args["allow_test"] = True
    payload = json.dumps(args).encode()
    if len(payload) > 16384:
        raise ValueError("banner request too large")
    data = _run(payload, TIMEOUT)
    if len(data) > limit:
        raise ValueError("banner response refused")
    return data


def head_status(url, version, proxy=None, timeout=PROBE_TIMEOUT):
    """Status of one HEAD through the same helper, proxy settings and User-Agent as the feed."""
    if not https_url(url):
        raise ValueError("invalid banner request")
    version_key(version)
    payload = json.dumps(dict(head=True, url=url, version=version, proxy=proxy, timeout=timeout)).encode()
    if len(payload) > 16384:
        raise ValueError("banner request too large")
    return int(_run(payload, timeout))


def post_status(url, body, version, proxy=None):
    """Status of one bounded JSON POST through the same helper, deadline, proxy settings and User-Agent."""
    if not https_url(url) or not isinstance(body, bytes) or not 0 < len(body) <= MAX_POST:
        raise ValueError("invalid banner request")
    version_key(version)
    text = body.decode("ascii")  # the report is ASCII JSON; anything else is refused before the helper
    payload = json.dumps(dict(post=True, url=url, body=text, version=version, proxy=proxy)).encode()
    if len(payload) > 16384:
        raise ValueError("banner request too large")
    return int(_run(payload, TIMEOUT))
