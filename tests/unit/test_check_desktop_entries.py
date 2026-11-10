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
Type=Application
Name=HST Writer
Categories=Office;WordProcessor;
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

    def test_app_launchers_keep_their_menu_name_icon_and_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            xdg = "opt/hst-office1.0/share/xdg/writer.desktop"
            link = {"usr/share/applications/vn.hasontech.hstoffice-writer.desktop": "/" + xdg}
            code, out = self.run_main(self.build(base / "a", {xdg: CLEAN}, link))
            self.assertEqual(code, 0, out)
            self.assertIn("apps: HST Writer", out)
            for bad, word in ((CLEAN.replace("Name=HST Writer", "Name=HST Office Writer"), "Name="),
                              (CLEAN.replace("Icon=vn.hasontech.hstoffice-writer", "Icon=writer"), "Icon="),
                              (CLEAN.replace("Categories=Office;WordProcessor;", "Categories=Utility;"), "Categories="),
                              (CLEAN + "NoDisplay=true\n", "hidden")):
                code, out = self.run_main(self.build(base / word.strip("="), {xdg: bad}, link))
                self.assertEqual(code, 1, word)
                self.assertIn(word, out)

    def test_app_check_reads_only_the_main_group(self):
        action = CLEAN + "\n[Desktop Action NewDocument]\nName=New Document\nIcon=document-new\n"
        self.assertEqual(MOD.app_hits(action, "vn.hasontech.hstoffice-writer"), [])
        self.assertEqual(MOD.app_hits(CLEAN, "vn.hasontech.hstoffice-base"), [])


class HiddenBase(unittest.TestCase):
    BASE = ("[Desktop Entry]\nNoDisplay=true\nType=Application\nName=HST Base\nIcon=vn.hasontech.hstoffice-base\n"
            "MimeType=application/vnd.oasis.opendocument.base;application/vnd.sun.xml.base;\n")
    START = "[Desktop Entry]\nName=HST Office\nActions=Writer;Calc;Impress;Draw;Math;\n\n[Desktop Action Math]\nName=Math\n"

    def test_base_launcher_is_hidden_but_opens_odb(self):
        self.assertEqual(MOD.base_hits(self.BASE, MOD.BASE_ID), [])
        shown = self.BASE.replace("NoDisplay=true\n", "")
        self.assertEqual(MOD.base_hits(shown, MOD.BASE_ID), ["HST Base is listed in the app menus"])
        no_odb = self.BASE.replace("application/vnd.oasis.opendocument.base;", "")
        self.assertEqual(len(MOD.base_hits(no_odb, MOD.BASE_ID)), 1)

    def test_office_launcher_has_no_base_action(self):
        self.assertEqual(MOD.base_hits(self.START, MOD.START_ID), [])
        with_base = self.START.replace("Draw;Math;", "Draw;Base;Math;")
        self.assertEqual(MOD.base_hits(with_base, MOD.START_ID), ["the HST Office launcher offers a Base action"])
        self.assertEqual(MOD.base_hits(with_base, "vn.hasontech.hstoffice-writer"), [])


if __name__ == "__main__":
    unittest.main()
