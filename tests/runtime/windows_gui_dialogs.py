# SPDX-License-Identifier: AGPL-3.0-only
"""The office's dialogs for the Windows GUI checks: list them over UNO and close them without a single key.

A dialog is closed with WM_CLOSE posted to its own HWND (the title bar X: the dialog cancels), never with Escape or
Alt+F4 into whatever window has the focus. endExecute is only the fallback for a dialog that ignored WM_CLOSE (it
ended the office for the page style dialogs)."""
import time

import windows_gui_guard as guard
from windows_gui_input import screenshot
from windows_gui_win32 import office_windows

SYSTEM_WIN32 = 1  # com.sun.star.lang.SystemDependent.SYSTEM_WIN32


def window_title(window):
    for getter in (lambda w: w.getTitle(), lambda w: w.getAccessibleContext().getAccessibleName()):
        try:
            value = getter(window)
            if value:
                return value
        except Exception:  # noqa: BLE001
            continue
    return ""


def dialogs(office):
    """[(window, title)] of the office's shown dialogs and message boxes: every shown top window that is not the
    container window of a frame (Start Center, documents; those may be titled "HST Office" as well)."""
    try:
        frames = office.desktop.getFrames()
        containers = [frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount())]
    except Exception:  # noqa: BLE001 - frames come and go while the office starts
        containers = []
    found = []
    for window in office.top_windows():
        try:
            if any(window == other for other in containers) or not window.isVisible():
                continue
            found.append((window, window_title(window)))
        except Exception:  # noqa: BLE001 - disposed while we looked
            continue
    return found


def dialog_hwnd(window):
    """Win32 handle of a UNO top window: its peer's XSystemDependentWindowPeer.getWindowHandle, else the one office
    window with the same title (None when there is none or several: a guess must not close a document)."""
    try:
        import uno
        handle = window.getWindowHandle(uno.ByteSequence(bytes(16)), SYSTEM_WIN32)
        if handle:
            return int(handle)
    except Exception:  # noqa: BLE001 - no peer interface, or disposed
        pass
    title = window_title(window)
    matches = [w[0] for w in office_windows() if title and w[2] == title]
    return matches[0] if len(matches) == 1 else None


def close_hwnd(hwnd, timeout=5.0):
    """Post WM_CLOSE to the office window `hwnd` and wait until it is gone; False when it is not ours or stayed."""
    return bool(hwnd) and guard.close_window(hwnd) and guard.wait_gone(hwnd, timeout)


def close_dialog(window, timeout=5.0):
    """End a dialog: WM_CLOSE to its own HWND, endExecute only when that did not close it. Never sends a key.
    Returns how it was closed ("wm_close", "endExecute") or "open" when neither worked."""
    hwnd = dialog_hwnd(window)
    if hwnd and close_hwnd(hwnd, timeout):
        return "wm_close"
    try:
        window.endExecute()
        return "endExecute"
    except Exception:  # noqa: BLE001 - not an XDialog (a message box ignores endExecute too)
        return "open"


def dismiss_startup(office, shot_path, timeout=40, settle=8):
    """Close the dialogs a start shows (the HST welcome, any core start-up dialog) so a check can drive the office.
    Waits up to `timeout` for the first one, then `settle` seconds for more. Returns their titles (screenshot of the
    first one at `shot_path`)."""
    seen, deadline = [], time.time() + timeout
    while time.time() < deadline:
        for window, title in dialogs(office):
            if not seen:
                time.sleep(1.5)
                screenshot(shot_path)
            seen.append(title)
            close_dialog(window)
            deadline = min(deadline, time.time() + settle)
        time.sleep(0.5)
    return seen
