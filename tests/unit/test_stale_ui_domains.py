# SPDX-License-Identifier: AGPL-3.0-only
"""Slot tree sync: an instdir dialog whose root <interface domain="hst-..."> came from a tree that delivered .ui files
from hst/l10n/ui is dropped when the current tree no longer delivers it that way, so make copies the plain dialog
again. The copy rule depends only on the source file, which is older than the stale copy, so make alone never does."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = {
    "windows": (ROOT / "scripts/windows/hst4-tree.sh", "LO"),
    "linux": (ROOT / "scripts/linux/local-build.sh", "SRC"),
}
CFG = "instdir/share/config/soffice.cfg"


def shell_function(script, name):
    match = re.search(rf"^{name}\(\) {{.*?^}}$", script.read_text(encoding="utf-8"), re.S | re.M)
    if not match:
        raise AssertionError(f"{name} not found in {script}")
    return match.group(0)


def ui(domain):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<interface domain="{domain}">\n  <requires lib="gtk" version="3.24"/>\n</interface>\n'


class InvalidateStaleUiDomainsTest(unittest.TestCase):
    def make_tree(self, root):
        lo = Path(root) / "lo"
        files = {
            f"{CFG}/modules/scalc/ui/formatcellsdialog.ui": "hst-sc",
            f"{CFG}/modules/swriter/ui/paradialog.ui": "hst-sw",
            f"{CFG}/vcl/ui/printdialog.ui": "vcl",
            f"{CFG}/cui/ui/optionsdialog.ui": "cui",
        }
        for rel, domain in files.items():
            (lo / rel).parent.mkdir(parents=True, exist_ok=True)
            (lo / rel).write_text(ui(domain), encoding="utf-8")
        return lo

    def run_rule(self, platform, lo):
        script, var = SCRIPTS[platform]
        snippet = (f'set -Eeuo pipefail\nlog() {{ echo "$*"; }}\n{var}="{lo}"\n'
                   f'{shell_function(script, "invalidate_stale_ui_domains")}\n'
                   f'invalidate_stale_ui_domains "{lo.parent}/ui-domains.keep"\n')
        return subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, check=True)

    def test_hst_domain_without_hst_catalog_tree_is_dropped(self):
        for platform in SCRIPTS:
            with self.subTest(platform), tempfile.TemporaryDirectory() as root:
                lo = self.make_tree(root)
                done = self.run_rule(platform, lo)
                self.assertIn("instdir has 2 .ui files with an hst- gettext domain", done.stdout)
                self.assertFalse((lo / CFG / "modules/scalc/ui/formatcellsdialog.ui").exists())
                self.assertFalse((lo / CFG / "modules/swriter/ui/paradialog.ui").exists())
                self.assertTrue((lo / CFG / "vcl/ui/printdialog.ui").exists())
                self.assertTrue((lo / CFG / "cui/ui/optionsdialog.ui").exists())
                self.assertFalse((lo.parent / "ui-domains.keep").exists())

    def test_dialog_the_tree_delivers_from_hst_l10n_is_kept(self):
        for platform in SCRIPTS:
            with self.subTest(platform), tempfile.TemporaryDirectory() as root:
                lo = self.make_tree(root)
                src = lo / "hst/l10n/ui/sc/uiconfig/scalc/ui/formatcellsdialog.ui"
                src.parent.mkdir(parents=True)
                src.write_text(ui("hst-sc"), encoding="utf-8")
                done = self.run_rule(platform, lo)
                self.assertIn("instdir has 1 .ui files", done.stdout)
                self.assertTrue((lo / CFG / "modules/scalc/ui/formatcellsdialog.ui").exists())
                self.assertFalse((lo / CFG / "modules/swriter/ui/paradialog.ui").exists())

    def test_same_name_with_another_domain_is_dropped(self):
        with tempfile.TemporaryDirectory() as root:
            lo = self.make_tree(root)
            src = lo / "hst/l10n/ui/sw/uiconfig/swriter/ui/formatcellsdialog.ui"
            src.parent.mkdir(parents=True)
            src.write_text(ui("hst-sw"), encoding="utf-8")
            self.run_rule("windows", lo)
            self.assertFalse((lo / CFG / "modules/scalc/ui/formatcellsdialog.ui").exists())

    def test_clean_instdir_and_missing_instdir_change_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            lo = Path(root) / "lo"
            lo.mkdir()
            self.assertEqual(self.run_rule("linux", lo).stdout, "")
            (lo / CFG / "vcl/ui").mkdir(parents=True)
            (lo / CFG / "vcl/ui/printdialog.ui").write_text(ui("vcl"), encoding="utf-8")
            self.assertEqual(self.run_rule("linux", lo).stdout, "")
            self.assertTrue((lo / CFG / "vcl/ui/printdialog.ui").exists())


if __name__ == "__main__":
    unittest.main()
