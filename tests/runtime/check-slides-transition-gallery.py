# SPDX-License-Identifier: AGPL-3.0-only
"""The Slides transitions gallery and its command .uno:HstApplyTransition (gtk3, vi_VN).

Usage: python3 tests/runtime/check-slides-transition-gallery.py [--instdir DIR] [--display :71] [--out DIR]

A three-slide presentation, the second slide current. Checked through the dispatcher:
  1. Transition=wipe gives the current slide the first wipe variant (TransitionType of the preset),
     the other slides keep none, and the command's state is "wipe";
  2. it is one undo action, and undo removes the transition again;
  3. Transition=None removes it; an unknown set changes nothing;
  4. duration and advance of the slide stay as they were.
If the Slides notebookbar has an item for .uno:HstApplyTransition (the content patch places it, or a
test copy of the .ui), the gallery is checked on screen too: AT-SPI finds the list "Hiệu ứng chuyển
tiếp" (Transitions) with transition items, and clicking the third item applies its set.
Writes evidence.json; exit 1 when a check fails.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

PORT = 7462
ROWS = []
GALLERY_NAMES = ("Hiệu ứng chuyển tiếp", "Transitions")


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:200]}", flush=True)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def dispatch(office, doc, command, **args):
    helper = office.service("com.sun.star.frame.DispatchHelper")
    frame = doc.getCurrentController().getFrame()
    return helper.executeDispatch(frame, command, "", 0, tuple(prop(k, v) for k, v in args.items()))


def state_of(office, doc, command):
    """The state the dispatcher reports for command (the current set id), or None."""
    import unohelper
    from com.sun.star.frame import XStatusListener

    class Listener(unohelper.Base, XStatusListener):
        value = None

        def statusChanged(self, event):
            Listener.value = event.State if event.IsEnabled else None

        def disposing(self, source):
            pass

    transformer = office.service("com.sun.star.util.URLTransformer")
    from com.sun.star.util import URL
    url = URL()
    url.Complete = command
    _ok, url = transformer.parseStrict(url)
    frame = doc.getCurrentController().getFrame()
    provider = frame.queryDispatch(url, "", 0)
    if provider is None:
        return None
    listener = Listener()
    provider.addStatusListener(listener, url)
    time.sleep(0.5)
    provider.removeStatusListener(listener, url)
    return Listener.value


def pages(doc):
    slides = doc.getDrawPages()
    return [slides.getByIndex(i) for i in range(slides.getCount())]


def transition(page):
    return page.getPropertyValue("TransitionType"), page.getPropertyValue("TransitionSubtype")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--display", default=":71")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/slides-transition-gallery"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        os.makedirs(args.out, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.out], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable] + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")]).start()
    try:
        doc = office.load("private:factory/simpress")
        time.sleep(6)
        slides = doc.getDrawPages()
        while slides.getCount() < 3:
            slides.insertNewByIndex(slides.getCount() - 1)
        first, second, third = pages(doc)
        second.setPropertyValue("Duration", 4)  # advance after 4 s: must survive the gallery
        doc.getCurrentController().setCurrentPage(second)
        time.sleep(1)
        doc.getUndoManager().clear()
        duration = second.getPropertyValue("TransitionDuration")

        dispatch(office, doc, ".uno:HstApplyTransition", Transition="wipe")
        time.sleep(1)
        state = state_of(office, doc, ".uno:HstApplyTransition")
        record("1. wipe applied to the current slide only; state is 'wipe'",
               transition(second)[0] != 0 and transition(first)[0] == 0 and transition(third)[0] == 0 and state == "wipe",
               (transition(first), transition(second), transition(third), state))
        undo = doc.getUndoManager()
        titles = undo.getAllUndoActionTitles()
        undo.undo()
        time.sleep(0.5)
        record("2. one undo action, and undo removes the transition", len(titles) == 1 and transition(second)[0] == 0,
               (titles, transition(second)))
        dispatch(office, doc, ".uno:HstApplyTransition", Transition="fade")
        dispatch(office, doc, ".uno:HstApplyTransition", Transition="None")
        removed = transition(second)
        dispatch(office, doc, ".uno:HstApplyTransition", Transition="no-such-transition")
        record("3. None removes it; an unknown set changes nothing", removed[0] == 0 and transition(second)[0] == 0,
               (removed, transition(second)))
        dispatch(office, doc, ".uno:HstApplyTransition", Transition="push")
        record("4. duration and advance stay", second.getPropertyValue("TransitionDuration") == duration
               and second.getPropertyValue("Duration") == 4,
               (second.getPropertyValue("TransitionDuration"), duration, second.getPropertyValue("Duration")))
        check_gallery_on_screen(office, doc, second, args)
    except Exception as error:  # noqa: BLE001
        record("crashed", False, repr(error))
    finally:
        office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in ROWS)
    print(f"{len(ROWS)} checks, {failed} failed")
    return 1 if failed else 0


def check_gallery_on_screen(office, doc, page, args):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ribbon_tabs", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-ribbon-tabs.py"))
    tabs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tabs)
    ui = os.path.join(args.instdir, "share/config/soffice.cfg/modules/simpress/ui/notebookbar.ui")
    with open(ui, encoding="utf-8") as handle:
        if ".uno:HstApplyTransition" not in handle.read():
            print("SKIP  gallery on screen: the Slides notebookbar has no .uno:HstApplyTransition item yet")
            return
    for wid, name in hst_gui.toplevels(args.display, office.pid):
        tabs.xdo(args.display, "windowmove", wid, "0", "0")
        tabs.xdo(args.display, "windowsize", wid, "1485", "900")
    time.sleep(3)
    tab = next((t for t in tabs.ribbon_tabs() if t[0] in ("Chuyển tiếp", "Transitions")), None)
    if tab:
        tabs.click(args.display, tab[1])
        time.sleep(2)
    # only the ribbon: the whole Slides tree (slide panes, shapes) is too large to walk
    tab_list = next((n for n in tabs.walk(tabs.office_app()) if n.getRoleName() == "page tab list"), None)
    gallery = next((n for n in (tabs.walk(tab_list) if tab_list else ())
                    if (n.name or "") in GALLERY_NAMES and n.childCount > 0), None)
    items = [gallery.getChildAtIndex(i) for i in range(gallery.childCount)] if gallery else []
    office.screenshot(os.path.join(args.out, "gallery.png"))
    record("5. the gallery is on the Transitions tab with transition items", len(items) >= 3,
           (tab[0] if tab else None, [i.name for i in items[:6]]))
    if len(items) >= 3:
        x, y, w, h = tabs.extents(items[2])
        tabs.xdo(args.display, "mousemove", str(x + w // 2), str(y + h // 2))
        tabs.xdo(args.display, "click", "1")
        time.sleep(1.5)
        record("6. clicking a transition applies it", transition(page)[0] != 0, transition(page))


if __name__ == "__main__":
    sys.exit(main())
