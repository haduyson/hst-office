# SPDX-License-Identifier: AGPL-3.0-only
"""make-single-deb.py merges synthetic split packages (no native build needed)."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("make_single_deb", ROOT / "scripts/linux/make-single-deb.py")
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


def make_deb(base, name, depends, files, scripts=None, conffiles=None, arch="amd64", extra=""):
    tree = base / f"tree-{name}"
    (tree / "DEBIAN").mkdir(parents=True)
    for rel, body in files.items():
        f = tree / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    ctl = f"Package: {name}\nVersion: 1.0.0-1\nArchitecture: {arch}\nMaintainer: x\nDescription: d\n"
    if depends:
        ctl += f"Depends: {depends}\n"
    (tree / "DEBIAN/control").write_text(ctl + extra, encoding="utf-8")
    for script, body in (scripts or {}).items():
        (tree / "DEBIAN" / script).write_text(body, encoding="utf-8")
        (tree / "DEBIAN" / script).chmod(0o755)
    if conffiles:
        (tree / "DEBIAN/conffiles").write_text("\n".join(conffiles) + "\n", encoding="utf-8")
    out = base / "split"
    out.mkdir(exist_ok=True)
    subprocess.run(["dpkg-deb", "--root-owner-group", "-b", str(tree), str(out / f"{name}.deb")], check=True, capture_output=True)
    return out


@unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb not available")
class MakeSingleDeb(unittest.TestCase):
    def run_tool(self, base, split, expect_ok=True, release="1.0.0-beta.4.1"):
        out = base / "out"
        proc = subprocess.run(
            ["python3", "-I", str(ROOT / "scripts/linux/make-single-deb.py"), str(split), str(out), "--release", release],
            capture_output=True, text=True, env={**os.environ, "TMPDIR": str(base)},
        )
        if expect_ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc, out

    def test_merges_depends_files_scripts_and_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_deb(base, "hst-office1.0-ure", "libc6, libssl3t64", {"opt/hst-office1.0/a": "a", "opt/hst-office1.0/x.conf": "x", "etc/hst.conf": "c"},
                     conffiles=["/opt/hst-office1.0/./x.conf", "/etc/hst.conf"],
                     extra="Replaces: hst-office1.0-stdlibs\n")
            make_deb(base, "hst-office1.0-core", "hst-office1.0-ure (>= 1.0.0), libc6 (>= 2.39), libglib2.0-0t64 | libglib2.0-0",
                     {"opt/hst-office1.0/b": "b", "usr/lib/menu/hst": "legacy" })
            split = make_deb(base, "hst-office1.0-menus", "hst-office1.0-core", {"usr/share/applications/x.desktop": "[Desktop Entry]"},
                             scripts={"postinst": "#!/bin/sh\nupdate-desktop-database\nexit 0\n", "postrm": "#!/bin/sh\nupdate-desktop-database\nexit 0\n", "prerm": "#!/bin/sh\n# nothing\nexit 0\n"})
            proc, out = self.run_tool(base, split)
            deb = out / "HSTOffice_1.0.0-beta.4.1_Linux_x86-64.deb"
            self.assertTrue(deb.is_file())
            self.assertIn("HSTOffice_1.0.0-beta.4.1_Linux_x86-64.deb", (out / "SHA256SUMS").read_text())
            field = lambda f: subprocess.run(["dpkg-deb", "-f", str(deb), f], capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(field("Package"), "hst-office")
            self.assertEqual(field("Version"), "1:1.0.0~beta.4.1-1")
            self.assertEqual(field("Architecture"), "amd64")
            depends = [c.strip() for c in field("Depends").split(",")]
            self.assertIn("libssl3t64 | libssl3", depends)
            self.assertIn("libglib2.0-0t64 | libglib2.0-0", depends)
            self.assertIn("libc6", depends)
            self.assertNotIn("libc6 (>= 2.39)", depends)  # redundant with the unbounded libc6
            self.assertFalse([d for d in depends if d.startswith("hst-office")])
            for field_name in ("Replaces", "Conflicts"):
                names = {c.strip() for c in field(field_name).split(",")}
                self.assertTrue({"hst-office1.0-ure", "hst-office1.0-core", "hst-office1.0-menus", "hst-office1.0-stdlibs"} <= names)
            listing = subprocess.run(["dpkg-deb", "-c", str(deb)], capture_output=True, text=True, check=True).stdout
            for want in ("opt/hst-office1.0/a", "opt/hst-office1.0/b", "usr/share/applications/x.desktop",
                         "usr/share/doc/hst-office/copyright", "usr/share/metainfo/vn.hasontech.hstoffice.metainfo.xml"):
                self.assertIn(want, listing)
            self.assertNotIn("usr/lib/menu", listing)
            ctl = base / "ctl"
            subprocess.run(["dpkg-deb", "-e", str(deb), str(ctl)], check=True)
            self.assertIn("update-desktop-database", (ctl / "postinst").read_text())
            meta = subprocess.run(["dpkg-deb", "--fsys-tarfile", str(deb)], capture_output=True, check=True).stdout
            xml = subprocess.run(["tar", "-xO", "./usr/share/metainfo/vn.hasontech.hstoffice.metainfo.xml"], input=meta, capture_output=True, check=True).stdout.decode()
            self.assertIn('<release version="1.0.0-beta.4.1"', xml)
            self.assertIn('type="development"', xml)
            postrm = (ctl / "postrm").read_text()
            self.assertIn("update-desktop-database", postrm)
            self.assertIn("rm -rf /opt/hst-office1.0", postrm)
            self.assertTrue(postrm.rstrip().endswith("exit 0"))
            self.assertEqual(subprocess.run(["sh", "-n", str(ctl / "postrm")]).returncode, 0)
            self.assertFalse((ctl / "prerm").exists(), "an exit-0-only script is dropped")
            self.assertEqual((ctl / "conffiles").read_text().split(), ["/etc/hst.conf"])

    def test_rejects_overlapping_files_and_two_script_owners(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_deb(base, "p1", "", {"opt/same": "1"})
            split = make_deb(base, "p2", "", {"opt/same": "2"})
            proc, _ = self.run_tool(base, split, expect_ok=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("opt/same", proc.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            body = {"postinst": "#!/bin/sh\necho hi\nexit 0\n"}
            make_deb(base, "p1", "", {"opt/a": "1"}, scripts=body)
            split = make_deb(base, "p2", "", {"opt/b": "2"}, scripts=body)
            proc, _ = self.run_tool(base, split, expect_ok=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("postinst", proc.stderr)

    def test_rejects_foreign_architecture_and_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            split = make_deb(base, "p1", "", {"opt/a": "1"}, arch="arm64")
            self.assertNotEqual(self.run_tool(base, split, expect_ok=False)[0].returncode, 0)
            empty = base / "empty"
            empty.mkdir()
            self.assertNotEqual(self.run_tool(base, empty, expect_ok=False)[0].returncode, 0)

    def test_final_release_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            split = make_deb(base, "p1", "", {"opt/hst-office1.0/a": "1"},
                             scripts={"postrm": "#!/bin/sh\nupdate-desktop-database\nexit 0\n"})
            _, out = self.run_tool(base, split, release="1.0.0")
            deb = out / "HSTOffice_1.0.0_Linux_x86-64.deb"
            version = subprocess.run(["dpkg-deb", "-f", str(deb), "Version"], capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(version, "1:1.0.0-1")

    def test_rejects_bad_release_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            split = make_deb(base, "p1", "", {"opt/a": "1"})
            proc, _ = self.run_tool(base, split, expect_ok=False, release="1.0-beta")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("bad release id", proc.stderr)

    def test_deb_version_orders_betas_before_final_and_above_published(self):
        def newer(a, b):
            return subprocess.run(["dpkg", "--compare-versions", a, "gt", b]).returncode == 0
        v = MOD.deb_version
        self.assertEqual(v("1.0.0-beta.4.1"), "1:1.0.0~beta.4.1-1")
        self.assertEqual(v("1.0.0"), "1:1.0.0-1")
        self.assertTrue(newer(v("1.0.0-beta.4"), "1.0.0-2"), "beta.4 must beat the published 1.0.0-2")
        self.assertTrue(newer(v("1.0.0-beta.4.1"), "1.0.0-2"))
        chain = ["1.0.0-beta.4", "1.0.0-beta.4.1", "1.0.0-beta.5", "1.0.0-beta.9", "1.0.0-beta.10", "1.0.0-rc.1", "1.0.0", "1.0.1-beta.1", "1.0.1"]
        for lower, higher in zip(chain, chain[1:]):
            self.assertTrue(newer(v(higher), v(lower)), f"{higher} must be newer than {lower}")
        with self.assertRaises(ValueError):
            v("1.0-beta")

    def test_t64_alternatives(self):
        f = MOD.with_t64_alternative
        self.assertEqual(f("libglib2.0-0 (>= 2.70)"), "libglib2.0-0 (>= 2.70) | libglib2.0-0t64 (>= 2.70)")
        self.assertEqual(f("libcups2t64"), "libcups2t64 | libcups2")
        self.assertEqual(f("libc6 (>= 2.35)"), "libc6 (>= 2.35)")
        self.assertEqual(f("libx | python3"), "libx | libxt64 | python3")
        self.assertEqual(f("libc6"), "libc6")

    def test_clause_helpers(self):
        self.assertEqual(MOD.clause_name("libfoo (>= 1) | libbar"), "libfoo")
        self.assertEqual(MOD.clause_name("python3:any"), "python3")
        self.assertEqual(MOD.clauses("a, b (>= 1),\n c"), ["a", "b (>= 1)", "c"])


if __name__ == "__main__":
    unittest.main()
