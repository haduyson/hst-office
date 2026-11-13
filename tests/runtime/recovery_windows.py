# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-recovery-kill-windows.py: one office per profile under the test folder, driven over UNO from the
office's own Python; windows found and answered with user32 (Enter on the dialog's default button)."""
import ctypes
import glob
import os
import re
import subprocess
import time

RESULTS = []
PORT = 22235
KINDS = {"writer": "private:factory/swriter", "calc": "private:factory/scalc", "impress": "private:factory/simpress"}


def record(label, ok, detail=""):
    RESULTS.append(bool(ok))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % str(detail)[:300]) if not ok else ""), flush=True)


def wait(predicate, timeout, step=0.5):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


class Office:
    def __init__(self, program, work, minutes=3):
        self.program, self.work, self.minutes, self.proc = program, work, minutes, None
        self.user = os.path.join(work, "profile", "user")

    def seed(self):
        """A new profile without the start-up dialogs (welcome, default apps, tip of the day): they are modal."""
        xcu = os.path.join(self.user, "registrymodifications.xcu")
        if os.path.exists(xcu):
            return
        os.makedirs(self.user, exist_ok=True)
        items = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
                 ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
                 ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false"),
                 ("/org.openoffice.Office.Recovery/AutoSave", "TimeIntervall", str(self.minutes))]
        with open(xcu, "w", encoding="utf-8") as handle:
            handle.write('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/'
                         'registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/'
                         'XMLSchema-instance">\n')
            for node, prop, value in items:
                handle.write('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n'
                             % (node, prop, value))
            handle.write("</oor:items>\n")

    def start(self):
        import uno
        self.seed()
        url = uno.systemPathToFileUrl(os.path.join(self.work, "profile"))
        self.proc = subprocess.Popen([os.path.join(self.program, "soffice.exe"), "-env:UserInstallation=" + url,
                                      "--nologo", "--nodefault", "--accept=socket,host=127.0.0.1,port=%d;urp;" % PORT])
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        self.ctx = wait(lambda: self._try(resolver), 180, 1)
        return self.ctx

    def _try(self, resolver):
        try:
            return resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % PORT)
        except Exception:  # noqa: BLE001 - not up yet
            return None

    def desktop(self):
        return self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)

    def configure(self):
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Recovery/AutoSave"
        provider = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.configuration.ConfigurationProvider", self.ctx)
        access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        access.setPropertyValue("TimeIntervall", self.minutes)
        access.commitChanges()

    def new(self, kind, marker):
        doc = self.desktop().loadComponentFromURL(KINDS[kind], "_default", 0, ())
        append(doc, marker)
        return doc

    def copies(self):
        return {p: os.path.getsize(p) for p in glob.glob(os.path.join(self.user, "backup", "*_*.od?"))
                if os.path.getsize(p) > 0}

    def kill(self):
        kill_profile(self.work)
        time.sleep(3)

    def recover(self):
        """Start again, press Enter on the recovery dialog (its default button), reconnect."""
        self.start()
        hwnd = wait(lambda: find_window(r"Khôi phục tài liệu|Document Recovery"), 90)
        if not hwnd:
            return False
        press_enter(hwnd)
        time.sleep(8)
        hwnd = find_window(r"Khôi phục tài liệu|Document Recovery")
        if hwnd:  # "Kết thúc" after a partial recovery
            press_enter(hwnd)
        return True

    def texts(self):
        out, enum = [], self.desktop().Components.createEnumeration()
        while enum.hasMoreElements():
            comp = enum.nextElement()
            if hasattr(comp, "supportsService"):
                out.append(text_of(comp))
        return out


def kill_profile(work):
    """taskkill /F of the office processes of this profile only (never another office on the machine)."""
    script = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'soffice*' -and $_.CommandLine -like '*%s*' }"
              " | ForEach-Object { taskkill /F /PID $_.ProcessId }" % work.replace("\\", "/").split(":", 1)[-1])
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)


def append(doc, marker):
    if doc.supportsService("com.sun.star.text.TextDocument"):
        doc.Text.insertString(doc.Text.End, " " + marker, False)
    elif doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        cell = doc.Sheets.getByIndex(0).getCellByPosition(0, 0)
        cell.String = (cell.String + " " + marker).strip()
    else:
        shape = doc.createInstance("com.sun.star.drawing.TextShape")
        doc.DrawPages.getByIndex(0).add(shape)
        shape.String = marker
    doc.setModified(True)


def text_of(doc):
    if doc.supportsService("com.sun.star.text.TextDocument"):
        return doc.Text.String
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return doc.Sheets.getByIndex(0).getCellByPosition(0, 0).String
    page = doc.DrawPages.getByIndex(0)
    return " ".join(page.getByIndex(i).String for i in range(page.Count))


def find_window(pattern):
    user32, found = ctypes.windll.user32, []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, _):
        buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buffer, 512)
        if user32.IsWindowVisible(hwnd) and re.search(pattern, buffer.value):
            found.append(hwnd)
        return True
    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def press_enter(hwnd):
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    user32.keybd_event(0x0D, 0, 0, 0)
    user32.keybd_event(0x0D, 0, 2, 0)
