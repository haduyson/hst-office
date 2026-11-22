#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Build hst-ocr.oxt from ocr/extension deterministically (sorted entries, fixed timestamps).

Usage: python3 ocr/build-oxt.py OUTPUT.oxt [--engine DIR]
--engine DIR copies a self-contained engine folder (DIR/hst-ocr[.exe] plus its data/: tessdata, models) into the
package as engine/. Without it the package holds only the thin UNO layer and finds the core through HST_OCR_ENGINE
(development). Per-OS engine folders and their signing are described in the prototype report.
"""
import argparse
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "extension")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
SKIP_DIRS = {"__pycache__", ".git"}


def entries(root, prefix=""):
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            if name.endswith((".pyc", "~")):
                continue
            path = os.path.join(base, name)
            yield prefix + os.path.relpath(path, root).replace(os.sep, "/"), path


def build(output, engine=None):
    files = dict(entries(SOURCE))
    if engine:
        if not os.path.isdir(engine):
            raise SystemExit("engine folder not found: %s" % engine)
        files.update(entries(engine, "engine/"))
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with zipfile.ZipFile(output, "w") as oxt:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            executable = name.startswith("engine/") and os.access(files[name], os.X_OK)
            info.external_attr = (0o755 if executable else 0o644) << 16
            stored = name.endswith((".onnx", ".traineddata"))  # already dense: deflate gains little, costs time
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            with open(files[name], "rb") as fh:
                oxt.writestr(info, fh.read())
    return len(files)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output")
    parser.add_argument("--engine")
    args = parser.parse_args(argv)
    count = build(args.output, args.engine)
    print("%s: %d files, %.1f MB" % (args.output, count, os.path.getsize(args.output) / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
