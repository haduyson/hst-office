# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the fault note of a crash the office's own handler ends silently (patch hst-windows-silent-crash-note).

A crash on the office's main thread before its main loop runs (start-up), at shutdown or under --norestore ends in the
office's handler with exit(255): Windows records no Application Error event and no WER report, the recovery flag stays
false, so the next start could only say "not closed". At start-up arm() names a fresh note file in the environment
(HST_FAULT_NOTE); the handler writes the first unhandled exception there ("code=0x.. module=.. offset=0x.. thread=..")
and appends "end=exit255" when it ends the process itself. The next start reads it (read) and turns it into the crash
signature (signature). Module base names and offsets only.
"""
import os
import re

NAME = "last-fault.txt"
ENV = "HST_FAULT_NOTE"
_FAULT = re.compile(r"code=0x([0-9A-Fa-f]{8}) module=(\S+) offset=0x([0-9A-Fa-f]+)")
NOTE_CODES = {"C0000005": "access violation", "E06D7363": "C++ exception", "C0000094": "integer divide by zero",
              "C00000FD": "stack overflow", "80000003": "breakpoint", "00000000": "abort"}


def signature(text):
    """The note's text -> crash signature (pure); "" when it has no fault line."""
    found = _FAULT.search(text or "")
    if not found:
        return ""
    code = found.group(1).upper()
    module = os.path.basename(found.group(2).replace("\\", "/"))
    kind = NOTE_CODES.get(code)
    text_out = "Exception %s%s in %s at offset 0x%s" % (code.lower(), " (%s)" % kind if kind else "", module,
                                                      found.group(3).lower())
    if "end=exit255" in text:
        text_out += "; the office's crash handler ended the process (exit code 255), so Windows recorded nothing"
    return text_out


def read(path, started):
    """The note of the session that started at `started` (a note older than that session is not its own); ""."""
    try:
        if os.path.getmtime(path) < started - 60:
            return ""
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(4096)
    except OSError:
        return ""


def arm(path):
    """Remove the previous note (already read) and name `path` to this process's crash handler."""
    try:
        os.remove(path)
    except OSError:
        pass
    import ctypes
    ctypes.windll.kernel32.SetEnvironmentVariableW(ENV, path)
