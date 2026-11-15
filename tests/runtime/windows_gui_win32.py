# SPDX-License-Identifier: AGPL-3.0-only
"""Win32 window queries for the Windows GUI checks (ctypes; importable on Windows only): the office's top-level
windows, their rectangles, and the `Win32` api object windows_gui_guard decides on."""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetShellWindow.restype = wintypes.HWND
user32.GetDesktopWindow.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = (wintypes.POINT,)
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
kernel32.OpenProcess.restype = wintypes.HANDLE


class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _text(getter, hwnd, size=512):
    buffer = ctypes.create_unicode_buffer(size)
    getter(hwnd, buffer, size)
    return buffer.value


class Win32:
    """The handful of user32/kernel32 calls windows_gui_guard needs (HWNDs as ints, 0 for none)."""

    def foreground(self):
        return user32.GetForegroundWindow() or 0

    def shell_window(self):
        return user32.GetShellWindow() or 0

    def desktop_window(self):
        return user32.GetDesktopWindow() or 0

    def class_name(self, hwnd):
        return _text(user32.GetClassNameW, hwnd, 256)

    def title(self, hwnd):
        return _text(user32.GetWindowTextW, hwnd)

    def pid(self, hwnd):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def thread_of(self, hwnd):
        return user32.GetWindowThreadProcessId(hwnd, None)

    def image(self, pid):
        """Full path of process `pid`'s executable ("" when it cannot be opened)."""
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
            return buffer.value if ok else ""
        finally:
            kernel32.CloseHandle(handle)

    def root(self, hwnd):
        return (user32.GetAncestor(hwnd, 2) or 0) if hwnd else 0  # GA_ROOT

    def window_from_point(self, x, y):
        return user32.WindowFromPoint(wintypes.POINT(x, y)) or 0

    def show(self, hwnd):
        user32.ShowWindow(hwnd, 5)  # SW_SHOW

    def set_foreground(self, hwnd):
        return bool(user32.SetForegroundWindow(hwnd))

    def bring_to_top(self, hwnd):
        user32.BringWindowToTop(hwnd)

    def attach(self, thread, attach):
        if thread and thread != kernel32.GetCurrentThreadId():
            user32.AttachThreadInput(kernel32.GetCurrentThreadId(), thread, bool(attach))

    def post(self, hwnd, message):
        return bool(user32.PostMessageW(hwnd, message, 0, 0))

    def alive(self, hwnd):
        return bool(user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd))

    def sleep(self, seconds):
        time.sleep(seconds)


def office_windows():
    """[(hwnd, class name, title, (left, top, right, bottom))] of the visible top-level VCL windows (class SAL*)."""
    found = []

    def visit(hwnd, _param):
        if not user32.IsWindowVisible(hwnd):
            return True
        name = _text(user32.GetClassNameW, hwnd, 256)
        if name.startswith("SAL"):
            found.append((hwnd, name, _text(user32.GetWindowTextW, hwnd), window_rect(hwnd)))
        return True
    user32.EnumWindows(_ENUM(visit), 0)
    return found


def find_window(predicate, timeout=30):
    """First office window whose title satisfies `predicate`, polled until `timeout`; None when none appeared."""
    deadline = time.time() + timeout
    while True:
        for window in office_windows():
            if predicate(window[2]):
                return window
        if time.time() > deadline:
            return None
        time.sleep(0.5)


def hwnd_of(title, timeout=10):
    """Win32 handle of the office window titled `title` (for screen coordinates and foreground)."""
    window = find_window(lambda name: name == title, timeout)
    return window[0] if window else None


def window_rect(hwnd):
    rect = _Rect()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def client_origin(hwnd):
    """Screen position of the window's client area (VCL child positions are relative to it)."""
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    return point.x, point.y
