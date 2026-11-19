# SPDX-License-Identifier: AGPL-3.0-only
"""Screenshots of the new Start Center (hst-start-center-redesign.patch) in one look: light or dark, 100 % or 125 %.

Usage: python3 tests/runtime/check-start-center-redesign.py --instdir DIR --out DIR --display :396
           [--theme light|dark] [--scale 1.0|1.25] [--lang vi_VN.UTF-8|en_US.UTF-8] [--size 1366x768]

The display must already run at the given size (e.g. `Xvfb :396 -screen 0 1366x768x24`); the check never starts or
stops it. 125 % is the font scale of the desktop (Xft.dpi 120, set here on the display with xrdb), dark is the
GTK theme Adwaita:dark. Five sample documents in five folders are created and opened once, so they are the recent
documents; two are pinned through the profile's history; the last one is closed with Close Document, which shows
the Start Center in the same window as a user sees it. Checks: the Start Center is shown, its window holds no
horizontal scroll bar (the window keeps its size), and the screenshot is kept as <out>/start-center-<look>.png.
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

SAMPLES = [("Báo cáo", "Báo cáo tổng kết quý 3.docx", "swriter", "MS Word 2007 XML"),
           ("Tài chính", "Kế hoạch ngân sách 2027.xlsx", "scalc", "Calc MS Excel 2007 XML"),
           ("Dự án", "Hồ sơ dự án chuyển đổi số.docx", "swriter", "MS Word 2007 XML"),
           ("Marketing", "Bài thuyết trình giới thiệu sản phẩm.pptx", "simpress", "Impress MS PowerPoint 2007 XML"),
           ("Công việc", "Danh sách công việc tháng 11.xlsx", "scalc", "Calc MS Excel 2007 XML")]
PINNED = ("Hồ sơ dự án chuyển đổi số.docx", "Kế hoạch ngân sách 2027.xlsx")


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    result = PropertyValue()
    result.Name, result.Value = name, value
    return result


def file_url(path):
    import uno
    return uno.systemPathToFileUrl(path)


def make_samples(office, root):
    urls = []
    for folder, _name, _factory, _filter in SAMPLES:
        os.makedirs(os.path.join(root, folder), exist_ok=True)
    if os.geteuid() == 0:  # the office runs as the build user
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, root], check=True)
    for folder, name, factory, filter_name in SAMPLES:
        path = os.path.join(root, folder, name)
        if not os.path.exists(path):
            doc = office.desktop().loadComponentFromURL("private:factory/" + factory, "_blank", 0,
                                                        (prop("Hidden", True), prop("OnMainThread", True)))
            doc.storeToURL(file_url(path), (prop("FilterName", filter_name),))
            doc.close(True)
        urls.append((name, file_url(path)))
    return urls


def pin(office, urls):
    provider = office.service("com.sun.star.configuration.ConfigurationProvider")
    access = provider.createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess",
        (prop("nodepath", "/org.openoffice.Office.Histories/Histories/PickList/ItemList"),))
    names = access.getElementNames()
    for url in names:
        if url in urls:
            access.getByName(url).setPropertyValue("Pinned", True)
    access.commitChanges()
    return len(names)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--display", default=":396")
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--lang", default="vi_VN.UTF-8")
    parser.add_argument("--size", default="1366x768")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    width, height = (int(v) for v in args.size.split("x"))
    look = "%s-%d" % (args.theme, round(args.scale * 100))
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    subprocess.run(["xrdb", "-display", args.display, "-merge", "-"], input="Xft.dpi: %d\n" % round(96 * args.scale),
                   text=True, check=True)
    hst_gui.setup_uno(args.instdir)
    env = {"GTK_THEME": "Adwaita:dark" if args.theme == "dark" else "Adwaita"}
    office = hst_gui.Office(args.instdir, os.path.join(out, "work-" + look), args.port or hst_gui.free_port(),
                            display=args.display, lang=args.lang, env=env)
    failures = []
    try:
        office.start()
        samples = make_samples(office, os.path.join(out, "samples"))
        frames = []
        for _name, url in samples:
            doc = office.desktop().loadComponentFromURL(url, "_blank", 0, (prop("OnMainThread", True),))
            frames.append(doc.getCurrentController().getFrame())
        print("recent documents in the history:", pin(office, [url for name, url in samples if name in PINNED]))
        for frame in frames[:-1]:
            frame.close(True)
        last = frames[-1]
        last.getContainerWindow().setPosSize(0, 0, width, height, 15)
        office.dispatch(last, ".uno:CloseDoc")
        time.sleep(3)
        last.getContainerWindow().setPosSize(0, 0, width, height, 15)
        time.sleep(4)  # the Start Center replaces the document; its banner settles
        component = last.getController()
        shown = component is not None and component.getImplementationName() == "com.sun.star.comp.sfx2.BackingComp"
        if not shown:
            failures.append("the Start Center is not shown after Close Document")
        size = last.getContainerWindow().getPosSize()
        if size.Width > width + 2:
            failures.append("the window grew to %d px: a column does not fit" % size.Width)
        shot = office.screenshot(os.path.join(out, "start-center-%s.png" % look))
        print("screenshot:", shot)
    finally:
        office.stop()
        subprocess.run(["xrdb", "-display", args.display, "-merge", "-"], input="Xft.dpi: 96\n", text=True, check=False)
    for failure in failures:
        print("FAIL:", failure)
    print("PASS" if not failures else "FAIL", look)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
