#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""A damaged registrymodifications.xcu (what a power cut can leave) is repaired from user/pack, kept for diagnosis,
and the user is told once.

Usage: python3 tests/runtime/check-profile-corruption.py --instdir <instdir> [--out tests/output/profile-corruption]
           [--display :97]

A first session changes a setting (Undo steps = 77) and quits normally, so the office writes its profile backup
(user/pack). Then, on a copy of that profile each time, registrymodifications.xcu is cut to 0 bytes, to half its
size, or overwritten with zero bytes; the next start must keep the setting, leave registrymodifications.xcu.hong-*
next to it and show the notice "Cài đặt HST Office" once. The X display must already run. Exit 1 when a check fails.
"""
import argparse
import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import hst_gui  # noqa: E402
import recovery_runtime as rr  # noqa: E402
from recovery_runtime import record  # noqa: E402

PORT = 22232
NODE, PROP, VALUE = "/org.openoffice.Office.Common/Undo", "Steps", 77


def damage(path, mode):
    size = os.path.getsize(path)
    with open(path, "r+b") as handle:
        if mode == "empty":
            handle.truncate(0)
        elif mode == "half":
            handle.truncate(size // 2)
        else:
            handle.write(b"\0" * size)


def read_setting(off):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "nodepath", NODE
    provider = off.service("com.sun.star.configuration.ConfigurationProvider")
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,)) \
        .getPropertyValue(PROP)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "profile-corruption"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    hst_gui.setup_uno(args.instdir)
    base = rr.office(args.instdir, os.path.join(args.out, "base"), PORT, args.display)
    base.start()
    base.set_config(NODE, PROP, VALUE)
    rr.finish(base)
    pack = os.path.join(rr.user_dir(base), "pack", "registrymodifications.pack")
    record("a normal quit writes the profile backup", os.path.exists(pack), pack)
    for mode in ("empty", "half", "zeros"):
        work = os.path.join(args.out, mode)
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(base.workdir, work, symlinks=True)
        off = rr.office(args.instdir, work, PORT, args.display)
        xcu = os.path.join(rr.user_dir(off), "registrymodifications.xcu")
        damage(xcu, mode)
        off.start(fresh=False)
        notice = rr.wait(lambda: [w for w in hst_gui.toplevels(off.display) if "Cài đặt HST Office" in w[1]], 60)
        record("%s: the notice is shown" % mode, notice)
        if notice:
            rr.press_default(off, "Cài đặt HST Office", 5)
        time.sleep(2)
        record("%s: the setting comes back from the backup" % mode, read_setting(off) == VALUE, read_setting(off))
        record("%s: the damaged file is kept for diagnosis" % mode, glob.glob(xcu + ".hong-*"))
        record("%s: the notice marker is consumed" % mode, not os.path.exists(xcu + ".hst-repaired"))
        rr.finish(off)
        with open(xcu, "rb") as handle:
            data = handle.read()
        record("%s: registrymodifications.xcu is complete after the quit" % mode,
               data.rstrip().endswith(b"</oor:items>") and b"\0" not in data, len(data))
    return rr.summary("profile corruption runtime")


if __name__ == "__main__":
    sys.exit(main())
