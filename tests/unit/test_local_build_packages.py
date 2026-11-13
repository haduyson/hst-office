# SPDX-License-Identifier: AGPL-3.0-only
"""Packaging helpers of scripts/linux/local-build.sh: .rpm/.AppImage only for refs whose ci-build.sh supports
--rpm-appimage, and exactly the packages SHA256SUMS lists are copied to the output."""
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scripts/linux/local-build.sh").read_text(encoding="utf-8")


def function(name):
    match = re.search(rf"^{name}\(\) {{.*?^}}$", SCRIPT, re.S | re.M)
    if not match:
        raise AssertionError(f"{name} not found in local-build.sh")
    return match.group(0)


HELPERS = function("supports_rpm_appimage") + "\n" + function("copy_packages") + "\n"


def bash(snippet, cwd):
    return subprocess.run(["bash", "-c", HELPERS + snippet], cwd=cwd, capture_output=True, text=True, check=False)


class LocalBuildPackagesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.inst = self.dir / "installer"
        self.dest = self.dir / "dest"
        self.inst.mkdir()
        self.dest.mkdir()

    def write_packages(self, names, extra=()):
        lines = []
        for name in names:
            data = name.encode()
            (self.inst / name).write_bytes(data)
            lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
        for name in extra:   # present in the directory but not listed: must not be copied
            (self.inst / name).write_text("stale")
        (self.inst / "SHA256SUMS").write_text("\n".join(lines) + "\n")

    def test_detects_the_rpm_appimage_flag(self):
        new = self.dir / "new.sh"
        new.write_text('case "$1" in\n  --package) ;;\n  --rpm-appimage) phase rpm-appimage do_rpm_appimage ;;\nesac\n')
        old = self.dir / "old.sh"
        old.write_text('case "$1" in\n  --package) phase package do_package ;;\nesac\n')
        self.assertEqual(bash(f"supports_rpm_appimage {new}", self.dir).returncode, 0)
        self.assertNotEqual(bash(f"supports_rpm_appimage {old}", self.dir).returncode, 0)

    def test_copies_deb_rpm_and_appimage_listed_in_sha256sums(self):
        names = ["HSTOffice_1.0.2_Linux_x86-64.deb", "HSTOffice_1.0.2_Linux_x86-64.rpm",
                 "HSTOffice_1.0.2_Linux_x86-64.AppImage"]
        self.write_packages(names, extra=["HSTOffice_1.0.1_Linux_x86-64.rpm"])
        done = bash(f"copy_packages {self.inst} {self.dest}", self.dir)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), sorted(names + ["SHA256SUMS"]))

    def test_deb_only_ref(self):
        self.write_packages(["HSTOffice_1.0.1_Linux_x86-64.deb"])
        self.assertEqual(bash(f"copy_packages {self.inst} {self.dest}", self.dir).returncode, 0)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["HSTOffice_1.0.1_Linux_x86-64.deb", "SHA256SUMS"])

    def test_checksum_mismatch_and_unexpected_names_fail(self):
        self.write_packages(["HSTOffice_1.0.2_Linux_x86-64.deb"])
        (self.inst / "HSTOffice_1.0.2_Linux_x86-64.deb").write_text("tampered")
        self.assertNotEqual(bash(f"copy_packages {self.inst} {self.dest}", self.dir).returncode, 0)
        other = self.dir / "other"
        other.mkdir()
        self.inst = other
        self.write_packages(["notes.txt"])
        self.assertNotEqual(bash(f"copy_packages {other} {self.dest}", self.dir).returncode, 0)


if __name__ == "__main__":
    unittest.main()
