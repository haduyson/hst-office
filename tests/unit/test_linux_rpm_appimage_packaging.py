# SPDX-License-Identifier: AGPL-3.0-only
"""Pure parts of the .rpm and AppImage repackaging (scripts/linux/rpm_spec.py, scripts/linux/appimage/
appimage_desktop_integration.py): versions, ELF requires, spec text, launcher rewriting, per-user integration."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "scripts", "linux"))
sys.path.insert(0, os.path.join(_paths.ROOT, "scripts", "linux", "appimage"))
import appimage_desktop_integration as integ  # noqa: E402
import rpm_spec  # noqa: E402

READELF = """
Dynamic section at offset 0x1 contains 3 entries:
 0x0000000000000001 (NEEDED)             Shared library: [libuno_sal.so.3]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000e (SONAME)             Library soname: [libmergedlo.so]
Version needs section '.gnu.version_r' contains 2 entries:
  000000: Version: 1  File: libc.so.6  Cnt: 2
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 4
  0x0020:   Name: GLIBC_2.2.5  Flags: none  Version: 3
  0x0030: Version: 1  File: libuno_sal.so.3  Cnt: 1
  0x0040:   Name: UDK_3_0_0  Flags: none  Version: 2
"""


class Rpm(unittest.TestCase):
    def test_version(self):
        self.assertEqual(rpm_spec.rpm_version("1.0.2"), ("1.0.2", "1"))
        self.assertEqual(rpm_spec.rpm_version("1.0.2-beta.1"), ("1.0.2~beta.1", "1"))
        for bad in ("26.8.1.1", "1.0", "", None, "1.0.2-"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                rpm_spec.rpm_version(bad)

    def test_requires_skip_bundled_libraries(self):
        scan = rpm_spec.parse_readelf(READELF)
        self.assertEqual(scan[0], "libmergedlo.so")
        requires = rpm_spec.external_requires([scan], {"libuno_sal.so.3"})
        self.assertEqual(requires, ["libc.so.6()(64bit)", "libc.so.6(GLIBC_2.2.5)(64bit)", "libc.so.6(GLIBC_2.34)(64bit)"])
        self.assertEqual(rpm_spec.baseline(requires), "2.34")
        more = requires + ["libm.so.6(GLIBC_2.35)(64bit)", "libstdc++.so.6(GLIBCXX_3.4.30)(64bit)",
                           "libstdc++.so.6(GLIBCXX_3.4.9)(64bit)", "libstdc++.so.6(CXXABI_1.3.13)(64bit)"]
        self.assertEqual(rpm_spec.baseline(more), "2.35")  # libm counts as much as libc
        self.assertEqual(rpm_spec.baseline(more, "GLIBCXX_"), "3.4.30")
        self.assertIsNone(rpm_spec.baseline([]))

    def test_files_and_spec(self):
        paths = ["/opt/hst-office1.0/program/soffice", "/usr/bin/hst-office", "/usr/share/doc/hst-office/copyright",
                 "/usr/share/applications/vn.hasontech.hstoffice-writer.desktop"]
        files = rpm_spec.file_list(paths)
        self.assertEqual(files, ["/opt/hst-office1.0", "/usr/bin/hst-office",
                                 "/usr/share/applications/vn.hasontech.hstoffice-writer.desktop", "%doc /usr/share/doc/hst-office"])
        with self.assertRaises(ValueError):
            rpm_spec.file_list(["/usr/share/a b"])
        spec = rpm_spec.spec_text("1.0.2", "1", ["libc.so.6()(64bit)"], files, "/w/payload")
        for line in ("Name: hst-office", "Version: 1.0.2", "Release: 1", "Vendor: HASON TECH", "AutoReqProv: no",
                     "Requires: libc.so.6()(64bit)", "%global _build_id_links none", "%global __os_install_post %{nil}"):
            self.assertIn(line + "\n", spec)
        self.assertIn('if [ "$1" -eq 0 ]; then rm -rf /opt/hst-office1.0; fi', spec)  # erase only, not upgrade
        self.assertNotIn("26.8", spec)
        with self.assertRaises(ValueError):
            rpm_spec.spec_text("1.0.2", "1", [], files, "/w/pay load")


DESKTOP = """[Desktop Entry]
Name=HST Office
Exec=hst-office1.0 %U
TryExec=hst-office1.0
Actions=Writer;

