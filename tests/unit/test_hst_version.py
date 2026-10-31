# SPDX-License-Identifier: AGPL-3.0-only
"""write-hst-version.py: release id, monotonic build number and the generated header."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("write_hst_version", ROOT / "scripts/write-hst-version.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
SCRIPT = ROOT / "scripts/write-hst-version.py"


class ReleaseBuildNumber(unittest.TestCase):
    def test_build_numbers(self):
        for release, build in (("1.0.0-beta.4", 400), ("1.0.0-beta.4.1", 401), ("1.0.0-beta.5", 500),
                               ("1.0.0-beta.10", 1000), ("1.0.0-rc.1", 5100), ("1.0.0", 10000)):
            self.assertEqual(MOD.release_build(release), build, release)

    def test_build_numbers_increase_with_semver_precedence(self):
        order = ["1.0.0-beta.1", "1.0.0-beta.4", "1.0.0-beta.4.1", "1.0.0-beta.4.2", "1.0.0-beta.5", "1.0.0-beta.10",
                 "1.0.0-rc.1", "1.0.0-rc.1.1", "1.0.0-rc.2", "1.0.0"]
        builds = [MOD.release_build(r) for r in order]
        self.assertEqual(builds, sorted(set(builds)))
        for build in builds:
            self.assertLessEqual(build, 65535)  # 4th component of a Windows file version

    def test_rejects_ids_outside_the_scheme(self):
        for bad in ("1.0", "1.0.0-alpha.1", "1.0.0-beta", "1.0.0-beta.50", "1.0.0-beta.1.100", "1.0.0-beta.01", "v1.0.0", ""):
            with self.assertRaises(ValueError, msg=bad):
                MOD.release_build(bad)


class ReleaseFile(unittest.TestCase):
    def write(self, release):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "release.json"
        path.write_text(json.dumps({"release": release}), encoding="utf-8")
        return path

    def test_reads_release_matching_version(self):
        self.assertEqual(MOD.read_release("1.0.0", self.write("1.0.0-beta.4.1")), "1.0.0-beta.4.1")

    def test_exits_on_core_mismatch_bad_or_missing_file(self):
        with self.assertRaises(SystemExit):
            MOD.read_release("1.0.1", self.write("1.0.0-beta.4.1"))
        with self.assertRaises(SystemExit):
            MOD.read_release("1.0.0", self.write("1.0.0-alpha.1"))
        with self.assertRaises(SystemExit):
            MOD.read_release("1.0.0", Path("/nonexistent/release.json"))

    def test_shipped_release_file_is_consistent(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        release = MOD.read_release(version)
        self.assertTrue(release.startswith(version))


class Header(unittest.TestCase):
    def test_header_defines_release_build_and_file_version(self):
        text = MOD.header_text("1.0.0", ("1", "0", "0"), "1.0.0-beta.4.1")
        for line in ('#define HST_VERSION "1.0.0"', "#define HST_VERSION_MICRO 0", '#define HST_RELEASE "1.0.0-beta.4.1"',
                     "#define HST_VERSION_BUILD 401", '#define HST_FILE_VERSION "1.0.0.401"'):
            self.assertIn(line, text)

    def test_cli_outputs_and_header_rewritten_only_on_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = Path(tmp) / "release.json"
            release.write_text('{"release": "1.0.0-beta.4.1"}', encoding="utf-8")
            run = lambda *args: subprocess.run(["python3", "-I", str(SCRIPT), "--release-file", str(release), *args],
                                               capture_output=True, text=True, check=True).stdout
            self.assertEqual(run("--release").strip(), "1.0.0-beta.4.1")
            self.assertEqual(run("--build").strip(), "401")
            env = run("--env")
            self.assertIn("export HST_RELEASE=1.0.0-beta.4.1", env)
            self.assertIn("export HST_VERSION_BUILD=401", env)
            header = Path(tmp) / "include" / "hst_version.h"
            self.assertIn("written", run("--header", str(header)))
            self.assertIn("unchanged", run("--header", str(header)))
            release.write_text('{"release": "1.0.0-beta.5"}', encoding="utf-8")
            self.assertIn("written", run("--header", str(header)))
            self.assertIn('HST_RELEASE "1.0.0-beta.5"', header.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
