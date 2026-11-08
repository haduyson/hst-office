# SPDX-License-Identifier: AGPL-3.0-only
"""Windows side of the GUI runtime checks: an installed HST Office started with its own profile, its windows, real
mouse and keyboard input (SendInput), screenshots and the accessibility tree over UNO.

Run with the office's own python.exe (so `import uno` works) on an interactive desktop (the GitHub Windows runner has
one). Nothing here starts or stops anything but the office it started itself.
"""
import ctypes
import os
import subprocess
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHOT_SCRIPT = os.path.join(ROOT, "scripts", "windows", "capture-screenshot.ps1")

user32 = ctypes.WinDLL("user32", use_last_error=True)
try:
    user32.SetProcessDPIAware()  # screen pixels for SetCursorPos and GetWindowRect alike
except AttributeError:
    pass


# ---- Win32 windows -------------------------------------------------------------------------------------------------
class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def office_windows():
    """[(hwnd, class name, title, (left, top, right, bottom))] of the visible top-level VCL windows (class SAL*)."""
    found = []

    def visit(hwnd, _param):
        if not user32.IsWindowVisible(hwnd):
            return True
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        if not name.value.startswith("SAL"):
            return True
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, 512)
        rect = _Rect()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        found.append((hwnd, name.value, title.value, (rect.left, rect.top, rect.right, rect.bottom)))
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


def client_origin(hwnd):
    """Screen position of the window's client area (VCL child positions are relative to it)."""
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    return point.x, point.y


def foreground(hwnd):
    """Bring `hwnd` to the front. Windows refuses SetForegroundWindow to a background process unless the last input
    came from it: an Alt press first (the documented way round the foreground lock)."""
    key_press(0x12)  # VK_MENU
    user32.ShowWindow(hwnd, 5)  # SW_SHOW
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    return user32.GetForegroundWindow() == hwnd


# ---- real input (SendInput) ----------------------------------------------------------------------------------------
class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _KeyInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeyInput), ("pad", ctypes.c_byte * 32)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


_MOVE, _ABSOLUTE, _LEFTDOWN, _LEFTUP, _KEYUP = 0x0001, 0x8000, 0x0002, 0x0004, 0x0002


def _send(*inputs):
    array = (_Input * len(inputs))(*inputs)
    return user32.SendInput(len(inputs), array, ctypes.sizeof(_Input))


def _mouse(flags, x=0, y=0):
    item = _Input(type=0)
    item.u.mi = _MouseInput(x, y, 0, flags, 0, 0)
    return item


