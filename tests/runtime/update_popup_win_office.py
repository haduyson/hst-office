# SPDX-License-Identifier: AGPL-3.0-only
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
        """The pop-up's accessible context, or None."""
        toolkit = self.service("com.sun.star.awt.Toolkit")
        for index in range(toolkit.getTopWindowCount()):
            window = toolkit.getTopWindow(index)
            context = accessible(window)
            if context is not None and context.getAccessibleName() == TITLE and window.isVisible():
                return context
        return None

    def press(self, label):
        """Press the pop-up's button `label` through its accessible action."""
        def find(context):
            for index in range(context.getAccessibleChildCount()):
                child = context.getAccessibleChild(index).getAccessibleContext()
                if child.getAccessibleName() == label and hasattr(child, "doAccessibleAction"):
                    return child
                found = find(child)
                if found is not None:
                    return found
            return None
        button = find(self.popup())
        return bool(button is not None and button.doAccessibleAction(0))

    def setting(self, name):
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", NODE
        return self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,)).getPropertyValue(name)


def type_into(title_part, text):
    """Foreground the document window (title contains title_part) and type `text` with SendInput (real keys)."""
    user32 = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def each(hwnd, _):
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, 512)
        if title_part in buffer.value and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows(proc(each), 0)
    if not found:
        return False
    user32.SetForegroundWindow(found[0])
    time.sleep(1.0)
    for char in text:
        vk = user32.VkKeyScanW(ord(char)) & 0xFF
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.05)
    return True
