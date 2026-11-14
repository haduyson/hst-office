# SPDX-License-Identifier: AGPL-3.0-only
"""The office never runs the upstream OpenCL self-test at start-up (error reports HSTO-000010/11).

On Windows a driver fault inside Desktop::CheckOpenCLCompute ended the first start of a new profile with the restart
code and no trace. hst-no-startup-opencl-test.patch removes the call; UseOpenCL also stays off by default. The runtime
check tests/runtime/check-first-start-no-opencl.ps1 proves it on a built office."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches" / "libreoffice"
PATCH = PATCHES / "hst-no-startup-opencl-test.patch"


class NoStartupOpenCLTestTests(unittest.TestCase):
    def test_patch_is_in_the_series(self):
        series = [line.strip() for line in (PATCHES / "series").read_text(encoding="utf-8").splitlines()]
        self.assertIn(PATCH.name, series)

    def test_patch_removes_the_only_call_and_adds_none(self):
        text = PATCH.read_text(encoding="utf-8")
        self.assertIn("+++ b/desktop/source/app/app.cxx", text)
        removed = [line for line in text.splitlines() if line.startswith("-") and not line.startswith("---")]
        added = [line for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")]
        self.assertTrue(any(re.search(r"\bCheckOpenCLCompute\(xDesktop\);", line) for line in removed))
        self.assertFalse(any("CheckOpenCLCompute(" in line for line in added))

    def test_no_other_patch_calls_the_self_test(self):
        for patch in PATCHES.glob("*.patch"):
            if patch == PATCH:
                continue
            added = [line for line in patch.read_text(encoding="utf-8", errors="replace").splitlines()
                     if line.startswith("+") and "CheckOpenCLCompute(" in line]
            self.assertEqual(added, [], patch.name)

    def test_use_opencl_stays_off_by_default(self):
        xcu = (ROOT / "extensions" / "hst-vietnamese-tools" / "StartupDefaults.xcu").read_text(encoding="utf-8")
        self.assertRegex(xcu, r'<prop oor:name="UseOpenCL">\s*<value>false</value>')

    def test_runtime_check_seeds_use_opencl_and_watches_the_test(self):
        script = (ROOT / "tests" / "runtime" / "check-first-start-no-opencl.ps1").read_text(encoding="utf-8")
        for needle in ('oor:name="UseOpenCL"', "opencltest", "OpenCL.dll", "SelectedOpenCLDeviceIdentifier"):
            self.assertIn(needle, script)


if __name__ == "__main__":
    unittest.main()
