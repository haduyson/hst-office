# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Five-second wall-clock request deadline, including DNS; kill and reap the private HTTPS helper."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from .banner_schema import MAX_IMAGE
from .banner_urls import https_url, test_url
from .update_logic import version_key

TIMEOUT = 5
PROBE_TIMEOUT = 1.5
MAX_POST = 8192  # display report body (banner_impressions_report)


ISOLATED = ["-I", "-S"]
# The bundled Linux python.bin finds its standard library only through PYTHONHOME, which -I (and -E) would hide:
# it runs without user site, site module and script-directory path entry, in an environment of our own instead.
ISOLATED_WITH_HOME = ["-s", "-S", "-P"]
PROBE = "import json, ssl, urllib.request"
_command = None  # (argv prefix, environment): chosen once per office process
_one_at_a_time = threading.Lock()  # banner, citation and error-report helpers queue; never run side by side


def _bundled(prefix=None):
    """(argv prefix, extra environment) of the office's own Python, most specific first.

    Embedded, sys.executable is whatever "python3" PATH names (often the system /usr/bin/python3): never used first.
    Windows: python-core-X/bin/python.exe needs program/ (python3XX.dll) on PATH. macOS: the framework's bin/python3.
    Linux: program/python.bin with python-core-X as its home."""
    prefix = Path(sys.base_prefix if prefix is None else prefix)
    program = prefix.parent
    found = []
    if (prefix / "bin" / "python.exe").is_file():
        found.append(([str(prefix / "bin" / "python.exe")] + ISOLATED, {"PATH": str(program)}))
    if (prefix / "bin" / "python3").is_file():
        found.append(([str(prefix / "bin" / "python3")] + ISOLATED, {}))
    if (program / "python.bin").is_file() and (prefix / "lib").is_dir():
        home = {"PYTHONHOME": str(prefix),
                "PYTHONPATH": os.pathsep.join((str(prefix / "lib"), str(prefix / "lib" / "lib-dynload")))}
        found.append(([str(program / "python.bin")] + ISOLATED_WITH_HOME, home))
    return found


def _fallbacks():
    """The interpreter running this code, when the office has no Python of its own (a distribution build)."""
    found = []
    for name in (getattr(sys, "_base_executable", ""), sys.executable):
        path = Path(name) if name else None
        if path and path.name.lower().startswith("python") and path.is_file():
            found.append(([str(path.resolve())] + ISOLATED, {}))
    return found


def _environment(extra):
    """The office's environment (proxy and CA variables stay) without any PYTHON* variable, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
    for key, value in extra.items():
        if key == "PATH":  # prepend; Windows spells it Path
            name = next((k for k in env if k.upper() == "PATH"), "PATH")
            value = value + os.pathsep + env.pop(name, "")
        env[key] = value
    return env


def _works(argv, env):
    options = {"env": env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.run(argv + ["-c", PROBE], timeout=20, check=False, **options).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def helper_command():
    """argv prefix and environment of the helper interpreter: the office's bundled Python when it starts and has
    TLS, else the running interpreter's executable. Probed once (one short process) and kept for the session."""
    global _command
    if _command is None:
        for argv, extra in _bundled() + _fallbacks():
            env = _environment(extra)
            if _works(argv, env):
                _command = (argv, env)
                break
        else:
            raise OSError("banner Python helper unavailable")
    return _command


def _run(payload, timeout, helper="banner_http.py"):
    """Bytes the private helper wrote before the wall-clock deadline; it is killed and reaped at expiry.

    `helper` is a sibling module of this package: banner_http.py, or error_report_http.py for an error report.
    Helpers run one at a time; the deadline starts when this one's turn comes."""
    with _one_at_a_time:
        argv, env = helper_command()
        deadline = time.monotonic() + timeout
        options = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL,
                   "shell": False, "close_fds": True, "env": env}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        # Isolated: no user site, no site module, no PYTHON* from the user. The installed helper adds only its package.
        with subprocess.Popen(argv + [str(Path(__file__).with_name(helper))], **options) as proc:
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