def mouse_move(x, y, steps=8, pause=0.02):
    """Move the pointer to screen pixel (x, y) in small steps, as a hand does (each step is a WM_MOUSEMOVE)."""
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    start = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(start))
    for step in range(1, steps + 1):
        px = start.x + (x - start.x) * step // steps
        py = start.y + (y - start.y) * step // steps
        _send(_mouse(_MOVE | _ABSOLUTE, px * 65535 // (width - 1), py * 65535 // (height - 1)))
        time.sleep(pause)
    here = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(here))
    return here.x, here.y


def click(x, y):
    mouse_move(x, y)
    _send(_mouse(_LEFTDOWN), _mouse(_LEFTUP))
    time.sleep(0.3)


def key_press(vk):
    down, up = _Input(type=1), _Input(type=1)
    down.u.ki = _KeyInput(vk, 0, 0, 0, 0)
    up.u.ki = _KeyInput(vk, 0, _KEYUP, 0, 0)
    _send(down, up)
    time.sleep(0.25)


VK = {"tab": 0x09, "enter": 0x0D, "escape": 0x1B, "space": 0x20, "down": 0x28, "up": 0x26}


def keys(*names):
    for name in names:
        key_press(VK[name])


def screenshot(path, cursor=True):
    """Full-screen PNG, the pointer drawn in unless `cursor` is False; never raises (a missing shot must not hide the
    check result)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SHOT_SCRIPT, "-Path", path]
                   + (["-WithCursor"] if cursor else []), timeout=60, check=False)
    return path


# ---- accessibility over UNO ----------------------------------------------------------------------------------------
def _state(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleStateType." + name)


def _role(name):
    import uno
    return uno.getConstantByName("com.sun.star.accessibility.AccessibleRole." + name)


def walk(accessible, depth=0, limit=14):
    """Yield (accessible context, depth) for the whole tree under `accessible` (depth-first)."""
    try:
        context = accessible.getAccessibleContext()
    except Exception:  # noqa: BLE001 - a disposed node
        return
    if context is None:
        return
    yield context, depth
    if depth >= limit:
        return
    try:
        count = min(context.getAccessibleChildCount(), 400)
    except Exception:  # noqa: BLE001
        return
    for index in range(count):
        try:
            child = context.getAccessibleChild(index)
        except Exception:  # noqa: BLE001
            continue
        if child is not None:
            yield from walk(child, depth + 1, limit)


def showing(context):
    try:
        return bool(context.getAccessibleStateSet() & _state("SHOWING"))
    except Exception:  # noqa: BLE001
        return False


def find_named(accessible, name, role=None):
    """First accessible context named `name` (and of `role`, an AccessibleRole name) under `accessible`."""
    wanted = _role(role) if role else None
    for context, _depth in walk(accessible):
        try:
            if context.getAccessibleName() == name and (wanted is None or context.getAccessibleRole() == wanted):
                return context
        except Exception:  # noqa: BLE001
            continue
    return None


def texts(accessible, limit=60):
    """Names of the showing labels, buttons and texts under `accessible` (evidence for a report)."""
    out = []
    for context, _depth in walk(accessible):
        try:
            name = context.getAccessibleName()
        except Exception:  # noqa: BLE001
            continue
        if name and showing(context) and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def press(context):
    """Run the default action (a button's click) of an accessible context."""
    context.doAccessibleAction(0)


# ---- the office ----------------------------------------------------------------------------------------------------
class WinOffice:
    """One soffice process of an installed HST Office with its own profile directory `profile`.

    `fresh`: start from an empty profile exactly as a new user does: no warm-up start, nothing seeded, the Start Center
    shown (no --nodefault) so the start-up jobs (onFirstVisibleTask) run as they do for the user."""

    def __init__(self, install, profile, port, log_dir, nodefault=False):
        self.program = os.path.join(install, "program")
        self.profile = os.path.abspath(profile)
        self.port = port
        self.log_dir = log_dir
        self.nodefault = nodefault
        self.proc = None
        self.ctx = None
        self.starts = 0

    @property
    def url(self):
        return "file:///" + self.profile.replace("\\", "/")

    def start(self, fresh=False):
        import shutil
        if fresh:
            shutil.rmtree(self.profile, ignore_errors=True)
        os.makedirs(self.profile, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        self.starts += 1
        cmd = [os.path.join(self.program, "soffice.exe"), "--norestore", "-env:UserInstallation=" + self.url,
               "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port] + (["--nodefault"] if self.nodefault else [])
        log = os.path.join(self.log_dir, "soffice-%d" % self.starts)
        self.proc = subprocess.Popen(cmd, stdout=open(log + ".out", "w"), stderr=open(log + ".err", "w"))
        self.ctx = self._connect()
        return self

    def _connect(self, timeout=180):
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        deadline = time.time() + timeout
        while True:
            try:
                ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % self.port)
                ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
                return ctx
            except Exception:  # noqa: BLE001 - not up yet, or the first start restarting itself after the extension sync
                if time.time() > deadline:
                    raise RuntimeError("UNO socket of %s did not open in %d s" % (self.profile, timeout))
                time.sleep(1)

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def expand(self, text):
        """A vnd.sun.star.expand: URL or a $MACRO text as the office expands it (a file URL for the install)."""
        text = text.replace("vnd.sun.star.expand:", "", 1) if text.startswith("vnd.sun.star.expand:") else text
        return self.ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros(text)

    @staticmethod
    def bin_pids():
        """Process ids of every soffice.bin (a change between two calls shows the office restarted itself)."""
        listing = subprocess.run(["tasklist", "/FI", "IMAGENAME eq soffice.bin", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, check=False).stdout
        return sorted(int(row.split('","')[1]) for row in listing.splitlines() if row.startswith('"soffice.bin"'))

    @property
    def desktop(self):
        return self.service("com.sun.star.frame.Desktop")

    def top_windows(self):
        toolkit = self.service("com.sun.star.awt.Toolkit")
        return [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]

    def load(self, url, hidden=False, **props):
        from com.sun.star.beans import PropertyValue
        args = []
        for name, value in dict(props, Hidden=hidden).items():
            prop = PropertyValue()
            prop.Name, prop.Value = name, value
            args.append(prop)
        return self.desktop.loadComponentFromURL(url, "_blank", 0, tuple(args))

    def dispatch_async(self, frame, command, **props):
        """Dispatch `command` from a thread (a modal dialog blocks the call until it closes); returns the thread."""
        from com.sun.star.beans import PropertyValue
        args = []
        for name, value in props.items():
            prop = PropertyValue()
            prop.Name, prop.Value = name, value
            args.append(prop)
        helper = self.service("com.sun.star.frame.DispatchHelper")
        thread = threading.Thread(target=lambda: helper.executeDispatch(frame, command, "", 0, tuple(args)), daemon=True)
        thread.start()
        return thread

    def config(self, node, name):
        import uno
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "nodepath", node
        access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,))
        return access.getPropertyValue(name) if name else access

    def stop(self, timeout=60):
        """Quit through Desktop.terminate (the caller closes its modal dialogs first); kill only our own process."""
        if self.proc is None:
            return None
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        try:
            self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(10)
        code, self.proc, self.ctx = self.proc.returncode, None, None
        # soffice.exe returns when soffice.bin ended; wait until our profile's lock file is gone too
        lock = os.path.join(self.profile, ".lock")
        for _ in range(30):
            if not os.path.exists(lock):
                break
            time.sleep(1)
        return code


# ---- dialogs of the office -----------------------------------------------------------------------------------------
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


def close_dialog(window):
    """End a modal dialog: endExecute when its peer offers XDialog, else Escape with real input."""
    try:
        window.endExecute()
        return "endExecute"
    except Exception:  # noqa: BLE001
        keys("escape")
        return "escape"


def window_rect(hwnd):
    rect = _Rect()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def hwnd_of(title, timeout=10):
    """Win32 handle of the office window titled `title` (for screen coordinates and foreground)."""
    window = find_window(lambda name: name == title, timeout)
    return window[0] if window else None


def load_check(name):
    """A tests/runtime/check-*.py script as a module (its main() is not run), to share its checks with Windows."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Results:
    """PASS/FAIL rows printed as they come and written to <out>/results.json after each one (a hang keeps evidence)."""

    def __init__(self, out, profile):
        self.out, self.profile, self.rows = out, profile, []
        os.makedirs(out, exist_ok=True)

    def __call__(self, name, ok, detail=""):
        import json
        self.rows.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:1500]})
        print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:400]), flush=True)
        with open(os.path.join(self.out, "results.json"), "w", encoding="utf-8") as handle:
            json.dump({"profile": self.profile, "results": self.rows,
                       "failed": sum(r["status"] == "FAIL" for r in self.rows)}, handle, ensure_ascii=False, indent=1)
        return ok

    def note(self, name, detail):
        """Evidence that is not a pass/fail claim."""
        print("INFO  %s  %s" % (name, str(detail)[:600]), flush=True)
        self.rows.append({"check": name, "status": "INFO", "detail": str(detail)[:1500]})

    def exit_code(self):
        failed = [r for r in self.rows if r["status"] == "FAIL"]
        print("%d checks, %d failed" % (sum(r["status"] != "INFO" for r in self.rows), len(failed)), flush=True)
        return 1 if failed else 0


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
