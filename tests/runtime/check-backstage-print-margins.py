#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Margins box of the File panel's Print page (hst-backstage-print.patch) end to end, widgets driven by id through
the UITest service (no keys). Usage: <office python> check-backstage-print-margins.py --soffice PATH --out DIR
[--shot CMD] [--no-pdf-printer]
Writer and Sheets: .uno:Print opens the page; the box shows the preset of the document (2 cm: "Bình thường");
picking a preset gives the page style its margins in one undo step ("Đổi lề trang"), the preview counts the new pages
and the job prints them; one undo gives the old margins back; "Lề tùy chỉnh" opens Page Setup. Slides: no box.
Exit 1 on a failure.
"""
import argparse, glob, importlib.util, os, sys, tempfile, time  # noqa: E401

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_spec = importlib.util.spec_from_file_location("check_backstage_print", os.path.join(HERE, "check-backstage-print.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
check, state, failures = base.check, base.state, base.failures

# entries of the box, in its order; margins in 1/100 mm (left, right, top, bottom) as the page style reports them
PRESETS = [("Bình thường", (2004,) * 4), ("Hẹp", (1270,) * 4), ("Vừa", (1905, 1905, 2540, 2540)),
           ("Rộng", (5080, 5080, 2540, 2540))]
CUSTOM, UNDO_TITLE = 4, "Đổi lề trang"


def props(**values):
    from com.sun.star.beans import PropertyValue
    out = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        out.append(prop)
    return tuple(out)


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
    """A document of several pages whose page count follows its margins, its page style at 2 cm."""
    doc = office.desktop.loadComponentFromURL(f"private:factory/{app}", "_blank", 0, ())
    if app == "swriter":
        text = doc.Text
        for n in range(60):
            text.insertString(text.getEnd(), "HST margins %d. " % n + "Synthetic paragraph text. " * 12, False)
            text.insertControlCharacter(text.getEnd(), 0, False)
    elif app == "scalc":
        doc.Sheets.getByIndex(0).getCellRangeByPosition(0, 0, 13, 119).setDataArray(
            tuple(tuple("R%dC%d text" % (r, c) for c in range(14)) for r in range(120)))
    if app in ("swriter", "scalc"):
        style = page_style(doc, app)
        for prop in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin"):
            style.setPropertyValue(prop, 2000)
    return doc


def wait_panel(office, timeout=30):
    for _ in range(timeout * 2):
        top = office.ui.getTopFocusWindow()
        if {"ok", "totalnumpages", "moreoptions"} <= set(top.getChildren()):
            return top
        time.sleep(0.5)


def open_page(office, doc):
    office.ui.executeCommandForProvider(".uno:Print", doc.getCurrentController().getFrame())
    top = wait_panel(office)
    time.sleep(3)  # the preview is painted on idle
    return top


def pick(office, doc, app, index, pdf_dir, shot):
    """Pick preset index on the open page; checks margins, undo step, preview and the printout."""
    top = wait_panel(office)
    before_pages = state(top.getChild("totalnumpages")).get("Text")
    old, undo = margins(doc, app), doc.UndoManager
    titles = len(undo.getAllUndoActionTitles())
    name, want = PRESETS[index]
    top.getChild("marginsbox").executeAction("SELECT", props(POS=str(index)))
    time.sleep(4)
    top = wait_panel(office)
    check(top is not None, f"{app}: {name}: the job stays on the Print page")
    check(near(margins(doc, app), want), f"{app}: {name}: the page style has {want} ({margins(doc, app)})")
    all_titles = undo.getAllUndoActionTitles()
    check(len(all_titles) == titles + 1 and all_titles[0] == UNDO_TITLE,
          f"{app}: {name}: one undo step '{UNDO_TITLE}' ({all_titles[:2]})")
    if top is None:
        return
    shown = state(top.getChild("marginsbox")).get("SelectEntryText")
    check(shown == name, f"{app}: {name}: the box shows it ({shown})")
    after_pages = state(top.getChild("totalnumpages")).get("Text")
    check(after_pages != before_pages,
          f"{app}: {name}: the preview counts the new pages ({before_pages} -> {after_pages})")
    shot(f"{app}-margins-{index}.png")
    if pdf_dir:
        before = set(glob.glob(os.path.join(pdf_dir, "*.pdf")))
        top.getChild("ok").executeAction("CLICK", ())
        printed = base.wait_pdf(pdf_dir, before)
        pages = printed and base.pdf_summary(printed)[0][0].split()[-1]
        check(printed and f"/ {pages}" == after_pages, f"{app}: {name}: the printout has the preview's pages ({pages})")
    undo.undo()
    time.sleep(1)
    check(near(margins(doc, app), old), f"{app}: one undo gives the margins back ({margins(doc, app)})")


def check_custom(office, doc, app, shot):
    top = open_page(office, doc)
    shown = top and state(top.getChild("marginsbox")).get("SelectEntryText")
    check(shown == PRESETS[0][0], f"{app}: the box shows the 2 cm page style as {PRESETS[0][0]} ({shown})")
    if top is None:
        return
    panel_id = state(top).get("ID")
    top.getChild("marginsbox").executeAction("SELECT", props(POS=str(CUSTOM)))
    for _ in range(40):
        dialog = office.ui.getTopFocusWindow()
        if state(dialog).get("ID") != panel_id and "cancel" in dialog.getChildren():
            break
        time.sleep(0.5)
    else:
        dialog = None
    check(dialog is not None, f"{app}: Lề tùy chỉnh opens Page Setup ({dialog and state(dialog).get('ID')})")
    shot(f"{app}-margins-custom.png")
    dialog and dialog.getChild("cancel").executeAction("CLICK", ())
    time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsmargins-"))  # noqa
    parser.add_argument("--shot", help="screenshot command with {} for the file")
    parser.add_argument("--no-pdf-printer", action="store_true", help="no printer of the profile, no printing")
    args = parser.parse_args()
    out = os.path.abspath(args.out)  # noqa
    os.makedirs(pdf_dir := os.path.join(out, "pdf"), exist_ok=True)
    shot = lambda name: args.shot and os.system(args.shot.format(os.path.join(out, name)))  # noqa: E731
    office = base.VisibleOffice(args.soffice, out, None if args.no_pdf_printer else pdf_dir)
    docs = []
    try:
        for app, index in (("swriter", 1), ("scalc", 3)):
            docs.append(doc := make_doc(office, app))
            office.close_welcome()
            check(open_page(office, doc) is not None, f"{app}: .uno:Print opens the Print page")
            pick(office, doc, app, index, None if args.no_pdf_printer else pdf_dir, shot)
            office.ui.executeCommandForProvider(".uno:HSTBackstage", doc.getCurrentController().getFrame())
            time.sleep(1)
            check_custom(office, doc, app, shot)
        docs.append(doc := make_doc(office, "simpress"))
        top = open_page(office, doc)
        visible = top and state(top.getChild("marginsbox")).get("ReallyVisible")
        check(top is not None and str(visible).lower() == "false", f"simpress: no margins box ({visible})")
        office.ui.executeCommandForProvider(".uno:HSTBackstage", doc.getCurrentController().getFrame())
        for doc in docs:
            doc.setModified(False)  # the office quits without asking
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
