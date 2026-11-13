# SPDX-License-Identifier: AGPL-3.0-only
"""Win32 side of check-recovery-kill-windows.py: the recovery dialog of our own office process, a click on one of its
buttons (only when nothing covers it) and a desktop screenshot for evidence."""
import ctypes
import re
import subprocess
import time


def find_window(pattern, pids=None):
    user32, found = ctypes.windll.user32, []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, _):
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, 512)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if user32.IsWindowVisible(hwnd) and re.search(pattern, buffer.value) and (pids is None or pid.value in pids):
            found.append(hwnd)
        return True
    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def press_enter(hwnd, from_right=260, from_bottom=26):
    """Click a button of the recovery dialog by its place from the bottom right (Return would only toggle the
    focused list row): 260 = "Khôi phục mục đã chọn" / "Recover Selected", 200 = "Kết thúc" / "Finish"."""
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetAncestor.restype = wintypes.HWND
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    scale = user32.GetDpiForWindow(hwnd) / 96.0 if hasattr(user32, "GetDpiForWindow") else 1.0
    point = wintypes.POINT(int(rect.right - from_right * scale), int(rect.bottom - from_bottom * scale))
    hit = user32.WindowFromPoint(point)
    if user32.GetAncestor(hit, 2) != hwnd:  # GA_ROOT: another window covers the dialog; never click into it
        print("recovery dialog is covered by another window: not clicked", flush=True)
        return False
    user32.SetCursorPos(point.x, point.y)
    user32.mouse_event(0x2, 0, 0, 0, 0)
    user32.mouse_event(0x4, 0, 0, 0, 0)
    return True


def shot(path):
    """Screenshot of the desktop (evidence when a recovery check fails)."""
    script = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $b=[System.Windows.Forms.Screen]::PrimaryScreen"
              ".Bounds; $i=New-Object System.Drawing.Bitmap $b.Width,$b.Height; [System.Drawing.Graphics]::FromImage($i)"
              ".CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size); $i.Save('%s')" % path)
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
