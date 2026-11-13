# SPDX-License-Identifier: AGPL-3.0-only
"""Crash signature from what each platform recorded (pure parsers plus two small readers): the fatal signal or
exception and the faulting stack as "module +offset" frames. Module names keep only their base name; absolute
addresses (different at every start) are dropped. The result passes the privacy filter in the report.
"""
import glob
import json
import os
import re
import subprocess

MAX_FRAMES = 20
_SIGNAL = re.compile(r"Fatal exception: Signal (\d+)")
_FRAME = re.compile(r"([^\s()\[\]]+)\(([^)]*)\)")  # backtrace_symbols: /path/libx.so(symbol+0x1f) or (+0x1f)
_PY_FATAL = re.compile(r"Fatal Python error: (.+)")
_TRAMPOLINE = re.compile(r"libc\.so\.\d+ \+0x[0-9a-f]+$")
_RAISING = re.compile(r"libc\.so\.\d+ (pthread_kill|gsignal|raise|abort)\b")
SIGNALS = {4: "SIGILL", 6: "SIGABRT", 7: "SIGBUS", 8: "SIGFPE", 11: "SIGSEGV"}


def linux_frame(line):
    """"/opt/x/program/libmergedlo.so(+0x3a2b1c) [0x7f..]" -> "libmergedlo.so +0x3a2b1c" (pure)."""
    found = _FRAME.search(line)
    if not found:
        return None
    module, inner = os.path.basename(found.group(1)), found.group(2)
    return ("%s %s" % (module, inner)).strip() if inner else module


def crash_frames(frames):
    """The frames below the signal that started it all (pure). The office's handler aborts after a fatal signal, so
    the stack it prints runs: handler frames, abort, handler again, raise(s), the signal trampoline (a libc frame
    without symbol), then the code that crashed. Without such a trampoline every frame is kept."""
    for i, frame in enumerate(frames[:-1]):
        if _TRAMPOLINE.match(frame) and not _RAISING.match(frames[i + 1]):
            return frames[i + 1:]
    return frames


def from_linux_stderr(text):
    """Signature from the stderr of a crashed session (pure): Python's fatal error line when an older build wrote one,
    the office handler's first "Fatal exception: Signal N" (the fault itself, printed before the emergency save; a
    later one is the abort that follows) and the crashing frames of its stack."""
    text = text or ""
    lines = text.splitlines()
    start = min((i for i, line in enumerate(lines) if _SIGNAL.search(line)), default=None)
    python = _PY_FATAL.findall(text)
    if start is None and not python:
        return ""
    out = ["Fatal signal: %s" % python[0].strip()] if python else []
    if start is not None:
        number = int(_SIGNAL.search(lines[start]).group(1))
        out.append("Office handler: Signal %d (%s)" % (number, SIGNALS.get(number, "?")))
        frames = [linux_frame(line) for line in lines[start + 1:start + 1 + 64] if line.startswith("#")]
        out += ["  " + frame for frame in crash_frames([f for f in frames if f])][:MAX_FRAMES]
    return "\n".join(out)


def from_ips(text):
    """macOS .ips crash report (header JSON line, then the body JSON) -> signature (pure)."""
    try:
        body = json.loads(text.split("\n", 1)[1])
    except (IndexError, ValueError):
        return ""
    exc = body.get("exception", {})
    out = ["%s (%s)" % (exc.get("type", "?"), exc.get("signal", "?"))]
    images = body.get("usedImages", [])
    threads = body.get("threads", [])
    index = body.get("faultingThread", 0)
    frames = threads[index].get("frames", []) if 0 <= index < len(threads) else []
    for frame in frames[:MAX_FRAMES]:
        image = images[frame.get("imageIndex", -1)] if 0 <= frame.get("imageIndex", -1) < len(images) else {}
        name = image.get("name") or os.path.basename(image.get("path", "")) or "?"
        out.append("  %s +0x%x%s" % (name, frame.get("imageOffset", 0),
                                      (" " + frame["symbol"]) if frame.get("symbol") else ""))
    return "\n".join(out)


def from_mac_reports(folder, since):
    """The newest soffice crash report written after `since` (epoch seconds), parsed; "" when none."""
    paths = [p for p in glob.glob(os.path.join(folder, "soffice*.ips")) if os.path.getmtime(p) >= since]
    if not paths:
        return ""
    try:
        with open(max(paths, key=os.path.getmtime), encoding="utf-8", errors="replace") as handle:
            return from_ips(handle.read())
    except OSError:
        return ""


