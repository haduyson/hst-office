# SPDX-License-Identifier: AGPL-3.0-only
"""Shared scenario of check-ui-mode-tabs.py (Linux) and check-windows-ui-mode-tabs.py (Windows): document tabs of
modules in different user interface modes keep the mode of their own module.

A Writer and a Sheets document are tabs of one window. A tab "shows its mode" when:
- a toolbar mode (Standard Toolbar): the menubar and the mode's mandatory toolbars are visible;
- a ribbon mode (Tabbed): no toolbar is visible and the menubar is hidden (HST's Tabbed mode has no menubar).
Before hst-ui-mode-per-tab.patch, "Apply to All" from the Writer tab, after Sheets had once gone from Standard Toolbar
back to Tabbed, left the Sheets tab with the menubar only: no ribbon, no toolbar (user report 13/11/2026).

The office object needs: desktop (XDesktop), dispatch(frame, command, args), set_config(node, prop, value),
config_access(node) (read-only configuration node) and window_states() (theWindowStateConfiguration).
"""
import os
import time

MODE_PATH = "/org.openoffice.Office.UI.ToolbarMode"
APPS = ("Writer", "Calc", "Impress", "Draw")
MANDATORY = {"Writer": ("standardbar", "textobjectbar"), "Calc": ("standardbar", "formatobjectbar")}
# the modes the reporter tried one by one (View > User Interface), ending with Standard Toolbar
CYCLE = ("Default", "Single", "Sidebar", "notebookbar_compact.ui", "notebookbar_groupedbar_compact.ui",
         "notebookbar_single.ui", "notebookbar.ui", "Default")
DOCS = (("Calc", "scalc", "Data.xlsx", "Calc MS Excel 2007 XML"),
        ("Writer", "swriter", "KhongGian.docx", "MS Word 2007 XML"))


def prop(name, value):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    p.Name, p.Value = name, value
    return p


def frames(desktop):
    access = desktop.getFrames()
    return [access.getByIndex(i) for i in range(access.getCount())]


def shown(desktop):
    return [f for f in frames(desktop) if f.getContainerWindow().isVisible()][0]


def app_of(frame):
    title = frame.Title
    return "Writer" if "HST Writer" in title else "Calc" if "HST Sheets" in title else ""


def tab_state(frame):
    lm = frame.LayoutManager
    toolbars = [e.ResourceURL for e in lm.getElements() if "/toolbar/" in e.ResourceURL]
    return {"title": frame.Title, "app": app_of(frame),
            "toolbars": sorted(u.split("/")[-1] for u in toolbars if lm.isElementVisible(u)),
            "menubar": bool(lm.isElementVisible("private:resource/menubar/menubar"))}


def matches(state, mode):
    """True when the tab shows `mode`: Standard Toolbar / Single Toolbar: the menubar and the mode's toolbars;
    a ribbon mode: no toolbar (Tabbed also hides the menubar)."""
    if mode in ("Default", "Single"):
        wanted = MANDATORY[state["app"]] if mode == "Default" else ("singlemode",)
        return state["menubar"] and all(t in state["toolbars"] for t in wanted)
    return not state["toolbars"] and (mode != "notebookbar.ui" or not state["menubar"])


def make_document(office, factory, path, filter_name):
    import uno
    doc = office.desktop.loadComponentFromURL("private:factory/" + factory, "_blank", 0, (prop("Hidden", True),))
    doc.storeToURL(uno.systemPathToFileUrl(path), (prop("FilterName", filter_name),))
    doc.close(True)
    return uno.systemPathToFileUrl(path)


def open_documents(office, folder):
    import uno
    os.makedirs(folder, exist_ok=True)
    for _app, factory, name, filter_name in DOCS:
        doc = office.desktop.loadComponentFromURL("private:factory/" + factory, "_blank", 0, (prop("Hidden", True),))
        url = uno.systemPathToFileUrl(os.path.join(folder, name))
        doc.storeToURL(url, (prop("FilterName", filter_name),))
        doc.close(True)
    for _app, _factory, name, _filter in DOCS:
        office.desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.join(folder, name)), "_blank", 0, ())
        time.sleep(3)


def goto(office, app, limit=6):
    for _ in range(limit):
        if app_of(shown(office.desktop)) == app:
            return shown(office.desktop)
        office.dispatch(shown(office.desktop), ".uno:NextDocumentTab")
        time.sleep(2.5)
    raise RuntimeError("no %s tab" % app)


MODULE_IDS = {"Writer": "com.sun.star.text.TextDocument", "Calc": "com.sun.star.sheet.SpreadsheetDocument",
              "Impress": "com.sun.star.presentation.PresentationDocument", "Draw": "com.sun.star.drawing.DrawingDocument"}


