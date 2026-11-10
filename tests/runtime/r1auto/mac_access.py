# SPDX-License-Identifier: AGPL-3.0-only
"""Native macOS Accessibility and LaunchServices observations (tooling Python)."""
import plistlib
from pathlib import Path
import time


def applications():
    """Running HST Office apps, read fresh from the process table each call. NSWorkspace.runningApplications is
    only refreshed by the main run loop, which a script never runs: it stayed empty while HST Office ran
    (r1-auto macOS run 42472920150, M1-startup-failure.png)."""
    import psutil
    from AppKit import NSRunningApplication
    found = []
    for proc in psutil.process_iter(["pid", "exe"]):
        if "HST Office.app/Contents/MacOS/" in (proc.info["exe"] or ""):
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(proc.info["pid"])
            if app is not None:
                found.append(app)
    return found


def ended(app):
    """True once the app's process is gone (NSRunningApplication.isTerminated is run-loop updated too)."""
    import psutil
    return not psutil.pid_exists(app.processIdentifier())


def attribute(element, name, default=None):
    import ApplicationServices as ax
    error, value = ax.AXUIElementCopyAttributeValue(element, name, None)
    return value if error == 0 else default


def nodes(app, budget=15.0):
    """Breadth-first AX walk; a busy app answers each call within 2 s and the walk within `budget` s."""
    import ApplicationServices as ax
    root = ax.AXUIElementCreateApplication(app.processIdentifier())
    ax.AXUIElementSetMessagingTimeout(ax.AXUIElementCreateSystemWide(), 2.0)  # global: covers every child element
    # AXChildren of an exec-started office held only its menu bar (r1-auto macOS run 42748669345, M7 tree):
    # its windows are listed under AXWindows.
    windows = list(attribute(root, "AXWindows", []) or [])
    # Windows only when the app lists them: AXChildren repeats them and adds the menu bar, whose ~1000 items
    # would use up the walk (r1-auto macOS run 42779349486). An app without windows still yields its own children.
    queue, end = (windows or [root]), time.monotonic() + budget
    for _ in range(5000):
        if not queue or time.monotonic() > end:
            break
        node = queue.pop(0)
        yield node
        queue.extend(attribute(node, "AXChildren", []) or [])


# System Events reads HST's modal dialogs where the pyobjc AX walk returned nothing (r1-auto macOS run
# 42474965758, beta5-start.png); the start-up probe (probe/mac-r1-startup) read and clicked them this way.
EVENTS = """
on run argv
tell application "System Events"
  set out to ""
  repeat with p in (every process whose unix id is (item 1 of argv as integer))
    repeat with w in windows of p
      if item 2 of argv is "read" then
        set out to out & "WINDOW: " & (name of w as text) & linefeed
        try
          repeat with t in (value of every static text of w)
            set out to out & (t as text) & linefeed
          end repeat
        end try
      else if exists button (item 2 of argv) of w then
        click button (item 2 of argv) of w
        return "clicked"
      end if
    end repeat
  end repeat
  return out
end tell
end run
"""


def events(app, action):
    import subprocess
    try:
        return subprocess.run(["osascript", "-", str(app.processIdentifier()), action], input=EVENTS,
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def texts(app):
    found = [str(value) for node in nodes(app) for key in ("AXTitle", "AXDescription", "AXValue")
             if isinstance(value := attribute(node, key), str) and value]
    return found + [line for line in events(app, "read").splitlines() if line]


def press(app, names):
    import ApplicationServices as ax
    for node in nodes(app):
        if attribute(node, "AXRole") == "AXButton" and attribute(node, "AXTitle") in names:
            error = ax.AXUIElementPerformAction(node, "AXPress")
            if error:
                raise RuntimeError("Không bấm được nút native")
            return
    for name in sorted(names):
        if events(app, name) == "clicked":
            return
    raise RuntimeError("Không tìm thấy nút: " + ", ".join(names))


def handlers():
    from CoreServices import LSCopyDefaultRoleHandlerForContentType, kLSRolesAll
    app = Path("/Applications/HST Office.app")
    with (app / "Contents/Info.plist").open("rb") as handle:
        expected = plistlib.load(handle)["CFBundleIdentifier"]
    types = {"docx": "org.openxmlformats.wordprocessingml.document",
             "xlsx": "org.openxmlformats.spreadsheetml.sheet",
             "pptx": "org.openxmlformats.presentationml.presentation"}
    return dict(expected=expected, **{name: LSCopyDefaultRoleHandlerForContentType(uti, kLSRolesAll)
                                     for name, uti in types.items()})


CONFIRM = """
on run argv
tell application "System Events"
  repeat with p in (every process whose background only is false or name is "CoreServicesUIAgent")
    repeat with w in windows of p
      try
        set said to (value of every static text of w) as text
        if said contains "HST Office" and (said contains "Internet" or said contains "internet") then
          set labels to {"Open", "Mở"}
          if item 1 of argv is "cancel" then set labels to {"Cancel", "Hủy"}
          repeat with label in labels
            if exists button label of w then
              if item 1 of argv is not "find" then click button label of w
              return (item 1 of argv) & " " & label & " in " & (name of p) & ": " & said
            end if
          end repeat
        end if
      end try
    end repeat
  end repeat
  return ""
end tell
end run
"""


def confirm_download(out):
    """Answer only the ordinary downloaded-app Open prompt, as a user does; never bypass a refusal.

    System Events reaches CoreServicesUIAgent's sheet on the runner where the pyobjc AX walk of
    NSWorkspace's application list does not (r1-auto macOS run 42471573001, M1-startup-failure.png)."""
    import subprocess
    from native import screenshot
    shot = Path(out) / "M1-download-confirmation.png"
    def script(mode):
        try:
            return subprocess.run(["osascript", "-", mode], input=CONFIRM, capture_output=True, text=True,
                                  timeout=30).stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
    if not script("find"):
        return False
    if not shot.exists():
        screenshot(shot)
    answer = script("click")
    with (Path(out) / "os-confirmation.log").open("a", encoding="utf-8") as log:
        log.write(answer + "\n")
    return True


def dismiss_download():
    """Cancel a leftover downloaded-app prompt for HST Office whose process the run already stopped."""
    import subprocess
    try:
        return subprocess.run(["osascript", "-", "cancel"], input=CONFIRM, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def close_owned(pids):
    import psutil
    processes = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            if proc.name().startswith("soffice"):
                proc.terminate()
                processes.append(proc)
        except psutil.NoSuchProcess:
            continue
    _, alive = psutil.wait_procs(processes, timeout=10)
    for proc in alive:
        proc.kill()
    psutil.wait_procs(alive, timeout=5)
