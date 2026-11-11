#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build results.json for one test PC from the artefacts pulled into its folder, in the r1auto report shape
(platform, run_id, package, display, results[item, status, detail, screenshot], owner_review).

  collect-results.py HOST_DIR --run-id 43000471110 --host hst4 [--expect-upgrade]

Reads install.json (install-msi.ps1), state-before*.json / state-after*.json (hst-state.ps1) and
<app>/probe.json + <app>/<app>-first*.png (hst_session_probe.py) under HOST_DIR/hst4-rc1 (or hst5-rc1).
"""
import argparse
import json
from pathlib import Path
import re
import sys

CLASSIC = ("auto", "", "hst_classic", "hst_classic_dark", "hst", "hst_dark")


def load(path):
    path = Path(path)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    # PowerShell may print warnings before the document: it starts at the first line opening with { or [
    match = re.search(r"(?m)^[\[{]", text)
    return json.loads(text[match.start():]) if match else None


def row(item, status, detail, screenshot=None):
    return dict(item=item, status=status, detail=detail, screenshot=screenshot)


def install_row(install, expect_upgrade):
    if not install:
        return row("RW1", "FAIL", dict(message="no install record"))
    ok = install.get("exit_code") in (0, 3010) and any("1.0.1" in p for p in _list(install.get("after")))
    upgraded = bool(_list(install.get("before"))) and not any("1.0.0|" in p for p in _list(install.get("after")))
    if expect_upgrade and ok and not upgraded:
        ok = False
    message = (f"exit {install.get('exit_code')} in {install.get('seconds')} s; before {_list(install.get('before'))}; "
               f"after {_list(install.get('after'))}")
    return row("RW1", "PASS" if ok else "FAIL", dict(message=message, msi=install.get("msi"), sha256=install.get("sha256"),
                                                     log_lines=install.get("log_lines", [])))


def _list(value):
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def profile_row(before, after):
    if not (before and after and before.get("profiles") and after.get("profiles")):
        return row("RW2", "SKIP", dict(message="no earlier HST profile on this PC (fresh install)"))
    b, a = before["profiles"][0], after["profiles"][0]
    kept = a["path"] == b["path"] and a["items"] >= b["items"] and a.get("UILocale") == b.get("UILocale") \
        and a.get("SymbolStyle") == b.get("SymbolStyle")
    return row("RW2", "PASS" if kept else "FAIL", dict(
        message=f"{b['path']}: {b['items']} items before, {a['items']} after; UILocale {b.get('UILocale')!r} -> "
                f"{a.get('UILocale')!r}; SymbolStyle {b.get('SymbolStyle')!r} -> {a.get('SymbolStyle')!r}"))


def probe_rows(root):
    rows, review, timing = [], [], {}
    settings = None
    for app in ("writer", "calc", "impress"):
        probe = load(root / app / "probe.json")
        if not probe:
            continue
        settings = settings or probe.get("settings")
        timing[app] = [dict(run=r["run"], first_window_s=r["first_window_s"], document_window_s=r["document_window_s"],
                            clean_close=(r.get("closed") or {}).get("method") == "terminate") for r in probe.get("runs", [])]
        shots = load(root / app / f"{app}-first.json") or []
        for shot in [shots] if isinstance(shots, dict) else shots:  # ConvertTo-Json writes one item as an object
            review.append(dict(item="RW6", detail=f"{shot['title']} at {shot['dpi']} dpi ({shot['width']}x{shot['height']}); "
                               f"{shot.get('masked_fraction', 0):.0%} masked (other windows)",
                               screenshot=f"{root.name}/{app}/{shot['file']}"))
    if not settings:
        return [row(i, "FAIL", dict(message="no in-session probe")) for i in ("RW3", "RW4", "RW5")], review
    vi = settings.get("ooLocale") == "vi"
    rows.append(row("RW3", "PASS" if vi else "FAIL", dict(message=f"ooLocale {settings.get('ooLocale')}, UILocale "
                                                                  f"{settings.get('UILocale')}")))
    classic = settings.get("SymbolStyle") in CLASSIC
    rows.append(row("RW4", "PASS" if classic else "FAIL", dict(message=f"SymbolStyle {settings.get('SymbolStyle')!r} "
                                                                       "(auto = Cổ điển)")))
    every = [r for runs in timing.values() for r in runs]
    measured = all(r["document_window_s"] for r in every) and every
    rows.append(row("RW5", "PASS" if measured else "FAIL", dict(message="seconds to the document window", timing=timing)))
    rows.append(row("RW6", "PASS" if review else "FAIL", dict(message=f"{len(review)} window-only screenshots for the owner")))
    return rows, review


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host_dir")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--expect-upgrade", action="store_true")
    args = parser.parse_args(argv[1:])
    base = Path(args.host_dir)
    install = load(base / "install.json")
    before = load(next(iter(sorted(base.glob("state-before*.json"))), base / "none"))
    after = load(next(iter(sorted(base.glob("state-after-upgrade.json"))), base / "none"))
    probe_rows_, review = probe_rows(base / f"{args.host}-rc1")
    results = [install_row(install, args.expect_upgrade), profile_row(before, after)] + probe_rows_
    report = dict(platform="windows", host=args.host, run_id=args.run_id,
                  package=dict(name=(install or {}).get("msi"), sha256=(install or {}).get("sha256")),
                  display=dict(scaling="the machine's own (not changed)"), results=results, owner_review=review)
    (base / "results.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for value in results:
        print(value["item"], value["status"], value["detail"].get("message", "")[:150])
    return 0 if all(r["status"] in ("PASS", "SKIP") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
