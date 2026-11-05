# SPDX-License-Identifier: AGPL-3.0-only
"""Drive HST Office dialogs through the UITest service: real dialogs on the headless svp plugin, addressed by
widget id. check-dialogs-writer.py and its siblings assert tab order, key controls and that an edit
reaches the document. The svp plugin is used because UITest only sees VCL widgets, not native gtk3,
and it activates windows without a window manager, which modeless dialogs need.
"""
import os
import time

import hst_gui


class DialogHarness:
    def __init__(self, instdir, workdir, port, display):
        self.display = display
        os.environ["HST_VCLPLUGIN"] = "svp"
        hst_gui.setup_uno(instdir)
        self.office = hst_gui.Office(instdir, workdir, port, display=display)
        self.office.start()
        self.ui = self.office.service("com.sun.star.ui.test.UITest")
        # The only open document's controller vetoes close() here (also with no dialog ever opened);
        # with this one left open, the documents of each check close normally.
        self.office.load("private:factory/swriter")

    def close(self):
        self.office.stop()

    def new_document(self, kind="swriter"):
        doc = self.office.load(f"private:factory/{kind}")
        self.wait_idle()
        return doc

    def close_document(self, doc):
        """Close without a save prompt; a veto that lasts means a dialog was left open."""
        from com.sun.star.util import CloseVetoException
        doc.setModified(False)
        for _ in range(5):
            try:
                doc.close(True)
                return
            except CloseVetoException:
                time.sleep(1)
        raise AssertionError(f"document refused to close (focus: {state(self.ui.getTopFocusWindow()).get('ID')})")

    def temp_url(self, name):
        return "file://" + os.path.join(self.office.workdir, name)

    def wait_idle(self, seconds=1.0):
        time.sleep(seconds)

    def open_dialog(self, command, dialog_id, timeout=30, modeless=False):
        """Open a dialog by .uno command and wait until the dialog with that widget id has focus."""
        if modeless:
            self.ui.executeCommand(command)
        else:
            self.ui.executeDialog(command)
        deadline = time.time() + timeout
        while time.time() < deadline:
            top = self.ui.getTopFocusWindow()
            # A modeless dialog's top window has no id of its own: dialog_id is then one of its widgets.
            if state(top).get("ID") == dialog_id or (modeless and has_child(top, dialog_id)):
                return top
            if "chào đón" in state(top).get("Text", ""):  # can appear after the first document loads
                click(top, "ok")
            time.sleep(0.5)
        raise AssertionError(f"{command}: dialog {dialog_id} did not open (focus: {state(top).get('ID')!r} {state(top).get('Text')!r} {state(top).get('WindowType')})")


def props(**values):
    from com.sun.star.beans import PropertyValue
    result = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        result.append(prop)
    return tuple(result)


def state(obj):
    return {p.Name: p.Value for p in obj.getState()}


def tab_titles(dialog, control="tabcontrol"):
    """Titles of every tab, in order, by selecting each one; returns to the first tab."""
    tabs = dialog.getChild(control)
    titles = []
    for pos in range(int(state(tabs)["PageCount"])):
        select_tab(dialog, pos, control)
        titles.append(state(tabs)["CurrPageTitle"])
    select_tab(dialog, 0, control)
    return titles


def select_tab(dialog, pos, control="tabcontrol"):
    dialog.getChild(control).executeAction("SELECT", props(POS=str(pos)))
    time.sleep(0.3)


def select_entry(dialog, widget, pos):
    dialog.getChild(widget).executeAction("SELECT", props(POS=str(pos)))
    time.sleep(0.2)


def type_value(dialog, widget, text):
    """Replace a field's text. UITest maps no Tab key (it types a stray "a"), so the value is read on OK."""
    field = dialog.getChild(widget)
    field.executeAction("FOCUS", ())
    field.executeAction("SELECT", props(FROM="0", TO="99"))
    field.executeAction("TYPE", props(KEYCODE="BACKSPACE"))
    field.executeAction("TYPE", props(TEXT=text))
    time.sleep(0.2)


def click(dialog, widget):
    dialog.getChild(widget).executeAction("CLICK", ())
    time.sleep(0.5)


def has_child(dialog, widget):
    try:
        dialog.getChild(widget)
        return True
    except Exception:  # noqa: BLE001 - UITest reports a missing child as a runtime error
        return False


def visible(dialog, widget):
    return state(dialog.getChild(widget)).get("ReallyVisible") == "true"


class Checks:
    """Collects results so one failure still reports the rest."""

    def __init__(self):
        self.failures = []

    def equal(self, what, actual, expected):
        good = actual == expected
        print(("ok   " if good else "FAIL ") + f"{what}: {actual!r}" + ("" if good else f" (expected {expected!r})"), flush=True)
        if not good:
            self.failures.append(what)

    def finish(self):
        print(f"{len(self.failures)} failure(s)" if self.failures else "all checks passed", flush=True)
        return 1 if self.failures else 0
