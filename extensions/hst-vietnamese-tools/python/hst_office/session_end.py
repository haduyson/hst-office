# SPDX-License-Identifier: AGPL-3.0-only
"""Did the operating system end the previous session (shut down, restart, log off), rather than a crash, a kill or a
power cut? Pure functions over what the office left behind (hst-session-end-note.patch).

  * Windows: the first WM_QUERYENDSESSION appends "session-end=query" to the fault note (HST_FAULT_NOTE, armed by
    windows_fault_note), WM_ENDSESSION appends "session-end=end", or "session-end=cancel" when the log off was
    cancelled. Windows ends the process right after WM_ENDSESSION, or while a save question still holds the log off
    ("Đóng bắt buộc" on the shutdown screen, or a forced restart for updates).
  * Linux: SIGTERM (systemd stopping the session at shutdown or log out; also a plain `kill`) ends the office at once;
    the office's handler first writes "Terminated: Signal 15" to stderr, which diag_crash keeps in last-session.err.

Such a session is not a crash: the next start still offers document recovery when the office kept recovery copies, but
does not ask to send a crash report. A fault recorded in the same session keeps it a crash (diag_crash checks the
crash signature first).
"""
import re

_LINUX = re.compile(r"^Terminated: Signal (\d+)\s*$", re.M)
_WINDOWS = re.compile(r"^session-end=(query|end|cancel)\s*$", re.M)


def from_linux_stderr(text):
    """What ended the session, from its stderr (pure); "" when the system did not end it."""
    if "15" in _LINUX.findall(text or ""):
        return "SIGTERM (shut down, log out or kill)"
    return ""


def from_windows_note(text):
    """What ended the session, from its fault note (pure); "" when the system did not end it or the log off was
    cancelled afterwards."""
    found = _WINDOWS.findall(text or "")
    if not found or found[-1] == "cancel":
        return ""
    if found[-1] == "end":
        return "WM_ENDSESSION (shut down, restart or log off)"
    return "WM_QUERYENDSESSION (shut down, restart or log off; ended while the office was still closing)"


def ended_by_system(state, previous):
    """True when the previous session was ended by the operating system and no emergency save ran: no crash report
    question (the recovery dialog still follows the office's own recovery state)."""
    return bool(previous) and previous.get("ended") == "session end" and not state.get("crashed")
