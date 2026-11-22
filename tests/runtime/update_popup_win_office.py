# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The office side of update-popup-drive-windows.py: a soffice with its own profile reached over a UNO socket, its
pop-up found and pressed through the accessibility tree, and real key presses (SendInput) into a window."""
import ctypes
import os
import subprocess
import time

TITLE = "Cập nhật HST Office"
NODE = "/org.openoffice.Office.HSTUpdate"


def wait(predicate, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001 - the window is still being built
            pass
        time.sleep(0.5)
    return False


def seed(profile, items):
    """(node, property, xml value) into registrymodifications.xcu, created when missing (later items win)."""
    path = os.path.join(profile, "user", "registrymodifications.xcu")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    head = '<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" ' \
           'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else head + "</oor:items>\n"
    lines = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % i for i in items)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace("</oor:items>", lines + "</oor:items>"))


def accessible(window):
    """The window's accessible context: toolkit windows hand out XAccessible as their property "XAccessible"."""
    try:
        return window.getAccessibleContext()
    except AttributeError:
        node = window.getProperty("XAccessible")
        return node.getAccessibleContext() if node is not None else None


class Office:
    def __init__(self, program, work, port, env):
        self.program, self.work, self.port, self.env, self.proc, self.ctx = program, work, port, env, None, None
        self.profile = os.path.join(work, "profile")

    def init_profile(self):
        """Create the profile and finish the bundled-extension sync before anything is seeded into it.

        A --terminate_after_init start registers the extensions but never writes user/extensions/bundled/
        lastsynchronized, so the next start synchronizes again and drops the values seeded for the extensions' schemas
        (Welcome/Shown read back false: the welcome dialog opens and the update pop-up rightly waits behind it). A short
        full headless run (converting an empty file) completes the sync, as hst_gui_profile.settle_extensions does on
        Linux. The profile's .lock is gone once that office has let the profile go."""
        marker = os.path.join(self.profile, "user", "extensions", "bundled", "lastsynchronized")
        lock = os.path.join(self.profile, ".lock")
        if os.path.exists(marker) and not os.path.exists(lock):
            return
        url = "file:///" + self.profile.replace("\\", "/")
        settle = os.path.join(self.work, "settle")
        os.makedirs(settle, exist_ok=True)
        empty = os.path.join(settle, "empty.txt")
        open(empty, "w").close()
        for _attempt in range(3):  # the first run may end asking for a restart after the sync
            subprocess.run([os.path.join(self.program, "soffice.exe"), "-env:UserInstallation=" + url, "--headless",
                            "--norestore", "--convert-to", "pdf", "--outdir", settle, empty],
                           env=self.env, timeout=180, check=False, capture_output=True)
            if wait(lambda: os.path.exists(marker) and not os.path.exists(lock), 60):
                return
        raise RuntimeError("the office did not finish setting up its profile")

    def start(self):
        url = "file:///" + self.profile.replace("\\", "/")
        self.proc = subprocess.Popen([os.path.join(self.program, "soffice.exe"), "-env:UserInstallation=" + url, "--norestore",
                                      "--nologo", "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port], env=self.env)
        import uno
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        conn = "uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % self.port
        wait(lambda: setattr(self, "ctx", resolver.resolve(conn)) or True, 120)
        from com.sun.star.beans import PropertyValue
        prop = PropertyValue()
        prop.Name, prop.Value = "OnMainThread", True
        return self.service("com.sun.star.frame.Desktop").loadComponentFromURL("private:factory/swriter", "_blank", 0, (prop,))

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def stop(self):
        try:
            self.service("com.sun.star.frame.Desktop").terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away with the office
            pass
        try:
            self.proc.wait(60)
        except subprocess.TimeoutExpired:
            self.proc.kill()  # our own soffice only
        subprocess.run(["taskkill", "/F", "/T", "/FI", "WINDOWTITLE eq " + TITLE], capture_output=True, check=False)
        time.sleep(3)

    def popup(self):
        """The pop-up's window handle (a visible top-level window titled TITLE), or None."""
        found = windows(lambda title: title == TITLE)
        return found[0] if found else None

    def _accessible_popup(self):
        toolkit = self.service("com.sun.star.awt.Toolkit")
        for index in range(toolkit.getTopWindowCount()):
            context = accessible(toolkit.getTopWindow(index))
            if context is not None and context.getAccessibleName() == TITLE:
                return context
        return None

    def press(self, label, index):
        """Press the pop-up's button `label` (its `index`-th button): its accessible action, else the keyboard (the
        pop-up in front, Tab `index` times from the default first button, Space)."""
        def find(context):
            for child_index in range(context.getAccessibleChildCount()):
                child = context.getAccessibleChild(child_index).getAccessibleContext()
                if child.getAccessibleName() == label and hasattr(child, "doAccessibleAction"):
                    return child
                found = find(child)
                if found is not None:
                    return found
            return None
        try:
            context = self._accessible_popup()
            button = find(context) if context is not None else None
            if button is not None:
                return bool(button.doAccessibleAction(0))
        except Exception:  # noqa: BLE001 - fall back to the keyboard
            pass
        hwnd = self.popup()
        if hwnd is None or not to_front(hwnd):
            return False
        send_keys([0x09] * index + [0x20])
        return True

    def describe(self):
        """What a failed run saw: the toolkit's top windows (accessible names) and the visible window titles."""
        names = []
        try:
            toolkit = self.service("com.sun.star.awt.Toolkit")
            for index in range(toolkit.getTopWindowCount()):
                context = accessible(toolkit.getTopWindow(index))
                names.append(context.getAccessibleName() if context is not None else None)
        except Exception as error:  # noqa: BLE001
            names.append(repr(error))
        return {"toolkit": names, "windows": [t for _h, t in windows_titled(lambda title: bool(title))]}

    def setting(self, name):
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", NODE
        return self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,)).getPropertyValue(name)


def windows_titled(predicate):
    """[(hwnd, title)] of the visible top-level windows whose title passes `predicate`."""
    user32, found = ctypes.windll.user32, []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def each(hwnd, _):
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, 512)
        if user32.IsWindowVisible(hwnd) and predicate(buffer.value):
            found.append((hwnd, buffer.value))
        return True
    user32.EnumWindows(proc(each), 0)
    return found


def windows(predicate):
    return [hwnd for hwnd, _t in windows_titled(predicate)]


def to_front(hwnd):
    """SetForegroundWindow, with this thread's input attached to the foreground thread when the plain call is refused."""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    for attach in (False, True):
        front = user32.GetForegroundWindow()
        thread = user32.GetWindowThreadProcessId(front, None) if attach and front else 0
        if thread:
            user32.AttachThreadInput(kernel32.GetCurrentThreadId(), thread, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if thread:
            user32.AttachThreadInput(kernel32.GetCurrentThreadId(), thread, False)
        time.sleep(0.5)
        if user32.GetForegroundWindow() == hwnd:
            return True
    return False


def send_keys(vks):
    user32 = ctypes.windll.user32
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.08)


def type_into(title_part, text):
    """Bring the document window (title contains title_part) to the front and type `text` with real key events."""
    found = windows(lambda title: title_part in title)
    if not found or not to_front(found[0]):
        return False
    time.sleep(0.5)
    send_keys([ctypes.windll.user32.VkKeyScanW(ord(char)) & 0xFF for char in text])
    return True
