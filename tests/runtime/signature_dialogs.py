# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog side of check-digital-signature.py: the UITest-driven signing dialogs, token PIN prompts, the welcome
dialog and the start of the office (gen VCL plugin: UITest reaches VCL dialogs only)."""
import os
import threading
import time

import signature_pki

CANCEL = object()


def props(**values):
    import uno
    from com.sun.star.beans import PropertyValue
    out = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name = name
        prop.Value = uno.Any("[]com.sun.star.beans.PropertyValue", value) if name == "FilterData" else value
        out.append(prop)
    return tuple(out)

class Dialogs:
    """UITest-driven dialog steps; answers token PIN prompts from a queue on the way."""

    def __init__(self, office, shots, pins):
        self.office, self.shots, self.pins = office, shots, list(pins)
        self.ui = office.service("org.libreoffice.uitest.UITest")
        self.prompts, self.unexpected = [], []

    def top(self):
        try:
            win = self.ui.getTopFocusWindow()
            return win, set(win.getChildren())
        except Exception:  # noqa: BLE001 - no focus window between dialogs
            return None, set()

    def shot(self, name):
        try:
            return self.office.screenshot(os.path.join(self.shots, name + ".png"))
        except Exception:  # noqa: BLE001 - evidence only
            return None

    @staticmethod
    def later(obj, action="CLICK", args=()):
        """Run a UI action in its own thread: buttons that open modal dialogs block the call."""
        thread = threading.Thread(target=obj.executeAction, args=(action, args), daemon=True)
        thread.start()
        return thread

    def _answer_pin(self, win):
        label = ""
        try:
            label = {p.Name: p.Value for p in win.getChild("openPasswordLabel").getState()}.get("Text", "")
        except Exception:  # noqa: BLE001
            pass
        answer = self.pins.pop(0) if self.pins else CANCEL
        self.prompts.append({"label": label, "answer": "cancel" if answer is CANCEL else "pin(%d digits)" % len(answer)})
        self.shot("pin-prompt-%d" % len(self.prompts))
        if answer is CANCEL:
            self.later(win.getChild("cancel"))
        else:
            win.getChild("newpassEntry").executeAction("TYPE", props(TEXT=answer))
            self.later(win.getChild("ok"))
        time.sleep(1.5)

    def wait(self, wanted, timeout=60, gone=False, accept_errors=False):
        """Wait until the top dialog has all ids in `wanted` (or, gone=True, until it has none)."""
        deadline = time.time() + timeout
        stale_since = None
        while time.time() < deadline:
            win, kids = self.top()
            if "newpassEntry" in kids:
                self._answer_pin(win)
                continue
            if (not gone and wanted <= kids) or (gone and not (wanted & kids)):
                return win
            # message boxes (wrong PIN, signing error): record, confirm, carry on
            if kids and "ok" in kids and not (kids & {"signatures", "searchbox", "newpassEntry"}):
                stale_since = stale_since or time.time()
                if time.time() - stale_since > 2:  # an error/info message box: record and confirm
                    self.unexpected.append(sorted(kids))
                    self.shot("message-%d" % len(self.unexpected))
                    self.later(win.getChild("ok"))
                    stale_since = None
                    time.sleep(1.5)
            time.sleep(0.5)
        self.shot("timeout")
        raise TimeoutError("dialog %s %s not reached; top has %s" % ("without" if gone else "with", sorted(wanted), sorted(self.top()[1])))

    def certificate_rows(self, accept_errors, timeout=40):
        """The certificate chooser lists token certificates only after the token login (PIN)."""
        deadline = time.time() + timeout
        while True:
            chooser = self.wait({"searchbox", "signatures", "ok"}, accept_errors=accept_errors)
            tree = chooser.getChild("signatures")
            rows = [(cid, {p.Name: p.Value for p in tree.getChild(cid).getState()}.get("Text", "")) for cid in tree.getChildren()]
            if rows or time.time() > deadline:
                return chooser, rows
            time.sleep(1)

    def sign_open_document(self, frame, tag, accept_errors=False):
        """Tệp tin → Chữ ký số… → Ký tài liệu… → certificate → Ký → Đóng, on the loaded document."""
        threading.Thread(target=self.office.dispatch, args=(frame, ".uno:Signature"), daemon=True).start()
        dialog = self.wait({"signatures", "sign", "close"}, accept_errors=accept_errors)
        self.later(dialog.getChild("sign"))
        chooser, rows = self.certificate_rows(accept_errors)
        self.shot(tag + "-1-chooser")
        match = [cid for cid, text in rows if signature_pki.USER_CN in text]
        if not match:
            self.later(chooser.getChild("cancel"))
            self.wait({"searchbox"}, gone=True, accept_errors=accept_errors)
            dialog, _ = self.top()
            self.later(dialog.getChild("close"))
            self.wait({"sign", "close"}, gone=True, accept_errors=accept_errors)
            return {"chooser_rows": [t for _c, t in rows], "signed": False}
        chooser.getChild("signatures").getChild(match[0]).executeAction("SELECT", ())
        self.later(chooser.getChild("ok"))
        dialog = self.wait({"signatures", "sign", "close"}, timeout=90, accept_errors=accept_errors)
        time.sleep(1)
        entries = list(dialog.getChild("signatures").getChildren())
        self.shot(tag + "-2-signed-dialog")
        self.later(dialog.getChild("close"))
        self.wait({"sign", "close"}, gone=True, accept_errors=accept_errors)
        # "Bạn có muốn ghi nhớ chữ ký đó cho mỗi lần lưu không?" follows a new signature: Không
        remember = False
        for _ in range(10):
            win, kids = self.top()
            if {"yes", "no"} <= kids:
                remember = True
                self.later(win.getChild("no"))
                time.sleep(1.5)
                break
            time.sleep(0.5)
        return {"chooser_rows": [t for _c, t in rows], "signed": bool(entries), "dialog_entries": len(entries),
                "remember_question": remember}

def dismiss_welcome(office, stop):
    """Close the HST welcome dialog if it shows; under the gen plugin its title is COMPOUND_TEXT,
    which hst_gui.toplevels() cannot read, so match the raw WM_NAME instead."""
    import re
    import subprocess
    while not stop.wait(1.0):
        pid = office.pid
        if pid is None:
            continue
        tree = subprocess.run(["xwininfo", "-display", office.display, "-root", "-children"], capture_output=True, text=True).stdout
        for wid in re.findall(r"^\s*(0x[0-9a-f]+) ", tree, re.M):
            prop = subprocess.run(["xprop", "-display", office.display, "-id", wid, "WM_NAME", "_NET_WM_PID"],
                                  capture_output=True, text=True).stdout
            if ("= %d" % pid) in prop and re.search(r"Ch\\340o m|Chào mừng|Welcome to", prop):
                office.click_close(wid)


def start_office(office):
    office.start()
    stop = threading.Event()
    threading.Thread(target=dismiss_welcome, args=(office, stop), daemon=True).start()
    return stop
