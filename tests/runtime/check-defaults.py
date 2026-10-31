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
    # Enables the HASON TECH Start Center banner (hst-start-center-banner.patch); no donation UI exists.
    "org.openoffice.Office.Common/Misc/ShowDonation": True,
    "org.openoffice.Setup/Product/WhatsNew": False,
    # Light ribbon: no module colour tint on the notebookbar (NotebookBar::UpdateBackground), 255 = dialog colour only.
    "org.openoffice.Office.Common/Misc/NotebookbarColorTransparency": 255,
    "org.openoffice.Office.Writer/DefaultFont/Standard": "Times New Roman",
    "org.openoffice.Office.Common/Menus/DonationURL": "https://hasontech.vn",
    # Single help target for F1 / Help menu / dialog Help buttons (hst-debrand.patch): the offline
    # Vietnamese guide in the bundled HST extension, expanded to a file URL (hst-offline-help.patch).
    "org.openoffice.Office.Common/Help/HelpRootURL":
        "vnd.sun.star.expand:$BUNDLED_EXTENSIONS/hst-vietnamese-tools/help/index.html",
    "org.openoffice.Office.Common/Help/BuiltInHelpNotInstalledPopUp": False,
    # Hidden items and online catalogues: no URL (and no repository or extension-site URL) ships.
    "org.openoffice.Office.Common/Menus/SendFeedbackURL": "",
    "org.openoffice.Office.Common/Menus/GetInvolvedURL": "",
    "org.openoffice.Office.Common/Menus/ReleaseNotesURL": "",
    "org.openoffice.Office.Common/Menus/CreditsURL": "",
    "org.openoffice.Office.Common/Menus/ExtensionsURL": "",
    "org.openoffice.Office.ExtensionManager/ExtensionRepositories/WebsiteLink": "",
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
    """Connect over the UNO pipe (profile is pre-initialised, so no first-start restart)."""
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)  # the pipe opens early in startup; calls made before startup settles get disposed
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:  # NoConnectException until soffice listens
            if time.time() > deadline:
                raise
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/defaults"))
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)  # profile must be an absolute file:// URL
    program = os.path.join(os.path.abspath(args.instdir), "program")  # URE bootstrap needs an absolute path
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
    # A fresh profile makes soffice restart itself once; initialise it first so the
    # listening process below is the one that stays up.
    for _ in range(3):  # exit code 81 = "restart requested" while the profile is created
        warm = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                               "--terminate_after_init", f"-env:UserInstallation=file://{profile}"], env=child_env, timeout=120, check=False)
        if warm.returncode == 0:
            break
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
        # The help URL must expand to the installed guide (what F1 hands to the browser).
        import uno
        help_url = read_config(ctx, "org.openoffice.Office.Common/Help/HelpRootURL")
        expander = ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander")
        expanded = expander.expandMacros(help_url[len("vnd.sun.star.expand:"):]) if help_url.startswith("vnd.sun.star.expand:") else help_url
        ok = expanded.startswith("file://") and os.path.isfile(uno.fileUrlToSystemPath(expanded))
        failed += not ok
        results["HelpRootURL expands to an installed file"] = {"actual": expanded, "status": "PASS" if ok else "FAIL"}
        print(f"{'PASS' if ok else 'FAIL'}  HelpRootURL expands to an installed file: {expanded}")
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
