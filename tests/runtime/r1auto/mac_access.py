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


def confirm_download(out):
    """Confirm only the ordinary downloaded-app Open prompt; never bypass a refusal."""
    from AppKit import NSWorkspace
    from native import screenshot
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() not in {"com.apple.CoreServicesUIAgent", "com.apple.finder"}:
            continue
        labels = texts(app)
        combined = " ".join(labels)
        if "HST Office" not in combined or not any(word in combined for word in ("internet", "Internet", "tải")):
            continue
        buttons = [attribute(node, "AXTitle") for node in nodes(app) if attribute(node, "AXRole") == "AXButton"]
        if not set(buttons) & {"Open", "Mở"}:
            continue
        screenshot(Path(out) / "M1-download-confirmation.png")
        press(app, {"Open", "Mở"})
        return True
    return False


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
