# SPDX-License-Identifier: AGPL-3.0-only
"""Evidence of one office start for scripts/perf/startup-timing.py: the splash bitmap's size, what the start left in
the profile, and screenshots."""
import os
import struct


def png_size(path):
    """(width, height) of a PNG (its IHDR chunk), the splash bitmap."""
    with open(path, "rb") as handle:
        head = handle.read(24)
    return struct.unpack(">II", head[16:24])


def profile_facts(profile):
    """What the start left in the profile that tells which start-up work ran."""
    user = os.path.join(profile, "user")
    facts = {}
    for name in ("extensions/bundled/lastsynchronized", "extensions/buildid", "config/javasettings_Windows_X86_64.xml",
                 "config/javasettings_Linux_X86_64.xml", "config/javasettings_macOS_aarch64.xml",
                 "config/javasettings_macOS_X86_64.xml", "registrymodifications.xcu", "hst-office/hst-office.log"):
        path = os.path.join(user, *name.split("/"))
        if os.path.exists(path):
            facts[name] = os.path.getsize(path)
    log = os.path.join(user, "hst-office", "hst-office.log")
    if os.path.exists(log):
        with open(log, encoding="utf-8", errors="replace") as handle:
            facts["hst-office.log tail"] = handle.read()[-1500:]
    return facts


def screenshot(path, box=None):
    """The screen (or the `box` left, top, right, bottom around it with a 20 px margin) as a PNG."""
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab(all_screens=True)
        if box:
            image.crop((box[0] - 20, box[1] - 20, box[2] + 20, box[3] + 20)).save(path)
            return "%s window %s" % (os.path.basename(path), list(box))
        image.save(path)
        return os.path.basename(path)
    except Exception as error:  # noqa: BLE001 - screenshots are optional evidence
        return "no screenshot: %s" % error
