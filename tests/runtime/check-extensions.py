#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime proof for the bundled HST Vietnamese tools: installs the built .oxt into an isolated profile with
unopkg, drives LibreOffice over a UNO socket and checks real documents (insert/undo/save/reopen, conversion
with formatting, Calc formats and CSV).

Usage: python3 tests/runtime/check-extensions.py --soffice <path>/program/soffice --extension dist/extensions/hst-vietnamese-tools.oxt
           --fixtures tests/fixtures/vietnamese/manifest.json --output tests/output/extensions [--display :99]
Exit status is non-zero on any FAIL. Modal dialogs are not clicked by this script (see report).
"""
import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures", "vietnamese", "runtime"))
from lo_session import Session  # noqa: E402
from recorder import Recorder  # noqa: E402
import scenarios_calc  # noqa: E402
import scenarios_encoding  # noqa: E402
import scenarios_registration  # noqa: E402
import scenarios_welcome  # noqa: E402
import scenarios_writer  # noqa: E402


def verify_fixtures(rec, manifest_path):
    base = os.path.dirname(manifest_path)
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    for entry in manifest["files"]:
        digest = hashlib.sha256(open(os.path.join(base, entry["path"]), "rb").read()).hexdigest()
        rec.check("fixture " + entry["path"], digest == entry["sha256"], digest)
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soffice", required=True)
    ap.add_argument("--extension", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--port", type=int, default=2105)
    ap.add_argument("--mode", choices=("user", "bundled"), default="user",
                    help="user: unopkg add into an isolated profile; bundled: unpack into <install>/share/extensions (modifies the tree)")
    ap.add_argument("--allow-modify-install", action="store_true", help="required for --mode bundled; use only on a disposable copy")
    ap.add_argument("--display", default=None, help="X display for non-headless runs (default: headless)")
    ap.add_argument("--only", choices=("welcome",), help="run just one scenario group (faster while developing)")
    args = ap.parse_args()
    for label, path in (("soffice", args.soffice), ("extension", args.extension), ("fixtures", args.fixtures)):
        if not os.path.exists(path):
            print("BLOCKED: %s not found: %s" % (label, path))
            return 2
    if args.mode == "bundled" and not args.allow_modify_install:
        print("BLOCKED: --mode bundled changes the soffice installation; pass --allow-modify-install for a disposable copy")
        return 2
    out = os.path.abspath(args.output)
    rec = Recorder()
    fixtures = verify_fixtures(rec, os.path.abspath(args.fixtures))
    session = Session(os.path.abspath(args.soffice), os.path.abspath(args.extension), os.path.join(out, "session"), args.port, args.display, args.mode)
    ok, text, listing = session.install()
    rec.check("unopkg add", ok, text)
    if args.mode == "user":
        rec.check("unopkg list shows identifier", "vn.hasontech.hst.vietnamese-tools" in listing, listing[-300:])
    started = time.time()
    rec.check("test probe installed", *session.install_probe()[:1])
    try:
        session.start()
        version = session.version()
        print("office:", version)
        deployed = session.deployed_identifiers()
        rec.check("office reports the extension deployed (%s)" % args.mode, any(n == "vn.hasontech.hst.vietnamese-tools" for _, n in deployed), deployed)
        if args.only != "welcome":
            rec.run("registration", scenarios_registration.run, session, os.path.abspath(args.extension))
            rec.run("writer", scenarios_writer.run, session, fixtures, out)
            rec.run("encoding", scenarios_encoding.run, session, fixtures, out)
            rec.run("calc", scenarios_calc.run, session, fixtures, out)
        rec.run("welcome", scenarios_welcome.run, session, os.path.abspath(args.extension), out)
    finally:
        session.stop()
        rec.check("extension removed again", session.uninstall_bundled())
        session.cleanup()
    result = {"office": locals().get("version"), "extension": os.path.abspath(args.extension), "mode": args.mode, "seconds": round(time.time() - started, 1),
              "results": rec.rows, "failed": len(rec.failed), "blocked": sum(r["status"] == "BLOCKED" for r in rec.rows)}
    os.makedirs(out, exist_ok=True)
    json.dump(result, open(os.path.join(out, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%d checks, %d failed, %d blocked" % (len(rec.rows), len(rec.failed), sum(r["status"] == "BLOCKED" for r in rec.rows)))
    return 1 if rec.failed else 0


if __name__ == "__main__":
    sys.exit(main())
