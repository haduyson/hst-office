# SPDX-License-Identifier: AGPL-3.0-only
"""check-branding: asset verification, tree scan, allowlist semantics, CLI exit codes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from brand.audit import check_assets, load_allowlist, scan_tree  # noqa: E402

with open(os.path.join(ROOT, "assets", "brand", "brand-spec.json"), encoding="utf-8") as fh:
    SPEC = json.load(fh)
CLI = os.path.join(ROOT, "scripts", "check-branding.py")
ALLOWLIST = os.path.join(ROOT, "branding", "brand-audit-allowlist.json")


def write(base, rel, text):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class AssetCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def copy_repo_assets(self):
        for part in ("assets/brand/icons", "branding/libreoffice", "branding/windows", "branding/macos"):
            shutil.copytree(os.path.join(ROOT, part), os.path.join(self.tmp, part))

    def test_repo_assets_ok(self):
        self.assertEqual(check_assets(SPEC, ROOT), [])

    def test_missing_required_file_reported(self):
        self.copy_repo_assets()
        os.remove(os.path.join(self.tmp, "branding/libreoffice/about.svg"))
        self.assertIn("missing branding/libreoffice/about.svg", check_assets(SPEC, self.tmp))

    def test_wrong_png_size_reported(self):
        self.copy_repo_assets()
        shutil.copy(os.path.join(ROOT, "assets/brand/icons/hst-office-16.png"),
                    os.path.join(self.tmp, "branding/libreoffice/intro.png"))
        self.assertTrue(any("intro.png" in e for e in check_assets(SPEC, self.tmp)))

    def test_svg_with_upstream_name_or_external_image_reported(self):
        self.copy_repo_assets()
        write(self.tmp, "branding/libreoffice/logo.svg",
              '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
              '<title>LibreOffice</title><image xlink:href="http://example.invalid/x.png"/></svg>')
        errors = " | ".join(check_assets(SPEC, self.tmp))
        self.assertIn("embedded data URI", errors)
        self.assertIn("upstream product name", errors)

    def test_progress_conf_validated(self):
        self.copy_repo_assets()
        write(self.tmp, "branding/libreoffice/progress.conf", 'PROGRESSSIZE="abc"\n')
        self.assertTrue(any("progress.conf" in e for e in check_assets(SPEC, self.tmp)))


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        write(self.tmp, "share/registry/main.xcd", '<node oor:name="x">Welcome to LibreOffice</node>')
        write(self.tmp, "program/versionrc", "ProductKey=HST Office\n")
        write(self.tmp, "license/LICENSE.html", "LibreOffice is MPL-2.0 by The Document Foundation")
        write(self.tmp, "program/libfoo.so", "LibreOffice binary names are not scanned")

    def test_hit_found_and_binary_skipped(self):
        hits, scanned = scan_tree(self.tmp, [])
        paths = {h[0] for h in hits}
        self.assertEqual(paths, {"share/registry/main.xcd", "license/LICENSE.html"})
        self.assertEqual(scanned, 3)

    def test_allowlist_glob_and_regex(self):
        entries = [{"path": "license/**", "reason": "licence text"},
                   {"path": "share/registry/*.xcd", "regex": "internal-id", "reason": "does not match line"}]
        hits, _ = scan_tree(self.tmp, entries)
        self.assertEqual([h[0] for h in hits], ["share/registry/main.xcd"])

    def test_allowlist_requires_reason(self):
        path = os.path.join(self.tmp, "bad.json")
        write(self.tmp, "bad.json", json.dumps({"entries": [{"path": "**"}]}))
        with self.assertRaises(ValueError):
            load_allowlist(path)

    def test_repo_allowlist_loads(self):
        self.assertGreater(len(load_allowlist(ALLOWLIST)), 0)

    def test_cli_exit_codes(self):
        run = lambda *a: subprocess.run([sys.executable, CLI, *a], capture_output=True, text=True)
        self.assertEqual(run().returncode, 0)
        dirty = run("--install-root", self.tmp, "--allowlist", ALLOWLIST)
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("NAME: share/registry/main.xcd", dirty.stderr)
        self.assertEqual(run("--install-root", os.path.join(self.tmp, "nope")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
