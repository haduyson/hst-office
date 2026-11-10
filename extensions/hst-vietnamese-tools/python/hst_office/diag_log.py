# SPDX-License-Identifier: AGPL-3.0-only
"""HST's persistent local log: what went wrong, kept on this machine and attached to an error report.

<user profile>/user/hst-office/hst-office.log, rotated to hst-office.log.1 at 1 MB (two files, at most 2 MB). One
entry per event: UTC time, level, component, message; a traceback follows indented. Every entry passes the privacy
filter (error_report_filter.scrub) BEFORE it is written: no paths, URLs, document or user names reach the disk, so
the file itself never holds personal data. Callers log facts (version, error codes, exception types), never document
text. Logging never raises: a full disk or a read-only profile only loses the entry.

Entries: session start and exit (diag_crash), Python exceptions of the HST components (exception()), HST warnings
and errors shown to the user (Host.say), failed update and token set-up operations with their codes.
"""
import os
import tempfile
import threading
import time
import traceback

from .error_report_filter import personal_strings, scrub, tail_lines

LOG_NAME = "hst-office.log"
MAX_BYTES = 1024 * 1024  # per file; hst-office.log.1 holds the previous megabyte
READ_BYTES = 256 * 1024  # read from the end of each file for recent()
LEVELS = ("info", "warning", "error")
_LOCK = threading.RLock()
_STATE = {"dir": None, "secrets": None}


def configure(directory, secrets=None):
    """Set the log directory (and the personal strings to filter); tests and diag_crash.start call this."""
    with _LOCK:
        _STATE["dir"], _STATE["secrets"] = directory, secrets


def _office_dir():
    """<profile>/user/hst-office of the running office, or the temp directory outside the office."""
    try:
        import uno
        ctx = uno.getComponentContext()
        subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
        url = subst.substituteVariables("$(user)", True)
        return os.path.join(uno.fileUrlToSystemPath(url), "hst-office")
    except Exception:  # noqa: BLE001 - no office (unit tests, tools)
        return os.path.join(tempfile.gettempdir(), "hst-office-diagnostics")


def log_dir():
    with _LOCK:
        if _STATE["dir"] is None:
            _STATE["dir"] = _office_dir()
        return _STATE["dir"]


def _secrets():
    """Personal strings to filter: the environment's, plus the office's user/work/home folders inside the office."""
    if _STATE["secrets"] is None:
        try:
            import uno
            from .error_report_info import office_secrets
            _STATE["secrets"] = office_secrets(uno.getComponentContext())
        except Exception:  # noqa: BLE001 - outside the office
            _STATE["secrets"] = personal_strings()
    return _STATE["secrets"]


def format_entry(level, component, message, detail="", clock=time.time):
    """One scrubbed entry (pure apart from the clock): a header line, then the indented detail lines."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock()))
    level = level if level in LEVELS else "info"
    head = "%s %s %s: %s" % (stamp, level.upper(), component or "hst", " ".join(str(message).split()))
    body = "".join("\n  " + line for line in (detail or "").rstrip().splitlines())
    return head + body + "\n"


def _rotate(path, incoming):
    try:
        if os.path.getsize(path) + incoming > MAX_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass  # no log yet


def write(level, component, message, detail=""):
    """Append one entry; never raises."""
    try:
        with _LOCK:
            secrets = _secrets()
            entry = scrub(format_entry(level, component, message, detail), secrets)
            directory = log_dir()
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, LOG_NAME)
            data = entry.encode("utf-8", "replace")
            _rotate(path, len(data))
            with open(path, "ab") as handle:
                handle.write(data)
    except Exception:  # noqa: BLE001 - logging must never break the caller
        pass


def info(component, message):
    write("info", component, message)


def warning(component, message):
    write("warning", component, message)


def error(component, message):
    write("error", component, message)


def exception(component, print_too=True):
    """Inside an except block: log the current exception with its traceback (and print it as before)."""
    if print_too:
        traceback.print_exc()
    text = traceback.format_exc()
    last = text.strip().splitlines()[-1] if text.strip() else "exception"
    write("error", component, last, text)


def _tail(path):
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - READ_BYTES))
            return handle.read().decode("utf-8", "replace")
    except OSError:
        return ""


def recent(max_lines, max_bytes):
    """The last whole lines of the log (previous file first), within both limits."""
    path = os.path.join(log_dir(), LOG_NAME)
    with _LOCK:
        text = _tail(path + ".1") + _tail(path)
    # the first line of a file read from the middle may be cut: tail_lines keeps whole lines from the end
    return tail_lines(scrub(text, _secrets()), max_lines, max_bytes).strip()
