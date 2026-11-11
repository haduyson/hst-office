# SPDX-License-Identifier: AGPL-3.0-only
"""Win32 helpers of hst_session_probe.py: the office's own top-level windows, raising them for a screenshot and
closing its dialogs. Only soffice.bin windows are touched."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import time

user32 = ctypes.windll.user32


def office_windows():
    """[(title, width, height)] of visible soffice top-level windows."""
    found = []
    names = {p.lower() for p in ("soffice.bin", "soffice.exe")}

    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if process_name(pid.value) in names:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            buffer = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buffer, 512)
            found.append((buffer.value, rect.right - rect.left, rect.bottom - rect.top))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def process_name(pid):
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buffer, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return os.path.basename(buffer.value).lower()
    finally:
        kernel.CloseHandle(handle)


def running_offices():
    done = subprocess.run(["tasklist", "/FI", "IMAGENAME eq soffice.bin", "/FO", "CSV", "/NH"], capture_output=True, text=True)
    return [line for line in done.stdout.splitlines() if "soffice.bin" in line.lower()]


def office_hwnds():
    found = []

    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if user32.IsWindowVisible(hwnd) and process_name(pid.value) == "soffice.bin":
            found.append(hwnd)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def set_topmost(on):
    """An office started from a task cannot take the foreground, and the user's windows may cover it: only the office's
    own windows are lifted (topmost, not activated) for the screenshot and put back right after. Bottom first, so
    dialogs stay above their document."""
    flags = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
    hwnds = office_hwnds()
    for hwnd in reversed(hwnds):
        user32.SetWindowPos(hwnd, -1 if on else -2, 0, 0, 0, 0, flags)
    time.sleep(0.8)
    return len(hwnds)


def dismiss_dialogs():
    """WM_CLOSE (the title bar X: cancel, nothing is sent) to office windows that are not documents; an open modal
    dialog vetoes terminate(), and a killed office leaves the session marker that asks for a crash report."""
    closed = []

    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if user32.IsWindowVisible(hwnd) and process_name(pid.value) == "soffice.bin":
            buffer = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buffer, 512)
            if buffer.value and " \u2014 HST" not in buffer.value and " - HST" not in buffer.value:
                closed.append(buffer.value)
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    time.sleep(1.5 if closed else 0)
    return closed