[Desktop Action Writer]
Exec=hst-office1.0 --writer
"""


class Integration(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.appdir = os.path.join(self.root, "AppDir")
        xdg = os.path.join(self.appdir, "opt", "hst-office1.0", "share", "xdg")
        apps = os.path.join(self.appdir, "usr", "share", "applications")
        icons = os.path.join(self.appdir, "usr", "share", "icons", "hicolor", "48x48", "apps")
        mime = os.path.join(self.appdir, "usr", "share", "mime", "packages")
        for d in (xdg, apps, icons, mime):
            os.makedirs(d)
        for module in ("startcenter", "writer"):
            with open(os.path.join(xdg, module + ".desktop"), "w", encoding="utf-8") as handle:
                handle.write(DESKTOP)
            os.symlink("/opt/hst-office1.0/share/xdg/%s.desktop" % module, os.path.join(apps, "vn.hasontech.hstoffice-%s.desktop" % module))
        for name, folder in (("vn.hasontech.hstoffice-writer.png", icons), ("hst-office1.0.xml", mime)):
            with open(os.path.join(folder, name), "wb") as handle:
                handle.write(b"data")
        self.appimage = os.path.join(self.root, 'My "Apps" $x', "HST 100%.AppImage")
        os.makedirs(os.path.dirname(self.appimage))
        open(self.appimage, "w").close()
        self.env = {"HOME": self.root, "XDG_DATA_HOME": os.path.join(self.root, "data")}
        patch = mock.patch.object(integ.shutil, "which", return_value=None)  # no host tools, no notification
        patch.start()
        self.addCleanup(patch.stop)

    def read(self, *parts):
        with open(os.path.join(self.env["XDG_DATA_HOME"], *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_exec_quoting(self):
        self.assertEqual(integ.exec_quote("/a b/c"), '"/a b/c"')
        self.assertEqual(integ.exec_quote('/x"$`\\%'), '"/x\\\\"\\\\$\\\\`\\\\\\\\%%"')
        with self.assertRaises(ValueError):
            integ.exec_quote("/a\nb")

    def test_install_move_remove_cycle(self):
        self.assertTrue(integ.auto(self.appdir, self.appimage, self.env, system_launcher="/nonexistent"))
        writer = self.read("applications", "vn.hasontech.hstoffice-writer.desktop")
        self.assertIn("Exec=" + integ.exec_quote(self.appimage) + " --writer\n", writer)
        self.assertNotIn("TryExec", writer)
        start = self.read("applications", "vn.hasontech.hstoffice-startcenter.desktop")
        self.assertIn("Actions=Writer;RemoveIntegration;", start)
        self.assertIn("--remove-desktop-integration", start)
        self.assertEqual(self.read("icons", "hicolor", "48x48", "apps", "vn.hasontech.hstoffice-writer.png"), "data")
        self.assertEqual(self.read("mime", "packages", integ.MIME_NAME), "data")
        self.assertFalse(integ.auto(self.appdir, self.appimage, self.env, system_launcher="/nonexistent"))  # unchanged
        moved = self.appimage + ".moved"
        os.rename(self.appimage, moved)
        self.assertTrue(integ.auto(self.appdir, moved, self.env, system_launcher="/nonexistent"))
        self.assertIn(integ.exec_quote(moved), self.read("applications", "vn.hasontech.hstoffice-writer.desktop"))
        integ.remove(self.env)
        self.assertEqual(sorted(os.listdir(os.path.join(self.env["XDG_DATA_HOME"], "applications"))), [])
        self.assertEqual(self.read("hst-office", "appimage-integration.state"), "removed\n")
        self.assertFalse(integ.auto(self.appdir, moved, self.env, system_launcher="/nonexistent"))  # remembered
        integ.install(self.appdir, moved, self.env)
        self.assertTrue(os.path.exists(os.path.join(self.env["XDG_DATA_HOME"], "applications", "vn.hasontech.hstoffice-writer.desktop")))

    def test_system_install_and_foreign_manifest_entries(self):
        self.assertFalse(integ.auto(self.appdir, self.appimage, self.env, system_launcher=self.appimage))
        outside = os.path.join(self.root, "keep.txt")
        open(outside, "w").close()
        manifest, _ = integ.state_paths(self.env)
        os.makedirs(os.path.dirname(manifest))
        with open(manifest, "w", encoding="utf-8") as handle:
            json.dump({"files": [outside, 7]}, handle)
        integ.remove(self.env)
        self.assertTrue(os.path.exists(outside))  # only files inside $XDG_DATA_HOME are ever deleted

    def test_main_arguments(self):
        self.assertEqual(integ.main(["x"], self.env), 64)
        self.assertEqual(integ.main(["x", "--install"], self.env), 2)  # not inside an AppImage
        env = dict(self.env, APPDIR=self.appdir, APPIMAGE=self.appimage)
        self.assertEqual(integ.main(["x", "--install"], env), 0)
        self.assertEqual(integ.main(["x", "--remove"], env), 0)


if __name__ == "__main__":
    unittest.main()