def store_mode_toolbars(office, app, mode):
    """What "Apply to All" of the user interface dialog does for another application since hst-ui-mode-per-tab.patch
    (cui UIPickerDialog lcl_storeModeToolbars): its new mode's toolbars stored visible, toolbars only other modes use
    stored invisible. `office.dialog_stores_toolbars = False` reproduces 1.0.1 (configuration only)."""
    import uno
    modes = office.config_access(MODE_PATH + "/Applications/%s/Modes" % app)
    show, hide = [], []
    for name in modes.getElementNames():
        node = modes.getByName(name)
        (show if node.CommandArg == mode else hide).extend(list(node.Toolbars) + list(node.UserToolbars))
    states = office.window_states().getByName(MODULE_IDS[app])
    for url, visible in [(u, False) for u in hide if u not in show] + [(u, True) for u in show]:
        props = [p for p in (states.getByName(url) if states.hasByName(url) else ()) if p.Name != "Visible"]
        value = uno.Any("[]com.sun.star.beans.PropertyValue", tuple(props + [prop("Visible", visible)]))
        if states.hasByName(url):
            uno.invoke(states, "replaceByName", (url, value))
        else:
            uno.invoke(states, "insertByName", (url, value))


def apply_mode(office, app, mode, to_all=False):
    """Like the user interface dialog: "Apply to <module>" from the tab of `app`, or "Apply to All" (the other
    applications by configuration only, the current one by .uno:ToolbarMode)."""
    frame = goto(office, app)
    if to_all:
        for other in APPS:
            if other != app:
                office.set_config(MODE_PATH, "Active" + other, mode)
                office.set_config(MODE_PATH + "/Applications/" + other, "Active", mode)
                if getattr(office, "dialog_stores_toolbars", True):
                    store_mode_toolbars(office, other, mode)
    office.dispatch(frame, ".uno:ToolbarMode", (prop("Mode", mode),))
    time.sleep(3)


def switch_and_judge(office, check, label, modes, switches=4):
    """Switch tabs `switches` times; every shown Writer/Sheets tab must show modes[app], menubar included (a tab
    parked while its own module went through ribbon modes came back without its menubar before
    hst-menubar-parked-tab.patch; 1.0.1 did the same)."""
    bad = []
    for n in range(switches):
        office.dispatch(shown(office.desktop), ".uno:NextDocumentTab")
        time.sleep(2.5)
        state = tab_state(shown(office.desktop))
        if state["app"] in modes and not matches(state, modes[state["app"]]):
            bad.append("switch %d: %s" % (n + 1, state))
    return check(label, not bad, "; ".join(bad) or "every tab showed its mode")


def run(office, check, folder):
    """Open the documents, then the scenarios; `check(name, ok, detail)` records a result."""
    open_documents(office, folder)
    run_after_open(office, check, folder)


def run_after_open(office, check, folder):
    """The scenarios on the open Writer and Sheets tabs (new documents go to `folder`)."""
    # Mixed modes in one window: Writer Standard Toolbar, Sheets Tabbed.
    apply_mode(office, "Writer", "Default")
    switch_and_judge(office, check, "mixed modes: Writer Standard Toolbar, Sheets Tabbed",
                     {"Writer": "Default", "Calc": "notebookbar.ui"})
    # Sheets once Standard then Tabbed again (its toolbars stored as invisible), then "Apply to All" from Writer.
    apply_mode(office, "Calc", "Default")
    apply_mode(office, "Calc", "notebookbar.ui")
    apply_mode(office, "Writer", "Default", to_all=True)
    switch_and_judge(office, check, "Apply to All from Writer: the Sheets tab shows Standard Toolbar",
                     {"Writer": "Default", "Calc": "Default"})
    # Back to Tabbed for all, from the Sheets tab.
    apply_mode(office, "Calc", "notebookbar.ui", to_all=True)
    switch_and_judge(office, check, "Apply to All from Sheets: both tabs Tabbed",
                     {"Writer": "notebookbar.ui", "Calc": "notebookbar.ui"})
    # The reporter's steps: every mode in turn on one module, then Standard Toolbar for all with the toolbars
    # locked, then a document of the other module opened from the window (a new tab), in both directions.
    for app, other, (_o, factory, name, filter_name) in (("Writer", "Calc", DOCS[0]), ("Calc", "Writer", DOCS[1])):
        apply_mode(office, app, "notebookbar.ui", to_all=True)
        for mode in CYCLE:
            apply_mode(office, app, mode)
        apply_mode(office, app, "Default", to_all=True)
        frame = goto(office, app)
        layout = frame.LayoutManager
        for element in layout.getElements():
            if "/toolbar/" in element.ResourceURL and layout.isElementVisible(element.ResourceURL):
                layout.lockWindow(element.ResourceURL)
        url = make_document(office, factory, os.path.join(folder, "moi-" + name), filter_name)
        office.desktop.loadComponentFromURL(url, "_blank", 0, ())
        time.sleep(4)
        state = tab_state(shown(office.desktop))
        check("modes in turn on %s, Standard Toolbar for all, locked, new %s tab" % (app, other),
              state["app"] == other and matches(state, "Default"), str(state))
        # the second pass cycles a module whose other tab is parked: it must come back with its menubar
        switch_and_judge(office, check, "after the new %s tab: every tab Standard Toolbar" % other,
                         {"Writer": "Default", "Calc": "Default"}, switches=6)
