# SPDX-License-Identifier: AGPL-3.0-only
"""Real temporary trees: vendor detection, symlinks and p11-kit overrides."""
import json
from pathlib import Path
import tempfile
import unittest

import _paths
from hst_office.usb_token_detect import detect


class DetectionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()

    def touch(self, path, text=""):
        path = self.root / path.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_vnpt_primary_path_and_bundle_alias(self):
        primary = self.touch("usr/local/lib/libvnptca_p11_v8.dylib")
        alias = self.touch("Applications/VNPT-CA Token Manager.app/Contents/Resources/libvnptca_p11_v8.dylib")
        alias.unlink()
        alias.symlink_to(primary)
        self.touch("Library/OpenSC/lib/opensc-pkcs11.so")
        rows = detect("macos", self.root, self.home)
        self.assertEqual([r["vendor"] for r in rows], ["VNPT-CA", "OpenSC"])
        self.assertEqual(rows[0]["path"], str(primary))

    def test_vendor_platforms_and_dylib_glob(self):
        paths = ("usr/lib/libcastle.so.1.0.0", "usr/lib/libeTPkcs11.so", "usr/lib/bit4id/libbit4xpki.so",
                 "usr/lib/x86_64-linux-gnu/opensc-pkcs11.so", "usr/local/lib/libcastle.1.0.0.dylib",
                 "usr/local/lib/misaca_csp11_v2.dylib", "usr/local/lib/easyca_csp11_v1.dylib")
        for path in paths:
            self.touch(path)
        self.assertEqual(len(detect("linux", self.root, self.home)), 4)
        self.assertEqual(len(detect("macos", self.root, self.home)), 3)
        self.assertEqual(detect("windows", self.root, self.home), [])

    def test_missing_broken_symlink_and_directory_ignored(self):
        path = self.touch("usr/lib/libcastle.so.1.0.0")
        path.unlink()
        path.symlink_to("missing")
        (self.root / "usr/lib/libeTPkcs11.so").mkdir()
        self.assertEqual(detect("linux", self.root, self.home), [])

    def test_p11_kit_absolute_and_relative_modules(self):
        self.touch("usr/share/p11-kit/modules/test.module", "# comment\nmodule: /opt/vendor/token.so\n")
        self.touch("opt/vendor/token.so")
        self.touch("etc/pkcs11/modules/relative.module", "module: extra.so\n")
        self.touch("usr/lib/x86_64-linux-gnu/pkcs11/extra.so")
        self.assertEqual(len(detect("linux", self.root, self.home)), 2)

    def test_p11_kit_user_disables_vendor_and_admin_replaces_vendor(self):
        for place, value in (("usr/share/p11-kit/modules", "/old.so"), ("etc/pkcs11/modules", "/new.so")):
            self.touch(place + "/test.module", "module: " + value)
        self.touch("old.so")
        self.touch("new.so")
        self.assertTrue(detect("linux", self.root, self.home)[0]["path"].endswith("new.so"))
        self.touch("home/.config/pkcs11/modules/test.module", "module:\n")
        self.assertEqual(detect("linux", self.root, self.home), [])

    def test_p11_trust_and_restricted_modules_are_not_tokens(self):
        self.touch("usr/share/p11-kit/modules/trust.module", "module: /trust.so\ntrust-policy: yes\n")
        self.touch("etc/pkcs11/modules/restricted.module", "module: /trust.so\nenable-in: special-app\n")
        self.touch("trust.so")
        self.assertEqual(detect("linux", self.root, self.home), [])

    def test_catalog_requires_evidence_and_no_invented_ca_names(self):
        data = json.loads((Path(_paths.ROOT) / "data/hst/pkcs11-modules.json").read_text())
        for row in data["modules"]:
            self.assertTrue({"vendor", "label", "platform", "paths", "source"} <= row.keys())
            self.assertIn("https://", row["source"])
            if row["vendor"] in ("Viettel-CA", "BKAV-CA", "FPT-CA"):
                self.assertEqual(row["paths"], [])

    def test_menu_always_vietnamese_including_english_and_start_center(self):
        import xml.etree.ElementTree as ET
        from hst_office.data_files import load_locale
        root = ET.parse(Path(_paths.ROOT) / "extensions/hst-vietnamese-tools/Addons.xcu")
        ns = "{http://openoffice.org/2001/registry}"
        matches = [n for n in root.iter("node") if any(v.text == "org.hst.office.vi:SetupUsbToken"
                   for v in n.findall("prop/value"))]
        self.assertEqual(len(matches), 1)
        node = matches[0]
        self.assertEqual([v.text for v in node.findall("prop[@%sname='Title']/value" % ns)],
                         ["Thiết lập USB Token"] * 3)
        self.assertIn("StartModule", node.find("prop[@%sname='Context']/value" % ns).text)
        for language in ("en", "vi"):
            self.assertEqual(load_locale(language)["menu"]["usbToken"], "Thiết lập USB Token")

    def test_catalog_alias_cannot_override_explicit_exclusion(self):
        primary = self.touch("usr/lib/libcastle.so.1.0.0")
        alias = self.touch("usr/lib/libeTPkcs11.so")
        alias.unlink()
        alias.symlink_to(primary)
        self.touch("home/.config/pkcs11/modules/token.module",
                   "module: /usr/lib/libcastle.so.1.0.0\ndisable-in: soffice.bin\n")
        self.assertEqual(detect("linux", self.root, self.home), [])

    def test_global_none_ignores_user_exclusion(self):
        self.touch("usr/lib/libcastle.so.1.0.0")
        self.touch("etc/pkcs11/pkcs11.conf", "user-config: none\n")
        self.touch("home/.config/pkcs11/pkcs11.conf", "user-config: only\n")
        self.touch("home/.config/pkcs11/modules/token.module",
                   "module: /usr/lib/libcastle.so.1.0.0\ndisable-in: soffice.bin\n")
        self.assertEqual(len(detect("linux", self.root, self.home)), 1)

    def test_global_only_ignores_system_modules(self):
        self.touch("etc/pkcs11/pkcs11.conf", "user-config: only\n")
        self.touch("etc/pkcs11/modules/token.module", "module: /custom.so\n")
        self.touch("custom.so")
        self.assertEqual(detect("linux", self.root, self.home), [])

    def test_empty_user_module_also_excludes_catalog_path(self):
        self.touch("usr/lib/libcastle.so.1.0.0")
        self.touch("etc/pkcs11/modules/token.module", "module: /usr/lib/libcastle.so.1.0.0\n")
        self.touch("home/.config/pkcs11/modules/token.module", "module:\n")
        self.assertEqual(detect("linux", self.root, self.home), [])

    def test_alias_override_keeps_enabled_canonical_driver(self):
        primary = self.touch("usr/lib/libcastle.so.1.0.0")
        alias = self.root / "active.so"
        alias.symlink_to(primary)
        self.touch("usr/share/p11-kit/modules/token.module", "module: /usr/lib/libcastle.so.1.0.0\n")
        self.touch("home/.config/pkcs11/modules/token.module", "module: /active.so\n")
        for entries in (None, []):
            with self.subTest(catalog=entries is None):
                rows = detect("linux", self.root, self.home, entries)
                self.assertEqual([Path(row["path"]).resolve() for row in rows], [primary])

    def test_final_override_restores_vendor_after_admin_disable_or_replacement(self):
        primary = self.touch("usr/lib/libcastle.so.1.0.0")
        self.touch("usr/lib/libeTPkcs11.so")
        self.touch("usr/share/p11-kit/modules/token.module", "module: /usr/lib/libcastle.so.1.0.0\n")
        self.touch("home/.config/pkcs11/modules/token.module", "module: /usr/lib/libcastle.so.1.0.0\n")
        for intermediate in ("module: /usr/lib/libeTPkcs11.so\n", "module:\n",
                             "module: /usr/lib/libcastle.so.1.0.0\ndisable-in: soffice.bin\n"):
            with self.subTest(intermediate=intermediate):
                self.touch("etc/pkcs11/modules/token.module", intermediate)
                rows = detect("linux", self.root, self.home, entries=[])
                self.assertEqual([Path(row["path"]).resolve() for row in rows], [primary])
        # A displaced administrator driver cannot re-enter through the catalog.
        self.touch("etc/pkcs11/modules/token.module", "module: /usr/lib/libeTPkcs11.so\n")
        self.assertEqual([row["path"] for row in detect("linux", self.root, self.home)], [str(primary)])

    def test_final_alias_disable_or_empty_override_excludes_all_paths(self):
        primary = self.touch("usr/lib/libcastle.so.1.0.0")
        (self.root / "active.so").symlink_to(primary)
        self.touch("usr/share/p11-kit/modules/token.module", "module: /usr/lib/libcastle.so.1.0.0\n")
        self.touch("etc/pkcs11/modules/token.module", "module: /active.so\n")
        for final in ("module:\n", "", "module: /active.so\ndisable-in: soffice.bin\n",
                      "module: /active.so\nenable-in: another-app\n", "module: /active.so\ntrust-policy: yes\n"):
            with self.subTest(final=final):
                self.touch("home/.config/pkcs11/modules/token.module", final)
                self.assertEqual(detect("linux", self.root, self.home), [])

    def test_separate_explicit_exclusion_wins_over_enabled_alias_override(self):
        primary = self.touch("usr/lib/libcastle.so.1.0.0")
        (self.root / "active.so").symlink_to(primary)
        self.touch("usr/share/p11-kit/modules/token.module", "module: /usr/lib/libcastle.so.1.0.0\n")
        self.touch("home/.config/pkcs11/modules/token.module", "module: /active.so\n")
        self.touch("etc/pkcs11/modules/disabled.module",
                   "module: /usr/lib/libcastle.so.1.0.0\ndisable-in: soffice.bin\n")
        self.assertEqual(detect("linux", self.root, self.home), [])
