#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""What the template lists of a real HST Office offer, and screenshots of each list to look at.

Usage: python3 tests/runtime/check-template-lists.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/template-lists] [--shots tests/output/screenshots-template-lists] [--display :97]

Over UNO: the installed template files, the groups in com.sun.star.frame.DocumentTemplates and their titles. No upstream
English sample and no Draw BPMN template; the three style templates and the 18 HST templates stay. Prints what is left
per application and any template whose description names the upstream project (it reaches a new document's properties).
Screenshots (Start Center, Template Manager, File view "Mới" of each application): a text search cannot see images, so a
person opens them. Exit 1 when a check fails.
"""
import argparse
import os
import subprocess
import sys
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
COMMAND = ".uno:HSTBackstage"
GONE = ("officorr/Modern_business_letter_sans_serif.ott", "officorr/Modern_business_letter_serif.ott",
        "offimisc/Businesscard-with-logo.ott", "personal/CV.ott", "personal/Resume1page.ott", "draw/bpmn.otg")
STAY = ("styles/Default.ott", "styles/Modern.ott", "styles/Simple.ott")
HST_GROUPS = {"HST — Văn bản hành chính": 7, "HST — Bảng tính": 6, "HST — Trình chiếu": 5}
APPS = (("swriter", "Writer"), ("scalc", "Sheets"), ("simpress", "Slides"))


def groups_of(office):
    """{group title: [template title]} from the template service (UCB "open" on the hierarchy)."""
    import uno
    from com.sun.star.beans import Property
    from com.sun.star.ucb import OpenCommandArgument2
    templates = office.service("com.sun.star.frame.DocumentTemplates")
    templates.update()
    ucb = office.service("com.sun.star.ucb.UniversalContentBroker")

    def children(content):
        arg = OpenCommandArgument2()
        arg.Mode = 0  # com.sun.star.ucb.OpenMode.ALL
        prop = Property()
        prop.Name, prop.Handle = "Title", -1
        arg.Properties = (prop,)
        command = uno.createUnoStruct("com.sun.star.ucb.Command")
        command.Name, command.Handle = "open", -1
        command.Argument = arg
        rows = content.execute(command, 0, None).getStaticResultSet()
        found = []
        while rows.next():
            found.append((rows.getString(1), ucb.createContentIdentifier(rows.queryContentIdentifierString())))
        return found

    return {title: [name for name, _c in children(ucb.queryContent(child))] for title, child in children(templates.getContent())}


def descriptions_naming_upstream(instdir):
    folder = os.path.join(instdir, "share", "template", "common", "presnt")
    named = []
    for name in sorted(os.listdir(folder)):
        with zipfile.ZipFile(os.path.join(folder, name)) as package:
            meta = package.read("meta.xml").decode("utf-8", "replace")
        if "LibreOffice" in meta.split("<dc:description>")[-1].split("</dc:description>")[0] and "<dc:description>" in meta:
            named.append(name)
    return named


def shot_lists(office, args, check):
    env = dict(os.environ, DISPLAY=args.display)
    frame = office.desktop().getCurrentFrame()
    start = hst_gui.toplevels(args.display, office.pid)[0][0]
    # "Mẫu" in the Start Center's left column
    subprocess.run(["xdotool", "mousemove", "--window", start, "60", "195", "click", "1"], env=env, check=False, timeout=10)
    time.sleep(2)
    hst_gui.screenshot(os.path.join(args.shots, "start-center-mau.png"), args.display)
    worker = threading.Thread(target=office.dispatch, args=(frame, ".uno:NewDoc"), daemon=True)
    worker.start()
    time.sleep(6)
    hst_gui.screenshot(os.path.join(args.shots, "template-manager.png"), args.display)
    names = hst_gui.toplevels(args.display, office.pid)
    check("Template Manager opens", len(names) >= 2, repr([n for _w, n in names]))
    for wid, name in names:
        if " — HST " not in name and name != "HST Office":
            subprocess.run(["xdotool", "windowfocus", wid, "key", "Escape"], env=env, check=False, timeout=10)
    worker.join(15)
    for factory, label in APPS:
        doc = office.load(f"private:factory/{factory}")
        time.sleep(2)
        frame = doc.getCurrentController().getFrame()
        office.dispatch(frame, COMMAND)
        time.sleep(3)
        home = os.path.join(args.shots, f"file-view-home-{label.lower()}.png")
        moi = os.path.join(args.shots, f"file-view-moi-{label.lower()}.png")
        hst_gui.screenshot(home, args.display)
        wid = [w for w, n in hst_gui.toplevels(args.display, office.pid) if n.endswith("HST " + label)][-1]
        # "Mới" is the second item of the left column, at this place of the window in every application
        subprocess.run(["xdotool", "mousemove", "--window", wid, "60", "126", "click", "1"], env=env, check=False, timeout=10)
        time.sleep(3)
        hst_gui.screenshot(moi, args.display)
        with open(home, "rb") as first, open(moi, "rb") as second:
            check(f"{label}: File view Mới opens", first.read() != second.read())
        office.dispatch(frame, COMMAND)
        time.sleep(1)
        doc.setModified(False)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/template-lists"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-template-lists"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.shots, exist_ok=True)
    failures = []

    def check(name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
        if not ok:
            failures.append(name)

    common = os.path.join(os.path.abspath(args.instdir), "share", "template", "common")
    for rel in GONE:
        check(f"not installed: {rel}", not os.path.exists(os.path.join(common, rel)))
    for rel in STAY:
        check(f"installed: {rel}", os.path.isfile(os.path.join(common, rel)))
    hst_gui.setup_uno(args.instdir)
    office = hst_gui.Office(args.instdir, args.out, 22001, display=args.display, nodefault=False,
                            config=[("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]).start()
    try:
        groups = groups_of(office)
        for group, count in HST_GROUPS.items():
            check(f"group {group}: {count} templates", len(groups.get(group, [])) == count, ", ".join(groups.get(group, [])))
        titles = [title for names in groups.values() for title in names]
        for title in ("Businesscard with logo", "CV", "Resume", "Modern business letter serif", "Modern business letter sans-serif", "BPMN"):
            check(f"not listed: {title}", title not in titles)
        for group, names in sorted(groups.items()):
            print(f"LEFT  {group}: {len(names)}: {', '.join(names)}", flush=True)
        print("Descriptions naming the upstream project:", ", ".join(descriptions_naming_upstream(args.instdir)) or "none", flush=True)
        shot_lists(office, args, check)
    finally:
        office.stop()
    print(f"template lists: {len(failures)} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
