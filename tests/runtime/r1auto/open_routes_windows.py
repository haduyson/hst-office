# SPDX-License-Identifier: AGPL-3.0-only
"""Windows side of W16 (tooling Python only): window/process census, Explorer input and ShellExecuteEx.

Every route is driven the way a person does it: an Explorer window with the file selected, a real double click, a
real right click and a click on the context-menu entry (pywinauto UIA reads the menu, SendInput clicks). The census
lists top-level windows in z-order, so "the document window exists but sits behind Explorer" is visible in data."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
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


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def shell_execute(path, verb):
    """ShellExecuteEx with the verb name (None: the default verb, as Enter in Explorer). Returns how long the call
    itself took and the launched process id (the launcher, soffice.exe), or the error."""
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x400  # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
    info.lpVerb, info.lpFile, info.nShow = verb, str(path), 1
    started = time.monotonic()
    ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
    detail = dict(call_seconds=round(time.monotonic() - started, 2), ok=bool(ok))
    if not ok:
        detail["error"] = ctypes.GetLastError()
    elif info.hProcess:
        detail["pid"] = ctypes.windll.kernel32.GetProcessId(info.hProcess)
        ctypes.windll.kernel32.CloseHandle(info.hProcess)
    return detail


class Explorer:
    """One Explorer window showing a folder, the given file selected."""

    def __init__(self, path):
        self.path = Path(path)
        self.window = None

    def open(self, timeout=30):
        from pywinauto import Desktop
        before = {w.handle for w in Desktop(backend="uia").windows(class_name="CabinetWClass")}
        subprocess.Popen(["explorer.exe", "/select," + str(self.path)])
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            fresh = [w for w in Desktop(backend="uia").windows(class_name="CabinetWClass") if w.handle not in before]
            if fresh:
                self.window = fresh[0]
                time.sleep(1.5)  # the view fills its items after the frame shows
                return self
            time.sleep(0.3)
        raise TimeoutError("Explorer không mở thư mục chứa tệp")

    def item(self):
        bring_to_front(self.window.handle)
        stem = self.path.stem
        end = time.monotonic() + 15
        while time.monotonic() < end:
            items = [i for i in self.window.descendants(control_type="ListItem")
                     if i.window_text() in (self.path.name, stem)]
            if items:
                return items[0]
            time.sleep(0.5)
        raise LookupError("Không thấy tệp trong Explorer: " + self.path.name)

    def center(self):
        rect = self.item().rectangle()
        return (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2

    def double_click(self):
        from pywinauto import mouse
        x, y = self.center()
        mouse.double_click(coords=(x, y))
        return dict(at=[x, y])

    def context_menu(self):
        from pywinauto import mouse
        x, y = self.center()
        mouse.click(coords=(x, y))
        time.sleep(0.4)
        mouse.right_click(coords=(x, y))
        return self._menu_items(timeout=10)

    @staticmethod
    def _menu_items(timeout=5, exclude=()):
        from pywinauto import Desktop
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            menus = [m for m in Desktop(backend="uia").windows(class_name="#32768") if m.handle not in exclude]
            items = [i for m in menus for i in m.descendants(control_type="MenuItem")]
            if items:
                return menus, items
            time.sleep(0.3)
        raise TimeoutError("Menu chuột phải không hiện")

    def choose(self, label):
        """Right click, then the entry whose text is `label` (the shell's own "Open")."""
        menus, items = self.context_menu()
        names = [i.window_text() for i in items]
        target = next((i for i in items if i.window_text().replace("&", "") == label), None)
        if target is None:
            raise LookupError(f"Menu không có mục {label}: {names}")
        target.click_input()
        return dict(menu=names, chose=label)

    def open_with(self, wanted):
        """Right click ▸ Open with ▸ the entry naming `wanted` (submenu), or the same app in the Open-with dialog when
        the shell shows a dialog instead of a submenu."""
        menus, items = self.context_menu()
        names = [i.window_text() for i in items]
        entry = next((i for i in items if i.window_text().replace("&", "").lower().startswith("open with")), None)
        if entry is None:
            raise LookupError("Menu không có mục Open with: %s" % names)
        entry.click_input()
        time.sleep(1.5)
        try:
            _, sub = self._menu_items(timeout=3, exclude={m.handle for m in menus})
        except TimeoutError:
            sub = []
        subnames = [i.window_text() for i in sub]
        if sub:
            target = next((i for i in sub if wanted.lower() in i.window_text().lower()), None) or \
                next((i for i in sub if "hst" in i.window_text().lower()), None)
            if target is None:
                raise LookupError("Open with không có %s: %s" % (wanted, subnames))
            chose = target.window_text()
            target.click_input()
            return dict(menu=names, open_with=subnames, chose=chose)
        return dict(menu=names, open_with=[], **self._open_with_dialog(wanted))

    @staticmethod
    def _open_with_dialog(wanted, timeout=15):
        from pywinauto import Desktop
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for window in Desktop(backend="uia").windows():
                if _name(window.process_id()) != "openwith.exe":
                    continue
                entries = window.descendants(control_type="ListItem")
                names = [e.window_text() for e in entries]
                target = next((e for e in entries if wanted.lower() in e.window_text().lower()), None) or \
                    next((e for e in entries if "hst" in e.window_text().lower()), None)
                if target is None:
                    raise LookupError("Hộp Open with không có %s: %s" % (wanted, names))
                target.click_input()
                time.sleep(0.5)
                ok = next((b for b in window.descendants(control_type="Button")
                           if b.window_text().replace("&", "") in ("OK", "Always", "Just once")), None)
                if ok is not None:
                    ok.click_input()
                return dict(dialog=names, chose=target.window_text())
            time.sleep(0.5)
        raise TimeoutError("Không có menu con hay hộp Open with")

    def close(self):
        if self.window is not None:
            close_windows([self.window.handle])


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
