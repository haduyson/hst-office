# SPDX-License-Identifier: AGPL-3.0-only
"""check-desktop-entries.py rejects upstream product names and window classes in launchers of a .deb."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_desktop_entries", ROOT / "scripts/linux/check-desktop-entries.py")
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)

CLEAN = """[Desktop Entry]
Name=HST Office Văn bản
Comment=Soạn thảo văn bản
Keywords=Text;Letter;Microsoft Word;odt;docx;
Exec=hst-office1.0 --writer %U
Icon=vn.hasontech.hstoffice-writer
StartupWMClass=vn.hasontech.hstoffice-writer
MimeType=x-scheme-handler/vnd.libreoffice.command;
"""


class HitsTest(unittest.TestCase):
    def test_clean_entry_passes(self):
        # MimeType may keep upstream identifiers (scheme handlers), Exec is not read.
        self.assertEqual(MOD.hits(CLEAN), [])
        self.assertEqual(MOD.identity_hits(CLEAN, "vn.hasontech.hstoffice-writer"), [])
        self.assertEqual(MOD.identity_hits(CLEAN, None), [])

    def test_window_class_must_be_the_launcher_id(self):
        upstream = CLEAN.replace("StartupWMClass=vn.hasontech.hstoffice-writer", "StartupWMClass=libreoffice-writer")
        self.assertEqual(len(MOD.identity_hits(upstream, "vn.hasontech.hstoffice-writer")), 1)
        self.assertEqual(len(MOD.identity_hits(upstream, None)), 1)  # no link: still not LibreOffice's
        other = CLEAN.replace("StartupWMClass=vn.hasontech.hstoffice-writer", "StartupWMClass=vn.hasontech.hstoffice-calc")
        self.assertEqual(len(MOD.identity_hits(other, "vn.hasontech.hstoffice-writer")), 1)
        icon = CLEAN.replace("Icon=vn.hasontech.hstoffice-writer", "Icon=libreoffice-writer")
        self.assertEqual(MOD.identity_hits(icon, "vn.hasontech.hstoffice-writer"), ["Icon=libreoffice-writer"])
        stock = CLEAN.replace("Icon=vn.hasontech.hstoffice-writer", "Icon=document-new")
        self.assertEqual(MOD.identity_hits(stock, "vn.hasontech.hstoffice-writer"), [])

    def test_keywords_in_any_locale_fail(self):
        for line in ("Keywords=Text;OpenOffice Writer;odt;", "Keywords[vi]=Văn bản;LibreOffice;",
                     "GenericName[de]=Libre Office Textverarbeitung", "Comment=by The Document Foundation"):
            self.assertEqual(MOD.hits(CLEAN + line + "\n"), [line], line)


@unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb not available")
class PackageTest(unittest.TestCase):
    def build(self, base, files, links=None):
        tree = base / "tree"
        (tree / "DEBIAN").mkdir(parents=True)
        (tree / "DEBIAN/control").write_text("Package: t\nVersion: 1\nArchitecture: all\nMaintainer: x\nDescription: d\n")
        for rel, body in files.items():
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_text(body, encoding="utf-8")
        for rel, target in (links or {}).items():  # usr/share/applications/<id>.desktop -> /opt/... like the .deb
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            os.symlink(target, tree / rel)
        deb = base / "t.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "-b", str(tree), str(deb)], check=True, capture_output=True)
        return str(deb)

    def run_main(self, deb):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = MOD.main([deb])
        return code, out.getvalue()

    def test_package_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            clean = self.build(base / "a", {"opt/hst-office1.0/share/xdg/writer.desktop": CLEAN})
            self.assertEqual(self.run_main(clean)[0], 0)
            dirty = self.build(base / "b", {"opt/hst-office1.0/share/xdg/calc.desktop": CLEAN + "Keywords=Chart;OpenOffice Calc;\n"})
            code, out = self.run_main(dirty)
            self.assertEqual(code, 1)
            self.assertIn("OpenOffice Calc", out)
            empty = self.build(base / "c", {"opt/hst-office1.0/readme.txt": "x"})
            self.assertEqual(self.run_main(empty)[0], 1)

    def test_launcher_link_sets_the_expected_window_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            xdg = "opt/hst-office1.0/share/xdg/writer.desktop"
            link = {"usr/share/applications/vn.hasontech.hstoffice-writer.desktop": "/" + xdg}
            self.assertEqual(self.run_main(self.build(base / "a", {xdg: CLEAN}, link))[0], 0)
            wrong = CLEAN.replace("StartupWMClass=vn.hasontech.hstoffice-writer", "StartupWMClass=libreoffice-writer")
            code, out = self.run_main(self.build(base / "b", {xdg: wrong}, link))
            self.assertEqual(code, 1)
            self.assertIn("launcher id vn.hasontech.hstoffice-writer", out)


if __name__ == "__main__":
    unittest.main()
