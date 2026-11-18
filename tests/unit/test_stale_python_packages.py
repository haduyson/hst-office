# SPDX-License-Identifier: AGPL-3.0-only
"""Windows tree sync: a package filelist that delivers into another python-core directory than the tree's Python
tarball is dropped, so make delivers it again (libffi-8.dll must sit next to _ctypes.pyd of the bundled Python)."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/windows/hst4-tree.sh"


def shell_function(name):
    match = re.search(rf"^{name}\(\) {{.*?^}}$", SCRIPT.read_text(encoding="utf-8"), re.S | re.M)
    if not match:
        raise AssertionError(f"{name} not found in {SCRIPT}")
    return match.group(0)


class InvalidateStalePythonPackagesTest(unittest.TestCase):
    def make_tree(self, root, python="3.13.18"):
        lo = Path(root) / "lo"
        (lo / "workdir/Package/prepared").mkdir(parents=True)
        (lo / "workdir/ExternalPackage").mkdir(parents=True)
        (lo / "download.lst").write_text(f"PYTHON_SHA256SUM := 00\nPYTHON_TARBALL := Python-{python}.tar.xz\n")
        lists = {
            "libffi": "D:/lo/instdir/program/python-core-3.13.15/lib/libffi-8.dll\n",
            "python3": "D:/lo/instdir/program/python-core-3.13.18/lib/_ctypes.pyd\n",
            "cairo": "D:/lo/instdir/program/cairo.dll\n",
        }
        for name, text in lists.items():
            (lo / f"workdir/Package/{name}.filelist").write_text(text)
            (lo / f"workdir/Package/prepared/{name}").write_text("")
            (lo / f"workdir/ExternalPackage/{name}").write_text("")
        return lo

    def run_rule(self, lo):
        snippet = (f'set -Eeuo pipefail\nlog() {{ echo "$*"; }}\nLO="{lo}"\n'
                   f'{shell_function("invalidate_stale_python_packages")}\ninvalidate_stale_python_packages\n')
        return subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, check=True)

    def test_package_in_old_python_core_is_dropped(self):
        with tempfile.TemporaryDirectory() as root:
            lo = self.make_tree(root)
            done = self.run_rule(lo)
            self.assertIn("package libffi delivers into another python-core than 3.13.18", done.stdout)
            for path in ("workdir/Package/libffi.filelist", "workdir/Package/prepared/libffi",
                         "workdir/ExternalPackage/libffi"):
                self.assertFalse((lo / path).exists(), path)
            for name in ("python3", "cairo"):
                self.assertTrue((lo / f"workdir/Package/{name}.filelist").exists(), name)
                self.assertTrue((lo / f"workdir/ExternalPackage/{name}").exists(), name)

    def test_current_python_core_is_kept(self):
        with tempfile.TemporaryDirectory() as root:
            lo = self.make_tree(root, python="3.13.15")
            self.run_rule(lo)
            self.assertTrue((lo / "workdir/Package/libffi.filelist").exists())
            self.assertFalse((lo / "workdir/Package/python3.filelist").exists())  # 3.13.18 is now the stale one

    def test_tree_without_python_tarball_changes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            lo = self.make_tree(root)
            (lo / "download.lst").write_text("CAIRO_TARBALL := cairo-1.tar.xz\n")
            self.run_rule(lo)
            self.assertEqual(len(list((lo / "workdir/Package").glob("*.filelist"))), 3)


if __name__ == "__main__":
    unittest.main()
