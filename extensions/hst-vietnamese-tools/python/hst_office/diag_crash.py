# SPDX-License-Identifier: AGPL-3.0-only
"""Crash capture: did the last session end without closing, and what did the office or the OS record about it.

A session marker (session.json in the diag_log directory) is written at OnStartApp and removed at OnCloseApp; a
marker found at the next start means the session never closed (crash, kill, power loss). The signature is what the
platform recorded, read at that next start (crash_signature.py parses it):
  * Linux: the office's own fatal-signal handler prints "Fatal exception: Signal N" and a backtrace
    (module(+offset) frames) to stderr, before the emergency save (hst-emergency-save-crash-log.patch) and again
    when it aborts. It goes to last-session.err (truncated at every start, one session only); the office's stderr
    itself is moved there only when nobody reads it (desktop start: no terminal, no pipe, not headless).
    Python's faulthandler is NOT enabled: its handler runs on a small alternate signal stack, and the office's
    emergency save (a dialog with its own event loop) then ran on that stack, overflowed it into the heap and
    crashed a second time before saving anything.
  * macOS: the system crash report (~/Library/Logs/DiagnosticReports/soffice*.ips) newer than the marker.
  * Windows: the "Application Error" event (1000) for soffice.bin in the Application log newer than the marker
    (faulting module, exception code, offset). faulthandler stays off there: it would log every C++ exception.
No document content or names; the signature passes the privacy filter like every log entry.
"""
import json
import os
import platform
import stat
import sys
import time

from . import crash_signature, diag_log

MARKER = "session.json"
STDERR_NAME = "last-session.err"
STDERR_KEEP = 1024 * 1024  # a session's stderr beyond this is cut at the next start (only its end matters)
STATE = {"previous": None, "stderr": None}


def _path(name):
    return os.path.join(diag_log.log_dir(), name)


def read_marker(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def previous_session(system=None, marker=None, stderr_text=None, now=None):
    """{"ended": "crash"|"not closed", "started", "signature"} of an unclosed previous session, else None."""
    system = system or platform.system()
    marker = read_marker(_path(MARKER)) if marker is None else marker
    if not marker:
        return None
    started = float(marker.get("started", 0))
    if system == "Linux":
        text = _read_stderr() if stderr_text is None else stderr_text
        signature = crash_signature.from_linux_stderr(text)
    elif system == "Darwin":
        signature = crash_signature.from_mac_reports(os.path.expanduser("~/Library/Logs/DiagnosticReports"), started)
    elif system == "Windows":
        signature = crash_signature.from_windows_events(started)
    else:
        signature = ""
    return {"ended": "crash" if signature else "not closed", "started": started, "signature": signature,
            "version": marker.get("version", "")}


def _read_stderr():
    path = _path(STDERR_NAME)
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - STDERR_KEEP))
            return handle.read().decode("utf-8", "replace")
    except OSError:
        return ""


def keep_stderr(fd=2, cmdline_path="/proc/self/cmdline"):
    """True when someone reads this office's stderr: a terminal, a pipe (scripts), or a headless/conversion run."""
    try:
        if os.isatty(fd) or stat.S_ISFIFO(os.fstat(fd).st_mode):
            return True
    except OSError:
        return False  # closed: nobody reads it
    try:
        with open(cmdline_path, "rb") as handle:
            args = handle.read().split(b"\0")
        return any(arg in (b"--headless", b"-headless", b"--convert-to", b"--print-to-file", b"--cat") for arg in args)
    except OSError:
        return False  # macOS: no /proc; a Finder start has no reader


def _capture_stderr():
    """Linux/macOS: stderr into last-session.err when nobody else reads it (desktop start). No faulthandler (see the
    module docstring: it broke the emergency save)."""
    try:
        handle = open(_path(STDERR_NAME), "w", encoding="utf-8")  # truncates the previous session's
        STATE["stderr"] = handle
        if not keep_stderr():
            os.dup2(handle.fileno(), 2)
    except Exception:  # noqa: BLE001 - diagnostics must never stop the start
        diag_log.exception("diag_crash", print_too=False)


def start(ctx, environment):
    """OnStartApp: remember an unclosed previous session, then mark this one and start capturing."""
    try:
        os.makedirs(diag_log.log_dir(), exist_ok=True)
        STATE["previous"] = previous_session()
        product, os_, locale, _app = environment
        with open(_path(MARKER), "w", encoding="utf-8") as handle:
            json.dump({"started": time.time(), "pid": os.getpid(), "version": product.get("version", "")}, handle)
        if STATE["previous"]:
            diag_log.warning("session", "previous session ended: %s" % STATE["previous"]["ended"])
        diag_log.info("session", "start %s build %s engine %s; %s %s; %s; python %s" % (
            product.get("version"), product.get("build"), product.get("engine"), os_.get("version"), os_.get("arch"),
            locale, platform.python_version()))
        if sys.platform != "win32":
            _capture_stderr()
    except Exception:  # noqa: BLE001
        diag_log.exception("diag_crash", print_too=False)
    return STATE["previous"]


def stop():
    """OnCloseApp: the session closed normally."""
    diag_log.info("session", "exit")
    try:
        os.remove(_path(MARKER))
    except OSError:
        pass


def facts(previous):
    """Lines for diagnostics.crash about an unclosed session (pure)."""
    if not previous:
        return []
    lines = ["Session marker: previous session %s (version %s)" % (previous["ended"], previous.get("version") or "?")]
    if previous.get("signature"):
        lines += ["Crash signature:", previous["signature"]]
    else:
        lines.append("Crash signature: none recorded by the office or the system")
    return lines