_DATA = re.compile(r"<Data(?: Name='(\w+)')?>([^<]*)</Data>")
_CREATED = re.compile(r"SystemTime='([^']+)'")
EVENT_FIELDS = ("AppName", "AppVersion", "AppTimeStamp", "ModuleName", "ModuleVersion", "ModuleTimeStamp",
                "ExceptionCode", "FaultingOffset")  # the fixed order of event 1000 when names are missing


def from_event_xml(xml):
    """One Windows "Application Error" event (XML) -> signature, or "" when it is not soffice's (pure)."""
    pairs = _DATA.findall(xml)
    fields = {name or (EVENT_FIELDS[i] if i < len(EVENT_FIELDS) else str(i)): value
              for i, (name, value) in enumerate(pairs)}
    if fields.get("AppName", "").lower() not in ("soffice.bin", "soffice.exe"):
        return ""
    return "Exception %s in %s %s at offset %s (soffice %s)" % (
        fields.get("ExceptionCode", "?"), fields.get("ModuleName", "?"), fields.get("ModuleVersion", ""),
        fields.get("FaultingOffset", "?"), fields.get("AppVersion", "?"))


def event_time(xml):
    """Epoch seconds of an event's SystemTime (pure); 0 when unreadable."""
    import calendar
    import time
    found = _CREATED.search(xml)
    try:
        return calendar.timegm(time.strptime(found.group(1)[:19], "%Y-%m-%dT%H:%M:%S")) if found else 0
    except ValueError:
        return 0


def from_windows_events(since, run=subprocess.run):
    """The newest soffice Application Error event after `since`, via wevtutil (no window); "" when none."""
    query = "*[System[Provider[@Name='Application Error'] and (EventID=1000)]]"
    try:
        out = run(["wevtutil", "qe", "Application", "/q:" + query, "/c:10", "/rd:true", "/f:xml"],
                  capture_output=True, text=True, timeout=15, creationflags=0x08000000).stdout
    except Exception:  # noqa: BLE001 - no wevtutil, access denied, timeout
        return ""
    for event in re.findall(r"<Event .*?</Event>", out or "", re.S):
        if event_time(event) >= since - 60:
            signature = from_event_xml(event)
            if signature:
                return signature
    return ""


# "Application Hang" 1002 carries unnamed <Data> in this order (its message: "The program %1 version %2 stopped
# interacting with Windows and was closed ... Process ID %3 Start Time %4 Termination Time %5 Application Path %6
# Report Id %7 ... Hang type %10").
HANG_FIELDS = ("AppName", "AppVersion", "ProcessId", "StartTime", "TerminationTime", "AppPath", "ReportId",
               "PackageFullName", "PackageRelativeAppId", "HangType")
_HANG_REPORTS = ("AppHangB1", "AppHangXProcB1", "AppHangTransient")
_OFFICE = ("soffice.bin", "soffice.exe")
_EVENT_ID = re.compile(r"<EventID[^>]*>(\d+)</EventID>")


def from_hang_xml(xml):
    """One "Application Hang" (1002) or WER hang report (1001 AppHangB1) event -> text, "" when not soffice's (pure)."""
    pairs = _DATA.findall(xml)
    found = _EVENT_ID.search(xml)
    if found and found.group(1) == "1001":
        fields = {name: value for name, value in pairs}
        if fields.get("EventName") not in _HANG_REPORTS or fields.get("P1", "").lower() not in _OFFICE:
            return ""
        return "%s report for soffice %s" % (fields["EventName"], fields.get("P2", "?"))
    fields = {name or (HANG_FIELDS[i] if i < len(HANG_FIELDS) else str(i)): value
              for i, (name, value) in enumerate(pairs)}
    if fields.get("AppName", "").lower() not in _OFFICE:
        return ""
    kind = fields.get("HangType", "").strip()
    return "Application Hang (soffice %s)%s" % (fields.get("AppVersion", "?"), ("; hang type: %s" % kind) if kind else "")


def windows_hang(since, run=subprocess.run):
    """{"time": epoch, "text"} of the newest soffice hang event after `since` (the user or Windows closed a "not
    responding" office), via wevtutil; None when none."""
    query = ("*[System[(Provider[@Name='Application Hang'] and EventID=1002) or "
             "(Provider[@Name='Windows Error Reporting'] and EventID=1001)]]")
    try:
        out = run(["wevtutil", "qe", "Application", "/q:" + query, "/c:50", "/rd:true", "/f:xml"],
                  capture_output=True, text=True, timeout=15, creationflags=0x08000000).stdout
    except Exception:  # noqa: BLE001 - no wevtutil, access denied, timeout
        return None
    for event in re.findall(r"<Event .*?</Event>", out or "", re.S):
        when = event_time(event)
        if when >= since - 60:
            text = from_hang_xml(event)
            if text:
                return {"time": when, "text": text}
    return None
