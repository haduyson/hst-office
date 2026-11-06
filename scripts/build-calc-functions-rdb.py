#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Compile the type library of the Sheets functions (DOCSO, DOCTIEN, BODAU, TACHHO, TACHTEN) with the build's unoidl-write.

Usage: python3 scripts/build-calc-functions-rdb.py [--instdir upstream/libreoffice/instdir] [--check]

extensions/hst-vietnamese-tools/idl/XCalcFunctions.idl -> extensions/hst-vietnamese-tools/types/hst-calc-functions.rdb.
The .rdb is committed: it is the same file on Windows, macOS and Linux, and the extension is packaged by
scripts/build-extensions.py, which needs no compiler. Run this after changing the IDL; --check compares instead of
writing (exit 1 when stale). unoidl-write output is deterministic for the same IDL and engine version.
"""
import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "extensions", "hst-vietnamese-tools")
IDL = os.path.join(EXT, "idl", "XCalcFunctions.idl")
RDB = os.path.join(EXT, "types", "hst-calc-functions.rdb")


def compile_rdb(instdir, output):
    program = os.path.join(instdir, "program")
    tool = os.path.join(instdir, "sdk", "bin", "unoidl-write")
    if not os.path.exists(tool):
        raise SystemExit("BLOCKED: %s not found (build the SDK tools first)" % tool)
    env = dict(os.environ, LD_LIBRARY_PATH=program, DYLD_LIBRARY_PATH=program)
    subprocess.run([tool, os.path.join(program, "types.rdb"), os.path.join(program, "types", "offapi.rdb"), IDL, output],
                   check=True, env=env, timeout=120)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        built = os.path.join(tmp, "out.rdb")
        compile_rdb(os.path.abspath(args.instdir), built)
        data = open(built, "rb").read()
    if args.check:
        same = os.path.exists(RDB) and open(RDB, "rb").read() == data
        print("%s %s" % ("PASS" if same else "STALE", os.path.relpath(RDB, ROOT)))
        return 0 if same else 1
    os.makedirs(os.path.dirname(RDB), exist_ok=True)
    with open(RDB, "wb") as handle:
        handle.write(data)
    print("wrote %s (%d bytes)" % (os.path.relpath(RDB, ROOT), len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
