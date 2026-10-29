# SPDX-License-Identifier: AGPL-3.0-only
"""Check HST default configuration on a real HST Office build (fresh profile).

Usage: python3 tests/runtime/check-defaults.py [--instdir upstream/libreoffice/instdir] [--out tests/output/defaults]

Starts soffice headless with an isolated profile, connects over a UNO pipe and
reads the effective configuration (defaults from the patched officecfg layers),
then writes evidence.json. Exit 1 when any expectation fails.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPECTED = {
    "org.openoffice.Setup/Product/ooName": "HST Office",
    "org.openoffice.Setup/Product/ooVendor": "HASON TECH",
    "org.openoffice.Office.UI.ToolbarMode/Applications/Writer/Active": "notebookbar.ui",
    "org.openoffice.Office.UI.ToolbarMode/Applications/Calc/Active": "notebookbar.ui",
    "org.openoffice.Office.UI.ToolbarMode/Applications/Impress/Active": "notebookbar.ui",
    "org.openoffice.Office.Common/Misc/ShowDonation": False,
    "org.openoffice.Setup/Product/WhatsNew": False,
    "org.openoffice.Office.Writer/DefaultFont/Standard": "Times New Roman",
    "org.openoffice.Office.Common/Menus/DonationURL": "https://hasontech.vn",
}


def read_config(ctx, path):
    import uno  # noqa: F401  (imported lazily: needs the instdir on sys.path)
    from com.sun.star.beans import PropertyValue
    node_path, key = path.rsplit("/", 1)
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = PropertyValue()
    arg.Name, arg.Value = "nodepath", node_path
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
    return access.getByName(key)


def connect(pipe, timeout=90):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline = time.time() + timeout
    while True:
        try:
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:  # NoConnectException until soffice is ready
            if time.time() > deadline:
                raise
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/defaults"))
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)  # profile must be an absolute file:// URL
    program = os.path.join(args.instdir, "program")
    # Use the tested build's own Python-UNO bridge when it ships one (HST builds
    # with --enable-python=system do); otherwise fall back to the system bridge.
    # URE_BOOTSTRAP is for this Python process only; soffice must not inherit it.
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    profile = os.path.join(args.out, "profile")
    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(profile)
    pipe = f"hstdefaults{os.getpid()}"
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--norestore", "--nologo",
                             f"-env:UserInstallation=file://{profile}", f"--accept=pipe,name={pipe};urp;"], env=child_env)
    results, failed = {}, 0
    try:
        ctx = connect(pipe)
        for path, expected in EXPECTED.items():
            try:
                actual = read_config(ctx, path)
            except Exception as error:  # report missing keys as failures, keep going
                actual = f"ERROR {error}"
            ok = actual == expected
            failed += not ok
            results[path] = {"expected": expected, "actual": actual, "status": "PASS" if ok else "FAIL"}
            print(f"{'PASS' if ok else 'FAIL'}  {path} = {actual!r}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
