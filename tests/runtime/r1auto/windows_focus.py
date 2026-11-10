# SPDX-License-Identifier: AGPL-3.0-only
"""Bring HST Office to the front on Windows from the tooling process (tooling Python only).

Windows grants the foreground only to the process that produced the last input, so this process presses Alt and
then calls SetForegroundWindow itself (windows_gui.foreground does the same); soffice's own toFront() was refused
(real keys reached the desktop: r1-auto Windows run 42744370109, W5/W7)."""
import ctypes
from ctypes import wintypes
import time


def office_windows():
    """[(hwnd, title)] of visible, enabled top-level windows of soffice.bin; a modal dialog is the enabled one."""
    import psutil
    user32, found = ctypes.windll.user32, []
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if user32.IsWindowVisible(hwnd) and user32.IsWindowEnabled(hwnd):
            try:
                name = psutil.Process(pid.value).name().lower()
            except Exception:
                name = ""
            if name.startswith("soffice"):
                buffer = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buffer, 512)
                if buffer.value:
                    found.append((hwnd, buffer.value))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def foreground(title=""):
    from native import keyboard
    user32 = ctypes.windll.user32
    notice = user32.FindWindowW("#32770", "System Properties")  # the runner's paging-file notice pops up mid-run
    if notice:
        user32.PostMessageW(notice, 0x0010, 0, 0)  # WM_CLOSE
        time.sleep(0.5)
    windows = office_windows()
    target = next((w for w in windows if title and title in w[1]), windows[0] if windows else None)
    if target is None:
        return dict(ok=False, windows=[])
    if user32.GetForegroundWindow() != target[0]:
        keyboard(["alt"])
        user32.ShowWindow(target[0], 5)
        user32.SetForegroundWindow(target[0])
        time.sleep(0.5)
    return dict(ok=user32.GetForegroundWindow() == target[0], title=target[1], windows=[t for _, t in windows])
