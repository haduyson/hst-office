# SPDX-License-Identifier: AGPL-3.0-only
"""macOS launchers HST Writer, HST Sheets and HST Slides: the bundles make-app-launchers.py builds, the stub's
contract with their Info.plist, the signing step that drops the launch constraint, and the probe helper."""
import importlib.util
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MACOS = ROOT / "scripts" / "macos"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, MACOS / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MAKE = load("make_app_launchers", "make-app-launchers.py")
PROBE = load("app_launchers_probe", "app-launchers-probe.py")
HOST = {"CFBundleIdentifier": "vn.hasontech.hstoffice", "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0.600", "LSMinimumSystemVersion": "11.0",
        "NSHumanReadableCopyright": "© 2026 HASON TECH"}


class LauncherBundles(unittest.TestCase):
    def test_three_launchers_for_the_three_modules(self):
        self.assertEqual([(m, n) for m, n, _f, _s in MAKE.LAUNCHERS],
                         [("writer", "HST Writer"), ("calc", "HST Sheets"), ("impress", "HST Slides")])
        self.assertEqual(MAKE.bundle_path("/A/HST Office.app", "HST Sheets"),
                         Path("/A/HST Office.app/Contents/Helpers/HST Sheets.app"))

    def test_info_plist(self):
        info = MAKE.launcher_info(HOST, "calc", "HST Sheets", "sheets")
        self.assertEqual(info["CFBundleIdentifier"], "vn.hasontech.hstoffice.launcher.sheets")
        self.assertEqual((info["CFBundleName"], info["CFBundleDisplayName"]), ("HST Sheets", "HST Sheets"))
        self.assertEqual((info["HSTOfficeModule"], info["HSTOfficeHostIdentifier"]), ("calc", "vn.hasontech.hstoffice"))
        self.assertEqual(info["CFBundleExecutable"], MAKE.EXECUTABLE)
        self.assertEqual(info["CFBundlePackageType"], "APPL")
        self.assertIs(info["LSUIElement"], True)
        for key in ("CFBundleShortVersionString", "CFBundleVersion", "LSMinimumSystemVersion", "NSHumanReadableCopyright"):
            self.assertEqual(info[key], HOST[key], key)
        # XML, as upstream's signing script greps CFBundleIdentifier out of it
        text = plistlib.dumps(info, fmt=plistlib.FMT_XML).decode()
        self.assertRegex(text, r"<key>CFBundleIdentifier</key>\n\t<string>vn\.hasontech\.hstoffice\.launcher\.sheets</string>")

    def test_no_upstream_names_in_the_bundle_texts(self):
        for module, name, _family, suffix in MAKE.LAUNCHERS:
            text = plistlib.dumps(MAKE.launcher_info(HOST, module, name, suffix)).decode().lower()
            self.assertNotIn("libreoffice", text)
            self.assertNotIn("microsoft", text)

    def test_host_without_required_keys_is_refused(self):
        with self.assertRaises(ValueError):
            MAKE.launcher_info(dict(HOST, CFBundleVersion=""), "writer", "HST Writer", "writer")

    def test_icons_come_from_the_hst_module_artwork(self):
        for _module, _name, family, _suffix in MAKE.LAUNCHERS:
            plan = MAKE.iconset_sources(family)
            self.assertEqual(set(plan), set(MAKE.MEMBERS))
            self.assertEqual(plan["icon_512x512@2x.png"].name, family + "-1024.png")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                MAKE.iconset_sources("hst-writer", tmp)

    def test_stub_reads_the_keys_the_bundle_writes(self):
        stub = (MACOS / "hst-app-launcher.m").read_text(encoding="utf-8")
        for key in ("HSTOfficeModule", "HSTOfficeHostIdentifier"):
            self.assertIn('@"%s"' % key, stub)
        modules = re.search(r"@\[ (@\"\w+\"(?:, @\"\w+\")*) \]", stub).group(1)
        self.assertEqual(re.findall(r'@"(\w+)"', modules), [m for m, *_ in MAKE.LAUNCHERS])
        # no shell or AppleScript in the launcher
        for forbidden in ("/bin/sh", "osascript", "NSAppleScript", "system("):
            self.assertNotIn(forbidden, stub)
        self.assertNotIn("LibreOffice", stub)

    def test_collect_builds_them_before_signing_and_verify_checks_them(self):
        trial = (MACOS / "trial-build.sh").read_text(encoding="utf-8")
        collect = trial[trial.index("do_collect()"):trial.index("do_verify()")]
        self.assertLess(collect.index("make-app-launchers.py"), collect.index("adhoc-sign.sh"))
        self.assertLess(collect.index("make-app-launchers.py"), collect.index("build-dmg.sh"))
        verify = trial[trial.index("do_verify()"):]
        self.assertIn("Contents/Helpers/$name.app", verify)

    def test_developer_id_signing_drops_the_parent_launch_constraint(self):
        sign = (MACOS / "sign-notarize.sh").read_text(encoding="utf-8")
        upstream = sign.index('bash "$kit/macosx-codesign-app-bundle"')
        launchers = sign.index('"$app/Contents/Helpers/"*.app')
        gates = sign.index("check_signatures \"$app\"")
        self.assertLess(upstream, launchers)
        self.assertLess(launchers, gates)
        step = sign[launchers:gates]
        self.assertNotIn("launch-constraint", step)
        self.assertIn("--options=runtime", step)
        self.assertIn('--entitlements "$TMP/kit/build/hardened_runtime.xcent" "$app"', step)

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck not available")
    def test_probe_script_passes_shellcheck(self):
        result = subprocess.run(["shellcheck", "-x", str(MACOS / "app-launchers-probe.sh")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


class ProbeHelper(unittest.TestCase):
    XCU = ('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry">\n'
           '<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>false</value>'
           '</prop></item>\n</oor:items>\n')

    def test_seed_sets_each_value_once(self):
        text = PROBE.seed_text(PROBE.seed_text(self.XCU))
        self.assertEqual(text.count('oor:path="/org.hasontech.hstoffice.Welcome"'), 1)
        self.assertIn("<value>true</value>", text)
        self.assertIn("pipe,name=hst-launcher-probe;urp;", text)
        self.assertEqual(text.count("ooSetupConnectionURL"), 1)
        with self.assertRaises(ValueError):
            PROBE.seed_text("<x/>")

    def test_documents_are_counted_by_kind(self):
        class Doc:
            def __init__(self, service):
                self.service = service

            def supportsService(self, name):
                if self.service is None:
                    raise RuntimeError("no model")
                return name == self.service
        docs = [Doc(PROBE.KINDS["writer"]), Doc(PROBE.KINDS["calc"]), Doc(PROBE.KINDS["writer"]), Doc(None), Doc("x")]
        self.assertEqual(PROBE.kinds_of(docs), {"writer": 2, "calc": 1})


if __name__ == "__main__":
    unittest.main()
