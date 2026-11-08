#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Start Center "Tài liệu gần đây" thumbnail of a PDF with a faint diagonal stamp, on an INSTALLED HST Office (Windows).

The PDF is synthetic (pdf_translucent_stamp_sample: black stamp text under /ca 0.1, signature widgets). It is opened as
a user does: once in HST Draw (draw_pdf_import, as "Chỉnh sửa bằng HST Draw" or an older build did), then in HST PDF
(the default). After each close the recent-documents thumbnail is read from the profile
(Histories/PickList Thumbnail, the picture the Start Center draws) and its stamp band measured: a stamp drawn as faint
as in the opened file keeps every pixel there light; one drawn without its /ca is black. The office is then started
again and the Start Center photographed.

Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-pdf-recent-thumbnail.py --install DIR --out DIR
[--port 2119]. Evidence: <out>/opened-*.png, <out>/thumbnail-*.png, <out>/start-center.png. Exit 1 on any FAIL.
"""
import argparse
import base64
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pdf_translucent_stamp_sample as sample  # noqa: E402
import png_luma  # noqa: E402
import windows_gui as wg  # noqa: E402

FAINT = 200  # darkest stamp pixel: /ca 0.1 black on white renders about 229; a dropped /ca renders 0


def thumbnail(office, name):
    """PNG bytes of the recent-documents thumbnail of the entry whose URL ends with `name`, or None."""
    items = office.config("/org.openoffice.Office.Histories/Histories", None).getByName("PickList").getByName("ItemList")
    for url in items.getElementNames():
        if url.endswith(name):
            data = items.getByName(url).getPropertyValue("Thumbnail")
            return base64.b64decode(data) if data else None
    return None


def measure(check, office, name, label, out):
    data = thumbnail(office, name)
    if not data:
        check.note("thumbnail after %s" % label, "none: the Start Center shows the generic icon")
        return None
    path = os.path.join(out, "thumbnail-%s.png" % label)
    with open(path, "wb") as handle:
        handle.write(data)
    width, height, luma = png_luma.read(data)
    darkest, dark_share = png_luma.band_stats(luma, *sample.STAMP_BAND)
    check.note("thumbnail after %s" % label, "%dx%d, stamp band darkest %d, dark share %.4f (%s)"
               % (width, height, darkest, dark_share, path))
    return darkest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2119)
    args = parser.parse_args()
    out, install = os.path.abspath(args.out), os.path.abspath(args.install)
    check = wg.Results(out, "pdf-recent-thumbnail")
    pdf = sample.write(os.path.join(out, "hst-stamp-test.pdf"))
    import uno
    url = uno.systemPathToFileUrl(pdf)
    office = wg.WinOffice(install, os.path.join(out, "profile"), args.port, os.path.join(out, "logs"))
    try:
        office.start(fresh=True)
        check.note("start-up dialog closed first", wg.dismiss_startup(office, os.path.join(out, "startup-dialog.png")))
        darkest = {}
        for label, props in (("hst-draw", {"FilterName": "draw_pdf_import"}), ("hst-pdf", {})):
            component = office.load(url, **props)
            check("the PDF opens in %s" % label, component is not None, getattr(component, "ImplementationName", None))
            time.sleep(4)
            wg.screenshot(os.path.join(out, "opened-%s.png" % label))
            try:
                frame = component.getFrame() if hasattr(component, "getFrame") else component.getCurrentController().getFrame()
                frame.close(True)
            except Exception:  # noqa: BLE001 - a controller without a frame of its own
                component.close(True)
            time.sleep(2)
            darkest[label] = measure(check, office, os.path.basename(pdf), label, out)
        last = darkest["hst-pdf"] if darkest["hst-pdf"] is not None else darkest["hst-draw"]
        check("the recent-documents thumbnail draws the stamp faint, as in the opened file (darkest > %d)" % FAINT,
              last is not None and last > FAINT, darkest)
        office.stop()
        office.start()
        wg.dismiss_startup(office, os.path.join(out, "startup-dialog-2.png"), timeout=15)
        time.sleep(4)
        start_center = wg.find_window(lambda title: title.startswith("HST Office"), timeout=10)
        if start_center:
            wg.foreground(start_center[0])
        wg.screenshot(os.path.join(out, "start-center.png"))
        check.note("Start Center window", start_center)
    except Exception:  # noqa: BLE001
        import traceback
        check("harness", False, traceback.format_exc())
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    sys.exit(main())
