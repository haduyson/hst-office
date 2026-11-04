# SPDX-License-Identifier: AGPL-3.0-only
"""Check the HASON TECH banner in the ribbon of HST Writer, Sheets and Slides (gtk3, real GUI).

Usage: python3 tests/runtime/check-ribbon-banner.py [--instdir upstream/libreoffice/instdir]
           [--baseline-instdir DIR] [--display :93] [--display-hidpi :94] [--apps writer,calc,impress]
           [--out tests/output/ribbon-banner] [--shots DIR]

Per app at 1485x900 (vi UI, fake xdg-open on PATH that logs URLs, so no browser opens): the banner is
found in the AT-SPI tree (role link, name "<name> — <tagline>") and recognised in a screenshot as that
bundled artwork; hovering pauses the rotation; a click opens its URL with UTM; with keyboard focus Enter
opens it again; with focus elsewhere it rotates to another item within rotateSeconds + 2 s and the new
item's accessible name matches; at 1100x700 it is hidden and at 1485x900 it returns. The ribbon height (frame top to document
tab bar) is the same with the banner shown and hidden, and equals the baseline build (--baseline-instdir,
a build without the banner) at the same window size, at 100 % and with GDK_SCALE=2 (--display-hidpi,
an Xvfb of at least 3000x1820). Fallback: in a hard-linked copy of the installation with the feed
service broken and the AIOS art replaced by a 2000x600 image, the installed defaults still show and the
odd image is fitted into the unchanged slot. Also a dark-theme screenshot (GTK_THEME=Adwaita:dark).
Writes evidence.json; exit 1 when a check fails. The X displays must already run.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_banner_probe as probe  # noqa: E402
from ribbon_banner_run import Run, xdo  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    return ok


def device_box(run, record):
    """AT-SPI extents as screenshot pixels."""
    return [v * run.factor() for v in record["box"]]


def item_of(catalogue, ident):
    return next((i for i in catalogue if i["id"] == ident), None)


def main_flow(args, catalogue, rotate, app, scale, display):
    tag = f"{app}-x{scale}"
    label = lambda what: f"[{tag}] {what}"  # noqa: E731
    shots = args.shots if scale == 1 else None
    with Run(args, args.instdir, app, display, scale, tag) as run:
        height = run.ribbon_height() * scale
        wide_shot = run.shot("01-wide", shots)
        node = run.banner()
        if not check(label("1485x900: banner visible in the accessibility tree, role link"), node is not None):
            return {"height": height, "shot": wide_shot}
        record = probe.describe(node)
        box = device_box(run, record)
        run.hover(box)  # hover pauses: name and drawing belong together from here on
        time.sleep(1.5)
        drawn = probe.recognise(run.shot("02-hover"), box, catalogue, scale)
        record = probe.describe(run.banner())
        item = item_of(catalogue, drawn[0])
        check(label("drawn art is a bundled item"), item is not None, repr(drawn))
        check(label("slot keeps 360:104, at most 360 px per scale"),
              box[2] <= 360 * scale and abs(box[2] / box[3] - 360 / 104) < 0.2, repr(box))
        check(label("slot lies inside the ribbon, not over the document"),
              run.frame[1] < box[1] and box[1] + box[3] <= run.frame[1] + height, f"{box} ribbon={height}")
        if item:
            check(label("accessible name = '<name> — <tagline>' of the drawn item"), record["name"] == item["label"],
                  record["name"])
            if scale == 1:
                time.sleep(rotate + 2)
                held = probe.recognise(run.shot("02-hover-held"), box, catalogue, scale)[0]
                check(label(f"hover pauses the rotation for {rotate + 2} s"), held == item["id"], repr(held))
            # the destination depends on the real click counter here; check_ribbon_banner_click.py stubs it
            run.click(box)
            opened = run.opener.wait_for(1)
            check(label("click opens the item URL with UTM, or the home page"),
                  opened[-1:] in ([item["url"]], [item["home"]]), repr(opened[-1:]))
            time.sleep(1.3)  # double clicks within a second open one tab
            run.banner().queryComponent().grabFocus()
            time.sleep(0.5)
            xdo(display, "key", "Return")
            opened = run.opener.wait_for(2)
            check(label("Enter on the focused banner opens it"), opened[-1:] in ([item["url"]], [item["home"]]),
                  repr(opened[-1:]))
        run.leave()
        start, first, changed = time.time(), drawn[0], None
        while time.time() - start < rotate + 2 and changed is None:
            now = probe.recognise(run.shot("03-rotating"), box, catalogue, scale)[0]
            changed = now if now and now != first else None
            time.sleep(0.3)
        check(label(f"rotates to another item within rotateSeconds+2 = {rotate + 2} s"), first and changed,
              f"{first} -> {changed} after {time.time() - start:.1f}s")
        if changed:
            run.hover(box)
            time.sleep(0.5)
            drawn = probe.recognise(run.shot("03-after"), box, catalogue, scale)
            item = item_of(catalogue, drawn[0])
            name = probe.describe(run.banner())["name"]
            check(label("after rotation: accessible name matches the drawn item"),
                  bool(item) and name == item["label"], f"{drawn} {name}")
            run.leave()
        run.size(1100, 700)
        run.shot("04-narrow", shots)
        check(label("1100x700: banner hidden"), run.banner() is None)
        narrow_height = run.ribbon_height() * scale
        check(label("ribbon height identical with banner shown and hidden"), narrow_height == height,
              f"shown={height} hidden={narrow_height}")
        run.size(1485, 900)
        back = run.banner()
        check(label("1485x900 again: banner shown"), back is not None)
        return {"height": height, "box": box, "shot": wide_shot}


if __name__ == "__main__":
    from check_ribbon_banner_extra import main  # noqa: E402 - argument parsing, fallback and dark runs
    sys.exit(main(sys.modules[__name__]))
