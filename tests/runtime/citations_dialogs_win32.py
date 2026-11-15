# SPDX-License-Identifier: AGPL-3.0-only
"""Windows driver of check-citations-dialogs.py (stdlib ctypes only, so HST's bundled Python runs it).

Runs in the tester's own Windows session (a disconnected one is fine: see citations-dialogs-own-session.ps1), never
the console user's. Such a session has no input desktop, so SendInput is refused (ERROR_ACCESS_DENIED, checked on
HST4). Keys therefore go to the office window as the keyboard messages Windows itself would deliver: the window's
thread input is attached, it gets the keyboard focus, the modifier state is set with SetKeyboardState (VCL reads
Shift/Ctrl/Alt with GetKeyState) and WM_KEYDOWN/WM_SYSKEYDOWN/…UP are posted; VCL's own message loop translates and
dispatches them, accelerators (Alt+Shift+I) included. Screenshots: PrintWindow(PW_RENDERFULLCONTENT) to a PNG.
"""
import ctypes
from ctypes import wintypes
import os
import struct
import time
import zlib

user32, gdi32, kernel32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
VK = {"tab": 0x09, "return": 0x0D, "escape": 0x1B, "space": 0x20, "shift": 0x10, "ctrl": 0x11, "alt": 0x12}
MODIFIERS = ("shift", "ctrl", "alt")
OFFICE = {"soffice.bin", "soffice.exe"}
HANDLE = ctypes.c_void_p
for _f, _res, _args in (
        (user32.GetWindowThreadProcessId, wintypes.DWORD, (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))),
        (user32.PostMessageW, wintypes.BOOL, (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        (user32.SetFocus, wintypes.HWND, (wintypes.HWND,)),
        (user32.IsWindowVisible, wintypes.BOOL, (wintypes.HWND,)),
        (user32.GetWindowTextW, ctypes.c_int, (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)),
        (user32.GetWindowRect, wintypes.BOOL, (wintypes.HWND, ctypes.POINTER(wintypes.RECT))),
        (user32.PrintWindow, wintypes.BOOL, (wintypes.HWND, HANDLE, wintypes.UINT)),
        (user32.GetDC, HANDLE, (wintypes.HWND,)),
        (user32.ReleaseDC, ctypes.c_int, (wintypes.HWND, HANDLE)),
        (gdi32.CreateCompatibleDC, HANDLE, (HANDLE,)),
        (gdi32.CreateCompatibleBitmap, HANDLE, (HANDLE, ctypes.c_int, ctypes.c_int)),
        (gdi32.SelectObject, HANDLE, (HANDLE, HANDLE)),
        (gdi32.DeleteObject, wintypes.BOOL, (HANDLE,)),
        (gdi32.DeleteDC, wintypes.BOOL, (HANDLE,)),
        (gdi32.GetDIBits, ctypes.c_int, (HANDLE, HANDLE, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                         ctypes.c_void_p, wintypes.UINT)),
        (kernel32.OpenProcess, HANDLE, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)),
        (kernel32.CloseHandle, wintypes.BOOL, (HANDLE,)),
        (kernel32.QueryFullProcessImageNameW, wintypes.BOOL, (HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                             ctypes.POINTER(wintypes.DWORD)))):
    _f.restype, _f.argtypes = _res, _args  # 64-bit handles and lParam values must not be truncated to int


def _process_name(pid):
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buffer, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return os.path.basename(buffer.value).lower() if ok else ""
    finally:
        kernel32.CloseHandle(handle)


def office_windows():
    """[(hwnd, title)] of the visible top-level office windows on this session's desktop, front to back."""
    found = []

    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if _process_name(pid.value) in OFFICE:
                buffer = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buffer, 512)
                found.append((hwnd, buffer.value))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def _png(path, width, height, bgra):
    out = bytearray()  # 8-bit RGB rows, each with filter byte 0; the DIB rows are BGRA
    for y in range(height):
        line = bgra[y * width * 4:(y + 1) * width * 4]
        out += b"\0" + bytes(b for px in range(width) for b in (line[px * 4 + 2], line[px * 4 + 1], line[px * 4]))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(out), 6)) + chunk(b"IEND", b""))


class Win32Driver:
    def wait_window(self, title, timeout=25):
        deadline = time.time() + timeout
        while time.time() < deadline:
            found = [hwnd for hwnd, name in office_windows() if name == title]
            if found:
                return found[0]
            time.sleep(0.5)
        return None

    def document_window(self):
        found = [hwnd for hwnd, name in office_windows() if "HST Writer" in name]
        return found[0] if found else None

    def size(self, window):
        rect = wintypes.RECT()
        user32.GetWindowRect(window, ctypes.byref(rect))
        return rect.right - rect.left, rect.bottom - rect.top

    def screenshot(self, window, path):
        width, height = self.size(window)
        screen = user32.GetDC(None)
        memory, bitmap = gdi32.CreateCompatibleDC(screen), gdi32.CreateCompatibleBitmap(screen, width, height)
        old = gdi32.SelectObject(memory, bitmap)
        try:
            user32.PrintWindow(window, memory, 2)  # PW_RENDERFULLCONTENT
            header = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)  # top-down
            pixels = ctypes.create_string_buffer(width * height * 4)
            gdi32.GetDIBits(memory, bitmap, 0, height, pixels, ctypes.create_string_buffer(header, 44), 0)
            _png(path, width, height, pixels.raw)
        finally:
            gdi32.SelectObject(memory, old)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory)
            user32.ReleaseDC(None, screen)

    def keys(self, window, *keys):
        """The X11 driver's key names ("Tab", "space", "Escape", "Return", "alt+shift+i"), posted to ``window`` only
        (never the foreground window), which must be an HST Office window."""
        import windows_gui_guard as guard
        if not guard.is_ours(window):
            raise guard.BlockedInput("keys %r not posted: %#x is not an HST Office window" % (keys, window or 0))
        thread = user32.GetWindowThreadProcessId(window, None)
        mine = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(mine, thread, True)
        try:
            user32.SetFocus(window)
            for key in keys:
                self._chord(window, key.lower().split("+"))
                time.sleep(0.15)
        finally:
            self._modifiers(())
            user32.AttachThreadInput(mine, thread, False)

    def _modifiers(self, held):
        state = (ctypes.c_ubyte * 256)()
        user32.GetKeyboardState(state)
        for name in MODIFIERS:
            state[VK[name]] = 0x80 if name in held else 0
        user32.SetKeyboardState(state)

    def _chord(self, window, parts):
        held, name = [p for p in parts if p in MODIFIERS], parts[-1]
        vk = VK.get(name) or ord(name.upper())
        scan = user32.MapVirtualKeyW(vk, 0)
        alt = "alt" in held
        down, up = (WM_SYSKEYDOWN, WM_SYSKEYUP) if alt else (WM_KEYDOWN, WM_KEYUP)
        context = 1 << 29 if alt else 0
        self._modifiers(held)
        user32.PostMessageW(window, down, vk, 1 | scan << 16 | context)
        time.sleep(0.2)  # VCL reads the modifier state while it handles the message
        user32.PostMessageW(window, up, vk, 1 | scan << 16 | context | 3 << 30)
        time.sleep(0.2)
        self._modifiers(())
