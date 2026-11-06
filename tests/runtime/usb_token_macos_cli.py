# SPDX-License-Identifier: AGPL-3.0-only
"""Native macOS run of HST ▸ Thiết lập USB Token in a real HST Office.app, signing with SoftHSM2.

macOS counterpart of check-usb-token-setup.py (no platform override: real Darwin, bundled NSS
and Python). SoftHSM2 plays the VNPT-CA driver through HST_USB_TOKEN_TEST_ROOT
(<root>/usr/local/lib/libvnptca_p11_v8.dylib -> libsofthsm2). Scenarios, each with a fresh HOME:
  fresh    no certificate store yet;
  firefox  an existing Firefox profile (internal, Builtin Roots and another module) that must
           stay byte-identical while a new HST store is created and selected after restart;
           setup runs before NSS is first used, so the profile is compared with its creation;
  firefox-warm  the same after a PDF export has already opened the profile in core NSS: the
           profile is compared with the state core left it in before setup.
Each: setup, repeat (existing), restart, the token certificate through XSecurityEnvironment
with the test PIN, an ODT signed through the UI and validated by HST, a final repeat.

  --tools       soffice PATH contains Homebrew modutil/certutil;
  --no-tools    soffice PATH has neither (the normal Mac case; no test simulation flag).
Run with the app's bundled Python (PYTHONPATH: Contents/Resources, pyuno dir, this directory);
the driver's PATH must provide softhsm2-util, pkcs11-tool, certutil, modutil, openssl 3.
`--verify <results.json>` (any Python with lxml and cryptography) adds the independent
XML-DSig verification of the signed ODT files."""
import argparse
import json
import os
from pathlib import Path
import sys
import types

import signature_pki
from usb_token_macos_harness import mac_dialogs


def verify(results_path):
    import signature_verify
    results = json.loads(Path(results_path).read_text())
    failed = 0
    for row in results:
        if not row.get("signed_odt"):
            continue
        verified = signature_verify.verify_package(row["signed_odt"], row["ca_pem"])
        row["independent_verification"] = verified
        ok = len(verified) == 1 and verified[0]["valid"] and not verified[0]["unchecked"]
        row["checks"]["independent_signature_verification"] = ok
        failed += not ok
        print("%s/%s independent verification: %s" % (row["scenario"], row["mode"], "PASS" if ok else verified))
    Path(results_path).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return 1 if failed or not all(r.get("signed_odt") for r in results) else 0


def main(run_case):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path)
    ap.add_argument("--oxt", type=Path)
    ap.add_argument("--workdir", type=Path)
    ap.add_argument("--port", type=int, default=2093)
    ap.add_argument("--scenario", choices=("all", "fresh", "firefox", "firefox-warm"), default="all")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--tools", dest="tools", action="store_true")
    group.add_argument("--no-tools", dest="tools", action="store_false")
    ap.add_argument("--repeat", type=int, default=1, help="run each selected scenario this many times")
    ap.add_argument("--verify", type=Path, help="independent verification of an earlier results.json")
    args = ap.parse_args()
    if args.verify:
        return verify(args.verify)
    if not (args.app and args.oxt and args.workdir):
        ap.error("--app, --oxt and --workdir are required")
    if sys.platform != "darwin" or os.geteuid() == 0:
        ap.error("Run on macOS as a normal user.")
    missing = signature_pki.missing_tools()
    if missing:
        print("FAIL: missing test tools: " + ", ".join(missing))
        return 2
    try:
        import signature_verify  # noqa: F401
    except ImportError:  # lxml/cryptography are not in the bundled Python; see --verify
        sys.modules["signature_verify"] = types.ModuleType("signature_verify")
    from usb_token_harness import signing_helpers
    signing = signing_helpers()
    signing.Dialogs = mac_dialogs(signing)
    args.workdir = args.workdir.resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)
    results, status = [], 0
    scenarios = ("fresh", "firefox", "firefox-warm") if args.scenario == "all" else (args.scenario,)
    for round_ in range(1, args.repeat + 1):
        for scenario in scenarios:
            tag = "%s-%d" % (scenario, round_) if args.repeat > 1 else None
            results.append(run_case(args, scenario, signing, tag))
            passed = results[-1].get("passed", False)
            status |= not passed
            print("%s: %s (%d checks)" % (tag or scenario, "PASS" if passed else "FAIL", len(results[-1]["checks"])), flush=True)
            print("  pin prompts: %s; ui retries: %s" % (results[-1].get("pin_prompts"), results[-1].get("ui_retries")), flush=True)
        (args.workdir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print("%s: %d scenarios, %d checks" % ("PASS" if not status else "FAIL", len(results),
                                          sum(len(r["checks"]) for r in results)))
    return status
