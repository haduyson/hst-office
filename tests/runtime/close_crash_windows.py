# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of check-close-crash-handler-windows.py: one office per run on its own profile (the owner's save settings),
driven over UNO from the office's own python.exe until the UNO bridge is dropped (a live bridge keeps the office from
ending when its last window closes). Windows are only touched through their own HWNDs (WM_CLOSE, posted keys) after
checking that they belong to this run's soffice.bin (windows_gui_guard)."""
import ctypes
import os
import re
import shutil
import subprocess
import time
import zlib
from ctypes import wintypes

import windows_gui_guard as guard

HERE = os.path.dirname(os.path.abspath(__file__))
U32 = ctypes.windll.user32
FACTORY = "/org.openoffice.Setup/Office/Factories/org.openoffice.Setup:Factory['com.sun.star.text.TextDocument']"
# Tools > Options > Load/Save > General as in the owner's report.
OWNER_SETTINGS = [("/org.openoffice.Office.Recovery/AutoSave", "Enabled", "true"),
                  ("/org.openoffice.Office.Recovery/AutoSave", "TimeIntervall", "1"),
                  ("/org.openoffice.Office.Recovery/AutoSave", "UserAutoSaveEnabled", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "CreateBackup", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "BackupIntoDocumentFolder", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "EditProperty", "true"),
                  ("/org.openoffice.Office.Common/Save/Document", "WarnAlienFormat", "false"),
                  (FACTORY, "ooSetupFactoryDefaultFilter", "MS Word 2007 XML")]
QUIET = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"), ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
         ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")]
RECOVERY = re.compile("Khôi phục tài liệu|Document Recovery")


def ps(*args):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def pids(work, image="soffice*"):
    """Office processes of THIS run (matched by its own profile path), never another office on the machine."""
    match = work.replace("\\", "/").split(":", 1)[-1]
    out = ps("-Command", "Get-CimInstance Win32_Process | Where-Object { $_.Name -like '%s' -and $_.CommandLine -like "
             "'*%s*' } | ForEach-Object { $_.ProcessId }" % (image, match))
    return {int(x) for x in out.split() if x.isdigit()}


def windows(own):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, _):
        pid = ctypes.c_ulong()
        U32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in own and U32.IsWindowVisible(hwnd):
            text = ctypes.create_unicode_buffer(512)
            U32.GetWindowTextW(hwnd, text, 512)
            found.append((hwnd, text.value))
        return True
    U32.EnumWindows(visit, 0)
    return found


def responsive(hwnd):
    result = ctypes.c_size_t()
    return bool(U32.SendMessageTimeoutW(wintypes.HWND(hwnd), 0, 0, 0, 0x2, 3000, ctypes.byref(result)))


def press_enter(hwnd):
    """Enter posted to our own dialog (its default button); refused for any window that is not ours."""
    if not guard.is_ours(hwnd):
        return False
    U32.PostMessageW(wintypes.HWND(hwnd), 0x100, 0x0D, 0x00000001)
    U32.PostMessageW(wintypes.HWND(hwnd), 0x101, 0x0D, 0xC0000001)
    return True


class Office:
    def __init__(self, program, work):
        self.program, self.work, self.proc, self.ctx = program, work, None, None
        self.port = 22300 + zlib.crc32(work.encode()) % 600
        self.docs = os.path.join(work, "docs")

    def url(self):
        import uno
        return uno.systemPathToFileUrl(os.path.join(self.work, "profile"))

    def prepare(self):
        """Fresh profile, initialised once (extension settings are only kept after that), then the settings."""
        shutil.rmtree(self.work, ignore_errors=True)
        os.makedirs(self.docs)
        for _ in range(2):
            subprocess.run([os.path.join(self.program, "soffice.exe"), "-env:UserInstallation=" + self.url(),
                            "--headless", "--norestore", "--terminate_after_init"], timeout=300)
            end = time.time() + 120
            while pids(self.work) and time.time() < end:
                time.sleep(2)
        xcu = os.path.join(self.work, "profile", "user", "registrymodifications.xcu")
        with open(xcu, encoding="utf-8") as handle:
            text = handle.read()
        items = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % i
                        for i in QUIET + OWNER_SETTINGS)
        with open(xcu, "w", encoding="utf-8") as handle:
            handle.write(text.replace("</oor:items>", items + "</oor:items>"))

    def start(self):
        import uno
        self.proc = subprocess.Popen([os.path.join(self.program, "soffice.exe"), "-env:UserInstallation=" + self.url(),
                                      "--nologo", "--nodefault", "--accept=socket,host=127.0.0.1,port=%d;urp;" % self.port])
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        end = time.time() + 300  # a busy test PC (a build running) starts slowly
        while self.ctx is None:
            try:
                self.ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % self.port)
            except Exception:  # noqa: BLE001 - not up yet
                if time.time() > end:
                    raise
                time.sleep(1)
        time.sleep(5)
        self.end_startup_dialogs()

    def end_startup_dialogs(self, settle=20):
        """The welcome dialog (shown on some fresh profiles in spite of the setting, sometimes late) is modal and
        would block the close: end it over UNO until none has shown for `settle` seconds."""
        toolkit = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        quiet_since = time.time()
        while time.time() - quiet_since < settle:
            for index in range(toolkit.getTopWindowCount()):
                window = toolkit.getTopWindow(index)
                if hasattr(window, "endExecute") and re.search("ch\u00e0o|Welcome", window.getTitle() or ""):
                    window.endExecute()
                    quiet_since = time.time()
            time.sleep(1)

    def drop_bridge(self):
        import uno
        self.ctx = None
        local = uno.getComponentContext()
        factory = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.BridgeFactory", local)
        for bridge in factory.getExistingBridges():
            bridge.dispose()
        time.sleep(2)

    def arm_fault(self, hwnd=0):
        """inject-main-thread-fault.ps1 on this run's soffice.bin; with hwnd it fires when that window is destroyed."""
        binary = sorted(pids(self.work, "soffice.bin"))
        args = ["-File", os.path.join(HERE, "inject-main-thread-fault.ps1"), "-ProcId", str(binary[0])]
        proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", *args, "-WaitHwnd", str(hwnd)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(8)  # compiled and armed
        return proc

    def fault_note(self):
        path = os.path.join(self.work, "profile", "user", "hst-office", "last-fault.txt")
        return open(path, encoding="utf-8", errors="replace").read().strip() if os.path.exists(path) else ""

    def kill(self):
        for pid in pids(self.work):
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        time.sleep(3)
