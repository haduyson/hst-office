# SPDX-License-Identifier: AGPL-3.0-only
"""check-ribbon-banner.py, part 3: where a click goes, with the probe stubbed in a copy of the installation.

The real installation is never modified: the copy is hard-linked and changed files are unlinked first.
HST_TEST_PROBE selects the stub's answer and exists only in that copied banner_click.py.
"""
import os
import re
import shutil
import subprocess
import time

import hst_gui
import ribbon_banner_probe as probe

STUB = '''

def PROBE(url, version, proxy=None):  # runtime test stub, only in the test's copy of the installation
    import os
    with open(os.environ["HST_TEST_PROBE_LOG"], "a", encoding="utf-8") as log:
        log.write(url + "\\n")
    mode = os.environ["HST_TEST_PROBE"]
    if mode == "refused":
        raise OSError("refused")
    if mode == "timeout":
        raise TimeoutError()
    return 503 if mode == "503" else 200
'''

OFFLINE = '''

def fetch(url, limit, version, proxy=None):  # runtime test stub, only in the test's copy of the installation
    raise OSError("offline")
'''


def replace_file(path, text):
    """Break the hard link first, so the source installation keeps its file."""
    os.unlink(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def stubbed_install(instdir, directory, direct_host):
    copy = os.path.join(directory, "instdir")
    shutil.rmtree(copy, ignore_errors=True)
    os.makedirs(directory, exist_ok=True)
    subprocess.run(["cp", "-al", instdir, copy], check=False, stderr=subprocess.DEVNULL)
    ext = os.path.join(copy, probe.EXT)
    path = os.path.join(ext, "python/hst_office/banner_click.py")
    replace_file(path, open(path, encoding="utf-8").read() + STUB)
    # no online generation: the live signed feed would replace the URLs this test prepares
    path = os.path.join(ext, "python/hst_office/banner_fetch.py")
    replace_file(path, open(path, encoding="utf-8").read() + OFFLINE)
    if direct_host:
        for name in ("data/banners.json", "data/banner-snapshots.json"):
            path = os.path.join(ext, name)
            text = open(path, encoding="utf-8").read()
            replace_file(path, re.sub(r"https://system\.hasontech\.vn/hst-office/go/[a-z-]+", direct_host, text))
    return copy


def one_mode(main, args, mode, copy, expected_home, probes_expected):
    tag = f"writer-click-{mode}"
    log = os.path.join(args.out, f"{tag}-probe.log")
    open(log, "w").close()
    catalogue, _ = probe.items(copy)
    env = {"HST_TEST_PROBE": mode, "HST_TEST_PROBE_LOG": log}
    with main.Run(args, copy, "writer", args.display, 1, tag, env) as run:
        node = run.banner()
        if not main.check(f"[click {mode}] banner present", node is not None):
            return
        box = main.device_box(run, probe.describe(node))
        run.hover(box)
        time.sleep(1.5)
        item = next((i for i in catalogue if i["id"] == probe.recognise(run.shot("hover"), box, catalogue, 1)[0]), None)
        if not main.check(f"[click {mode}] drawn item recognised", item is not None):
            return
        windows = {wid for wid, _ in hst_gui.toplevels(args.display, run.office.pid)}
        run.click(box)
        want = item["home"] if expected_home else item["url"]
        opened = run.opener.wait_for(1)
        main.check(f"[click {mode}] opens {'the home page' if expected_home else 'the item URL'} with UTM",
                   opened == [want], repr(opened))
        probed = open(log, encoding="utf-8").read().split()
        main.check(f"[click {mode}] probe count and target", len(probed) == probes_expected and all(
            p == "https://system.hasontech.vn/hst-office/banners.json" for p in probed), repr(probed))
        added = [name for wid, name in hst_gui.toplevels(args.display, run.office.pid) if wid not in windows]
        main.check(f"[click {mode}] no dialog", not added, repr(added))
        if mode == "reachable":
            time.sleep(1.3)
            main.xdo(args.display, "click", "--repeat", "2", "--delay", "90", "1")
            time.sleep(3)
            main.check("[click reachable] a double click opens one tab", len(run.opener.opened()) == 2,
                       repr(run.opener.opened()))


def click_flows(main, args):
    copy = stubbed_install(args.instdir, os.path.join(args.out, "click-install"), None)
    for mode, home in (("reachable", False), ("refused", True), ("503", True), ("timeout", True)):
        one_mode(main, args, mode, copy, home, 1)
    other = stubbed_install(args.instdir, os.path.join(args.out, "click-install-direct"), "https://aios.hasontech.vn")
    one_mode(main, args, "direct", other, False, 0)
