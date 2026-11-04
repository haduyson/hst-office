# SPDX-License-Identifier: AGPL-3.0-only
"""check-ribbon-banner.py, part 2: URL logger, fallback/oversized-image run, dark theme, entry point."""
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time

import hst_gui
import ribbon_banner_probe as probe


class Opener:
    """Fake xdg-open on PATH that appends every opened URL to a log file (SystemShellExecute ends there)."""

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.log = os.path.join(directory, "opened-urls.log")
        open(self.log, "w").close()
        script = os.path.join(directory, "xdg-open")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(f'#!/bin/sh\necho "$*" >> "{self.log}"\n')
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.directory = directory

    def opened(self):
        return [line.strip() for line in open(self.log, encoding="utf-8") if line.strip()]

    def wait_for(self, count, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline and len(self.opened()) < count:
            time.sleep(0.3)
        return self.opened()


def baseline(main, args, app, scale, display, measured):
    """Same window in a build without the banner: ribbon height and the first group must be identical."""
    from PIL import Image, ImageChops
    tag = f"{app}-x{scale}-baseline"
    with main.Run(args, args.baseline_instdir, app, display, scale, tag) as run:
        height = run.ribbon_height() * scale
        shot = run.shot("01-wide", args.shots if scale == 1 else None)
        frame = run.frame
    main.check(f"[{app}-x{scale}] ribbon height equals the build without banner", height == measured.get("height"),
          f"without={height} with={measured.get('height')}")
    if measured.get("shot"):
        area = (frame[0], frame[1] + 40 * scale, frame[0] + 140 * scale, frame[1] + height)
        diff = ImageChops.difference(Image.open(shot).convert("RGB").crop(area),
                                     Image.open(measured["shot"]).convert("RGB").crop(area)).getbbox()
        main.check(f"[{app}-x{scale}] first group pixel-identical with and without banner", diff is None, repr(diff))
    return height


def fallback_install(instdir, directory):
    """Hard-linked copy of the installation with the feed service broken and an oversized AIOS image.

    Replaced files are unlinked first, so the real installation is never modified."""
    copy = os.path.join(directory, "instdir")
    shutil.rmtree(copy, ignore_errors=True)
    os.makedirs(directory, exist_ok=True)
    # a few stale bytecode files may belong to another user: they cannot be linked and are not needed
    subprocess.run(["cp", "-al", instdir, copy], check=False, stderr=subprocess.DEVNULL)
    if not os.path.isfile(os.path.join(copy, "program/soffice.bin")):
        raise RuntimeError("installation copy failed")
    ext = os.path.join(copy, probe.EXT)
    snapshots = os.path.join(ext, "data/banner-snapshots.json")
    os.unlink(snapshots)
    with open(snapshots, "w", encoding="utf-8") as handle:
        handle.write("{ broken")  # BannerFeed cannot start: the service fails, the widget falls back
    big = probe.make_oversized(os.path.join(directory, "oversized-2000x600.png"))
    for scale in (1, 2, 3):
        target = os.path.join(ext, f"banners/aios@{scale}x.png")
        os.unlink(target)
        shutil.copy(big, target)
    return copy, big


def fallback_flow(main, args, catalogue, rotate, reference_box):
    """Service unavailable: installed defaults straight from the extension; a 2000x600 image is fitted."""
    copy, big = fallback_install(args.instdir, os.path.join(args.out, "fallback-install"))
    with main.Run(args, copy, "writer", args.display, 1, "writer-fallback-oversized") as run:
        node = run.banner()
        if not main.check("[fallback] service broken: banner still shown from the installed defaults",
                          node is not None):
            return
        record = probe.describe(node)
        box = main.device_box(run, record)
        deadline, drawn = time.time() + rotate * len(catalogue) + 10, (None,)
        while time.time() < deadline and drawn[0] != "oversized":  # slot 0 comes round again
            drawn = probe.recognise(run.shot("01-oversized"), box, catalogue, 1, [("oversized", big)])
            time.sleep(0.5)
        run.hover(box)
        time.sleep(1)
        drawn = probe.recognise(run.shot("01-oversized", args.shots), box, catalogue, 1, [("oversized", big)])
        main.check("[fallback] the 2000x600 image is aspect-fitted in its slot", drawn[0] == "oversized", repr(drawn))
        main.check("[fallback] oversized image does not change the slot size",
                   reference_box is None or box[2:] == reference_box[2:], f"{box} vs {reference_box}")
        main.check("[fallback] accessible name from the installed manifest",
                   probe.describe(run.banner())["name"] == catalogue[0]["label"], probe.describe(run.banner())["name"])
        run.click(box)
        opened = run.opener.wait_for(1)
        main.check("[fallback] click opens the installed item URL with UTM", opened[-1:] == [catalogue[0]["url"]],
                   repr(opened[-1:]))


def dark_flow(main, args, catalogue):
    """Dark GTK theme: the light artwork is drawn on a light card; screenshot for approval."""
    env = {"GTK_THEME": "Adwaita:dark"}
    with main.Run(args, args.instdir, "writer", args.display, 1, "writer-dark", env) as run:
        path = run.shot("01-dark", args.shots)
        node = run.banner()
        if not main.check("[dark] banner present in the dark theme", node is not None):
            return
        record = probe.describe(node)
        box = main.device_box(run, record)
        from PIL import Image
        shot = Image.open(path).convert("RGB")
        card = shot.getpixel((box[0] + 2, box[1] + box[3] // 2))
        pane = shot.getpixel((box[0] - 6, box[1] + box[3] // 2))
        main.check("[dark] light card behind the artwork on the dark ribbon",
                   sum(card) / 3 > 200 and sum(pane) / 3 < 110, f"card={card} pane={pane}")


def reduced_motion_flow(main, args, catalogue, rotate):
    """Accessibility option "Allow other animations: No": items switch without any cross-fade frame."""
    config = [("/org.openoffice.Office.Common/Accessibility", "AllowAnimatedOthers", "1")]
    with main.Run(args, args.instdir, "writer", args.display, 1, "writer-reduced-motion", config=config) as run:
        node = run.banner()
        if not main.check("[reduced motion] banner present", node is not None):
            return
        box = main.device_box(run, probe.describe(node))
        run.leave()
        path = os.path.join(run.work, "sample.png")
        seen, unmatched, deadline = [], 0, time.time() + 2 * rotate + 4
        while time.time() < deadline and len(set(seen)) < 2:
            hst_gui.screenshot(path, args.display)
            ident = probe.recognise(path, box, catalogue, 1)[0]
            unmatched += ident is None
            seen += [ident] if ident else []
        main.check("[reduced motion] rotates by a plain switch, no blended frame sampled",
                   len(set(seen)) >= 2 and unmatched == 0, f"samples={len(seen)} unmatched={unmatched}")


def main(module):
    parser = argparse.ArgumentParser(description=module.__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--baseline-instdir", help="a build without the banner, for the ribbon height comparison")
    parser.add_argument("--display", default=":93")
    parser.add_argument("--display-hidpi", help="Xvfb of at least 3000x1820 for GDK_SCALE=2")
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-banner"))
    parser.add_argument("--shots", default=os.path.join(hst_gui.ROOT, "tests/output/ribbon-banner/screenshots"))
    args = parser.parse_args()
    if os.geteuid() == 0:
        # AT-SPI needs a session bus shared with the office: run as the build user under dbus-run-session
        for directory in (args.out, args.shots):
            os.makedirs(directory, exist_ok=True)
            subprocess.run(["chown", "-R", hst_gui.BUILD_USER, directory], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    catalogue, rotate = probe.items(args.instdir)
    module.check("installed extension carries the banner manifest and artwork",
                 len(catalogue) >= 1 and all(os.path.isfile(p) for i in catalogue for p in i["art"].values()))
    measured = {}
    for app in filter(None, args.apps.split(",")):
        for scale, display in ((1, args.display), (2, args.display_hidpi)):
            if display is None:
                continue
            measured[(app, scale)] = module.main_flow(args, catalogue, rotate, app, scale, display)
            if args.baseline_instdir:
                measured[(app, scale)]["baseline"] = baseline(module, args, app, scale, display, measured[(app, scale)])
    fallback_flow(module, args, catalogue, rotate, (measured.get(("writer", 1)) or {}).get("box"))
    dark_flow(module, args, catalogue)
    reduced_motion_flow(module, args, catalogue, rotate)
    failed = sum(r["status"] == "FAIL" for r in module.RESULTS)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "ribbon": {f"{a}-x{s}": v for (a, s), v in measured.items()},
                   "checks": module.RESULTS}, handle, indent=2, ensure_ascii=False)
    print(f"{len(module.RESULTS) - failed} passed, {failed} failed")
    return 1 if failed else 0
