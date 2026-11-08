# SPDX-License-Identifier: AGPL-3.0-only
"""Native macOS Accessibility and LaunchServices observations (tooling Python)."""
import plistlib
from pathlib import Path
import time


def applications():
    from AppKit import NSWorkspace
    return [app for app in NSWorkspace.sharedWorkspace().runningApplications()
            if app.bundleURL() and app.bundleURL().lastPathComponent() == "HST Office.app"]


def attribute(element, name, default=None):
    import ApplicationServices as ax
    error, value = ax.AXUIElementCopyAttributeValue(element, name, None)
    return value if error == 0 else default


def nodes(app, budget=15.0):
    """Breadth-first AX walk; a busy app answers each call within 2 s and the walk within `budget` s."""
    import ApplicationServices as ax
    root = ax.AXUIElementCreateApplication(app.processIdentifier())
    ax.AXUIElementSetMessagingTimeout(ax.AXUIElementCreateSystemWide(), 2.0)  # global: covers every child element
    queue, end = [root], time.monotonic() + budget
    for _ in range(5000):
        if not queue or time.monotonic() > end:
            break
        node = queue.pop(0)
        yield node
        queue.extend(attribute(node, "AXChildren", []) or [])


def texts(app):
    return [str(value) for node in nodes(app) for key in ("AXTitle", "AXDescription", "AXValue")
            if isinstance(value := attribute(node, key), str) and value]


def press(app, names):
    import ApplicationServices as ax
    for node in nodes(app):
        if attribute(node, "AXRole") == "AXButton" and attribute(node, "AXTitle") in names:
            error = ax.AXUIElementPerformAction(node, "AXPress")
            if error:
                raise RuntimeError("Không bấm được nút native")
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
          repeat with label in {"Open", "Mở"}
            if exists button label of w then
              if item 1 of argv is "click" then click button label of w
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
