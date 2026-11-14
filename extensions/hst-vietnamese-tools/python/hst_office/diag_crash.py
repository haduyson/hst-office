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
    A crash the office's own handler ends with exit(255) (before the main loop, at shutdown, a second fault) leaves
    no event: the handler notes the first fault in a file start() names (windows_fault_note).
    Without one, an "Application Hang" event (1002) or a WER AppHangB1 report (1001) for soffice.bin means the office
    had stopped answering and was closed by the user or Windows ("not responding"): the session ended as a hang.
While the session runs, session_heartbeat stores in the marker the last time the office answered and the apps of its
open documents (no names); the next start reports them, and the hang's length from that time to the hang event.
No document content or names; the signature passes the privacy filter like every log entry.
"""
import json
import os
import platform
import stat
import sys
import time

from . import crash_signature, diag_log, windows_fault_note, session_facts

MARKER = "session.json"
STDERR_NAME = "last-session.err"
STDERR_KEEP = 1024 * 1024  # a session's stderr beyond this is cut at the next start (only its end matters)
STATE = {"previous": None, "stderr": None, "closed": False}


def _path(name):
    return os.path.join(diag_log.log_dir(), name)


def read_marker(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def update_marker(fields):
    """Merge `fields` into this session's marker (temporary file, then rename: a kill never leaves half a marker).
    False once the session closed or when the marker cannot be written."""
    if STATE["closed"]:
        return False
    path = _path(MARKER)
    marker = read_marker(path)
    if marker is None:
        return False  # never started (diag_crash.start failed) or already removed
    marker.update(fields)
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(marker, handle)
        os.replace(path + ".tmp", path)
        return True
    except OSError:
        return False


def _beat_fields(marker):
    return {name: marker[name] for name in ("beat", "apps", "active", "modified", "loading") if name in marker}


def previous_session(system=None, marker=None, stderr_text=None, now=None, note_text=None):
    """{"ended": "crash"|"hang"|"not closed", "started", "signature", "hang", "version", and the last heartbeat's
    "beat", "apps", "active", "modified", "loading" when recorded} of an unclosed previous session, else None."""
    system = system or platform.system()
    marker = read_marker(_path(MARKER)) if marker is None else marker
    if not marker:
        return None
    started = float(marker.get("started", 0))
    pid = marker.get("pid")  # the session's own soffice.bin: events of other offices on the PC never count
    if system == "Linux":
        text = _read_stderr() if stderr_text is None else stderr_text
        signature = crash_signature.from_linux_stderr(text)
    elif system == "Darwin":
        signature = crash_signature.from_mac_reports(os.path.expanduser("~/Library/Logs/DiagnosticReports"), started)
    elif system == "Windows":
        note = windows_fault_note.read(_path(windows_fault_note.NAME), started) if note_text is None else note_text
        signature = windows_fault_note.combined(crash_signature.from_windows_events(started, pid=pid),
                                                windows_fault_note.signature(note))
    else:
        signature = ""
    hang = crash_signature.windows_hang(started, pid=pid) if system == "Windows" and not signature else None
    ended = "crash" if signature else "hang" if hang else "not closed"
    return dict(_beat_fields(marker), ended=ended, started=started, signature=signature, hang=hang,
                version=marker.get("version", ""))


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
        diag_log.info("session", "start %s build %s; %s %s; %s; python %s" % (
            product.get("version"), product.get("build"), os_.get("version"), os_.get("arch"), locale,
            platform.python_version()))
        if sys.platform != "win32":
            _capture_stderr()
        else:
            windows_fault_note.arm(_path(windows_fault_note.NAME))
    except Exception:  # noqa: BLE001
        diag_log.exception("diag_crash", print_too=False)
    return STATE["previous"]


def stop():
    """OnCloseApp: the session closed normally."""
    STATE["closed"] = True
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
    elif previous.get("hang"):
        lines.append("Crash signature: none; the system recorded a hang (not responding, then closed)")
        lines.append("Hang: %s" % previous["hang"]["text"])
    else:
        lines.append("Crash signature: none recorded by the office or the system")
    return lines + session_facts.beat_facts(previous)
