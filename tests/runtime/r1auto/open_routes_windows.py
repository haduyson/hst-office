# SPDX-License-Identifier: AGPL-3.0-only
"""Windows side of W16 (tooling Python only): window/process census, window control, hang dumps and launches.

Routes are driven the way a person does it by open_routes_explorer.py. The census
lists top-level windows in z-order, so "the document window exists but sits behind Explorer" is visible in data."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import time

user32 = ctypes.windll.user32
OFFICE = ("soffice.bin", "soffice.exe")
WM_CLOSE = 0x0010


def _name(pid):
    """Process name now (no cache: Windows reuses process ids within a run)."""
    import psutil
    try:
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


def _text(hwnd, getter=user32.GetWindowTextW):
    buffer = ctypes.create_unicode_buffer(512)
    getter(hwnd, buffer, 512)
    return buffer.value


def census():
    """Visible top-level windows, topmost first: office ones in full, the rest only when they are above an office
    window or are Explorer / Open-with windows (the windows that can hide a document)."""
    rows = []
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            rows.append(dict(hwnd=hwnd, pid=pid.value, proc=_name(pid.value), cls=_text(hwnd, user32.GetClassNameW),
                             title=_text(hwnd), enabled=bool(user32.IsWindowEnabled(hwnd)),
                             owner=user32.GetWindow(hwnd, 4) or 0, iconic=bool(user32.IsIconic(hwnd)),
                             rect=[rect.left, rect.top, rect.right, rect.bottom]))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    for rank, row in enumerate(rows):
        row["z"] = rank
    last_office = max([r["z"] for r in rows if r["proc"] in OFFICE] or [-1])
    keep = [r for r in rows if r["proc"] in OFFICE or r["cls"] in ("CabinetWClass", "#32768")
            or r["proc"] == "openwith.exe" or (r["z"] < last_office and r["title"])]
    return keep, foreground()


def foreground():
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return dict(hwnd=hwnd, proc=_name(pid.value), title=_text(hwnd))


def processes(attrs):
    """[(Process, info)] of every process. psutil.process_iter(attrs) stores `info` on Process objects it shares
    between threads, so the Launches thread and the census would overwrite each other's: read our own copy."""
    import psutil
    found = []
    for proc in psutil.process_iter():
        try:
            found.append((proc, proc.as_dict(attrs=attrs)))
        except psutil.Error:
            pass
    return found


def office_processes():
    found = []
    for proc, info in processes(["pid", "ppid", "name", "cmdline", "create_time", "status"]):
        if (info["name"] or "").lower() in OFFICE:
            try:
                cpu = sum(proc.cpu_times()[:2])
                threads = proc.num_threads()
            except Exception:
                cpu, threads = None, None
            found.append(dict(pid=info["pid"], ppid=info["ppid"], name=info["name"],
                              status=info["status"], cpu=cpu, threads=threads,
                              cmdline=" ".join(info["cmdline"] or [])[:300]))
    return found


def press_alt():
    from native import keyboard
    keyboard(["alt"])


def bring_to_front(hwnd):
    """Windows gives the foreground to the process with the last input: press Alt here, then ask for it."""
    press_alt()
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    return user32.GetForegroundWindow() == hwnd


def close_windows(hwnds):
    for hwnd in hwnds:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def dismiss_system_notices():
    notice = user32.FindWindowW("#32770", "System Properties")  # the runner's paging-file notice
    if notice:
        user32.PostMessageW(notice, WM_CLOSE, 0, 0)


def minidump(pid, path):
    """A small dump (threads and their stacks) of a process that shows no window, for print-office-crashes.ps1."""
    kernel32, dbghelp = ctypes.windll.kernel32, ctypes.windll.dbghelp
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CreateFileW.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x0410 | 0x0040, False, pid)  # QUERY_INFORMATION | VM_READ | DUP_HANDLE
    if not process:
        return dict(pid=pid, error=ctypes.GetLastError())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = kernel32.CreateFileW(str(path), 0x40000000, 0, None, 2, 0x80, None)  # GENERIC_WRITE, CREATE_ALWAYS
    try:
        # MiniDumpWithDataSegs | WithHandleData | WithUnloadedModules | WithThreadInfo
        ok = dbghelp.MiniDumpWriteDump(process, pid, handle, 0x1 | 0x4 | 0x20 | 0x1000, None, None, None)
        return dict(pid=pid, dump=Path(path).name, ok=bool(ok))
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))
        kernel32.CloseHandle(wintypes.HANDLE(process))


class Launches:
    """Every launcher and office process seen during a route, polled every 50 ms in a thread: a launcher that hands
    the file to a running (or exiting) office lives well under the census interval."""
    NAMES = ("scalc.exe", "swriter.exe", "simpress.exe", "soffice.exe", "soffice.bin")

    def __init__(self):
        import threading
        self.seen, self.stop = {}, threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.start = time.monotonic()

    def _run(self):
        while not self.stop.is_set():
            now = round(time.monotonic() - self.start, 2)
            alive = set()
            for _, info in processes(["pid", "ppid", "name", "create_time"]):
                if (info["name"] or "").lower() in self.NAMES:
                    key = (info["pid"], info["create_time"])
                    alive.add(key)
                    self.seen.setdefault(key, dict(pid=key[0], ppid=info["ppid"], name=info["name"],
                                                   first=now, last=now))["last"] = now
            for key, value in self.seen.items():
                if key not in alive and "gone" not in value:
                    value["gone"] = now
            self.stop.wait(0.05)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(5)

    def report(self):
        return sorted(self.seen.values(), key=lambda v: v["first"])

    def launched(self, timeout):
        """Whether a launcher or office process started after the route began (a process running before it, e.g.
        the office that is closing, is seen at 0.0), waiting up to `timeout` seconds."""
        end = time.monotonic() + timeout
        while True:
            if any(value["first"] > 0 for value in list(self.seen.values())):
                return True
            if time.monotonic() >= end:
                return False
            time.sleep(0.1)
