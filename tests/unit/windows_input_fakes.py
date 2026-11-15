# SPDX-License-Identifier: AGPL-3.0-only
"""Fakes for the Windows harness input gate: a desktop of windows (class, title, process) with a foreground window,
and a stand-in windows_gui_win32 module whose user32 records every SendInput, so tests on any platform can prove
which keys would have reached which window."""
import os
import sys
import types

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

DESKTOP, SHELL, TRAY, SHUTDOWN, EXPLORER = 0x10, 0x20, 0x30, 0x40, 0x50
DOC, DIALOG, OTHER_OFFICE, FOREIGN_SAL = 0x100, 0x200, 0x300, 0x400
OFFICE_PID, OTHER_OFFICE_PID, EXPLORER_PID, FOREIGN_PID = 41, 42, 7, 9


class FakeApi:
    """The windows_gui_guard api over a dict of windows; `foreground_window` is what GetForegroundWindow returns."""

    def __init__(self, foreground_window=DOC):
        self.windows = {
            DESKTOP: ("#32769", "", EXPLORER_PID), SHELL: ("Progman", "Program Manager", EXPLORER_PID),
            TRAY: ("Shell_TrayWnd", "", EXPLORER_PID), SHUTDOWN: ("#32770", "Shut Down Windows", EXPLORER_PID),
            EXPLORER: ("CabinetWClass", "Tài liệu", EXPLORER_PID), 0x60: ("WorkerW", "", EXPLORER_PID),
            DOC: ("SALFRAME", "Tài liệu1 - HST Writer", OFFICE_PID), DIALOG: ("SALSUBFRAME", "Tùy chọn", OFFICE_PID),
            OTHER_OFFICE: ("SALFRAME", "Bảng tính1 - HST Sheets", OTHER_OFFICE_PID),
            FOREIGN_SAL: ("SALFRAME", "Untitled 1", FOREIGN_PID)}
        self.images = {OFFICE_PID: r"C:\Program Files\HST Office\program\soffice.bin",
                       OTHER_OFFICE_PID: r"D:\hst-test\office\program\soffice.bin",
                       EXPLORER_PID: r"C:\Windows\explorer.exe", FOREIGN_PID: r"C:\Other\program\other.bin"}
        self.foreground_window = foreground_window
        self.under_pointer = DOC
        self.posted, self.grants = [], set()
        self.closed_on_post = True

    def foreground(self):
        return self.foreground_window

    def shell_window(self):
        return SHELL

    def desktop_window(self):
        return DESKTOP

    def class_name(self, hwnd):
        return self.windows.get(hwnd, ("", "", 0))[0]

    def title(self, hwnd):
        return self.windows.get(hwnd, ("", "", 0))[1]

    def pid(self, hwnd):
        return self.windows.get(hwnd, ("", "", 0))[2]

    def image(self, pid):
        return self.images.get(pid, "")

    def thread_of(self, hwnd):
        return hwnd + 1 if hwnd else 0

    def root(self, hwnd):
        return hwnd

    def window_from_point(self, x, y):
        return self.under_pointer

    def show(self, hwnd):
        pass

    def set_foreground(self, hwnd):
        if hwnd in self.grants:
            self.foreground_window = hwnd
        return hwnd in self.grants

    def bring_to_top(self, hwnd):
        pass

    def attach(self, thread, attach):
        pass

    def post(self, hwnd, message):
        self.posted.append((hwnd, message))
        if self.closed_on_post:
            self.windows.pop(hwnd, None)
        return True

    def alive(self, hwnd):
        return hwnd in self.windows

    def sleep(self, seconds):
        pass


class FakeUser32:
    """Records SendInput calls as (foreground window at the time, [(vk, key-up?)])."""

    def __init__(self, api):
        self.api, self.sent, self.after_send = api, [], None

    def SendInput(self, count, array, size):  # noqa: N802 - the user32 name
        events = [(array[i].u.ki.wVk, bool(array[i].u.ki.dwFlags & 2)) if array[i].type == 1 else ("mouse",)
                  for i in range(count)]
        self.sent.append((self.api.foreground_window, events))
        if self.after_send:
            self.after_send(self)
        return count

    def SetProcessDPIAware(self):  # noqa: N802
        return 1

    def GetSystemMetrics(self, index):  # noqa: N802
        return 1920 if index == 0 else 1080

    def GetCursorPos(self, pointer):  # noqa: N802
        return 1

    def GetForegroundWindow(self):  # noqa: N802
        return self.api.foreground_window


def install(api):
    """Load windows_gui_guard/_input/_dialogs against `api` and a recording user32; returns (guard, input, dialogs,
    user32). Fresh modules each time, so one test's state never leaks into the next."""
    for name in ("windows_gui_guard", "windows_gui_input", "windows_gui_dialogs", "windows_gui_win32", "windows_gui_office",
                 "windows_gui_processes"):
        sys.modules.pop(name, None)
    user32 = FakeUser32(api)
    win32 = types.ModuleType("windows_gui_win32")
    win32.user32 = user32
    win32.window_rect = lambda hwnd: (100, 100, 900, 700)
    win32.office_windows = lambda: [(h, c, t, (0, 0, 1, 1)) for h, (c, t, p) in api.windows.items()
                                    if c.startswith("SAL")]
    sys.modules["windows_gui_win32"] = win32
    import windows_gui_guard as guard
    guard._API[:] = [api]
    import windows_gui_dialogs as dialogs
    import windows_gui_input as gui_input
    gui_input.time = types.SimpleNamespace(sleep=lambda seconds: None)  # this module's binding only
    return guard, gui_input, dialogs, user32
