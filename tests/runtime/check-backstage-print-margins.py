#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Margins box of the File panel's Print page (hst-backstage-print.patch) end to end on gtk3, no keys. The office side
runs in the office's python (UNO); the panel, a popup UITest does not reach, is read and driven through AT-SPI by
backstage_print_atspi.py in the system python3 (pyatspi). Start inside a session bus with the atk bridge:
    dbus-run-session -- env NO_AT_BRIDGE=0 GTK_MODULES=gail:atk-bridge SAL_USE_VCLPLUGIN=gtk3 \
        <office python> check-backstage-print-margins.py --soffice PATH --out DIR [--shot CMD]
Writer and Sheets: .uno:Print opens the page; the box shows the preset of the document ("Bình thường":
Writer 2 cm, Sheets 1,9/1,8 cm as its ribbon's Margins menu; Sheets has no "Vừa"); picking a preset gives the
page style its margins in one undo step ("Đổi lề trang") and the preview counts the new pages; one undo gives the old
margins back; "Lề tùy chỉnh" opens Page Setup. Slides: no box. Exit 1 on a failure.
"""
import argparse, importlib.util, json, os, subprocess, sys, tempfile, time  # noqa: E401

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_spec = importlib.util.spec_from_file_location("check_backstage_print", os.path.join(HERE, "check-backstage-print.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
check, failures = base.check, base.failures
ATSPI = os.path.join(HERE, "backstage_print_atspi.py")

# entries of the box per application, in its order; margins in 1/100 mm (left, right, top, bottom)
PRESETS = {"swriter": {"Bình thường": (2004,) * 4, "Hẹp": (1270,) * 4, "Vừa": (1905, 1905, 2540, 2540),
                       "Rộng": (5080, 5080, 2540, 2540)},
           "scalc": {"Bình thường": (1800, 1800, 1900, 1900), "Hẹp": (640, 640, 1900, 1900), "Rộng": (2540,) * 4}}
NORMAL, CUSTOM, UNDO_TITLE = "Bình thường", "Lề tùy chỉnh", "Đổi lề trang"


def atspi(*args):
    """Run the AT-SPI helper in the system python (outside the office's python environment)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "URE_"))}
    run = subprocess.run(["/usr/bin/python3", ATSPI, *args], capture_output=True, text=True, timeout=120, env=env)
    return json.loads(run.stdout) if run.stdout.strip() else {"error": run.stderr[-300:]}


def page_style(doc, app):
    if app == "swriter":
        name = doc.getCurrentController().getViewCursor().PageStyleName
    else:
        name = doc.getCurrentController().getActiveSheet().PageStyle
    return doc.StyleFamilies.getByName("PageStyles").getByName(name)


def margins(doc, app):
    style = page_style(doc, app)
    return style.LeftMargin, style.RightMargin, style.TopMargin, style.BottomMargin


def near(got, want, slack=3):
    return all(abs(g - w) <= slack for g, w in zip(got, want))


def make_doc(office, app):
    """A document of several pages whose page count follows its margins, its page style at "Bình thường"."""
    doc = office.desktop.loadComponentFromURL(f"private:factory/{app}", "_blank", 0, ())
    if app == "swriter":
        text = doc.Text
        for n in range(200):  # about 16 pages: narrower margins need fewer
            text.insertString(text.getEnd(), "HST margins %d. " % n + "Synthetic paragraph text. " * 12, False)
            text.insertControlCharacter(text.getEnd(), 0, False)
    elif app == "scalc":
        # 16 columns: 7 a page wide at 1,8 cm left and right, 8 at 0,64 cm
        doc.Sheets.getByIndex(0).getCellRangeByPosition(0, 0, 15, 119).setDataArray(
            tuple(tuple("R%dC%d text" % (r, c) for c in range(16)) for r in range(120)))
    if app in ("swriter", "scalc"):
        style = page_style(doc, app)
        for prop, value in zip(("LeftMargin", "RightMargin", "TopMargin", "BottomMargin"), PRESETS[app][NORMAL]):
            style.setPropertyValue(prop, value)
    return doc


def step_box(steps):
    """Move the margins box steps entries down from the one it shows (keys on the private display only)."""
    subprocess.run(["xdotool", "mousemove", "450", "650"], check=False, timeout=30)
    focused = atspi("focus").get("focused")
    check(bool(focused), "the margins box takes the focus")
    subprocess.run(["xdotool", "key", "--delay", "300", *["Down"] * steps], check=False, timeout=30)


def scroll_settings():
    """Wheel the settings column down (pointer on the private display only) so the shot shows the margins box."""
    subprocess.run(["xdotool", "mousemove", "450", "650", "click", "--repeat", "25", "5"], check=False, timeout=30)
    time.sleep(1)


def wait_page(timeout=40):
    """The Print page's state once its preview counts the pages, else the last state."""
    for _ in range(timeout):
        page = atspi("state")
        if page.get("pages"):
            return page
        time.sleep(1)
    return page


def open_page(office, doc):
    office.ui.executeCommandForProvider(".uno:Print", doc.getCurrentController().getFrame())
    page = wait_page()
    time.sleep(2)  # the preview is painted on idle
    return atspi("state") if page.get("pages") else page


def pick(doc, app, name, shot):
    """Pick preset name on the open page; checks entries, margins, undo step and preview."""
    page = atspi("state")
    old, undo = margins(doc, app), doc.UndoManager
    titles = len(undo.getAllUndoActionTitles())
    want = PRESETS[app][name]
    check(page.get("showing"), f"{app}: the margins box is there ({page})")
    step_box(list(PRESETS[app]).index(name))  # from "Bình thường", the application's presets in order
    time.sleep(4)
    after = atspi("state")
    check(bool(after.get("pages")), f"{app}: {name}: the job stays on the Print page")
    check(near(margins(doc, app), want), f"{app}: {name}: the page style has {want} ({margins(doc, app)})")
    all_titles = undo.getAllUndoActionTitles()
    check(len(all_titles) == titles + 1 and all_titles[0] == UNDO_TITLE,
          f"{app}: {name}: one undo step '{UNDO_TITLE}' ({all_titles[:2]})")
    check(after.get("pages") != page.get("pages"),
          f"{app}: {name}: the preview counts the new pages ({page.get('pages')} -> {after.get('pages')})")
    scroll_settings()
    shot(f"{app}-margins-{list(PRESETS[app]).index(name)}.png")
    undo.undo()
    time.sleep(1)
    check(near(margins(doc, app), old), f"{app}: one undo gives the margins back ({margins(doc, app)})")


def check_custom(office, doc, app, shot):
    open_page(office, doc)  # the shot shows the box at the page style's preset (NORMAL)
    scroll_settings()
    shot(f"{app}-margins-normal.png")
    step_box(len(PRESETS[app]))  # the last entry: "Lề tùy chỉnh"
    for _ in range(30):
        if (found := atspi("dialog").get("dialog")) is not None:
            break
        time.sleep(1)
    check(found is not None, f"{app}: {CUSTOM} opens Page Setup ({found})")
    shot(f"{app}-margins-custom.png")
    atspi("dialog", "cancel")
    time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsmargins-"))  # noqa
    parser.add_argument("--shot", help="screenshot command with {} for the file")
    args = parser.parse_args()
    out = os.path.abspath(args.out)  # noqa
    os.makedirs(out, exist_ok=True)
    shot = lambda name: args.shot and os.system(args.shot.format(os.path.join(out, name)))  # noqa: E731
    office = base.VisibleOffice(args.soffice, out, None)
    docs = []
    try:
        # one step down from "Bình thường": each entry the box passes changes the margins (one undo step each)
        for app, name in (("swriter", "Hẹp"), ("scalc", "Hẹp")):
            docs.append(doc := make_doc(office, app))
            office.close_welcome()
            page = open_page(office, doc)
            check(bool(page.get("pages")), f"{app}: .uno:Print opens the Print page ({page})")
            shot(f"{app}-print-page.png")
            pick(doc, app, name, shot)
            office.ui.executeCommandForProvider(".uno:HSTBackstage", doc.getCurrentController().getFrame())
            time.sleep(1)
            check_custom(office, doc, app, shot)
        for doc in docs:  # their File panels are on the accessibility bus too
            doc.setModified(False)
            doc.close(True)
        docs = [doc := make_doc(office, "simpress")]
        page = open_page(office, doc)
        check(bool(page.get("pages")) and not page.get("showing"), f"simpress: no margins box ({page})")
        scroll_settings()
        shot("simpress-no-margins.png")
        office.ui.executeCommandForProvider(".uno:HSTBackstage", doc.getCurrentController().getFrame())
        for doc in docs:
            doc.setModified(False)  # the office quits without asking
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
