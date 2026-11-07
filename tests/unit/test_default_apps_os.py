# SPDX-License-Identifier: AGPL-3.0-only
"""Per-OS default-apps command building (pure) and the Linux launcher reading, without changing the machine."""
import os
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import default_apps_linux as lx
from hst_office import default_apps_os as osx

WRITER = ("application/vnd.oasis.opendocument.text;application/msword;text/plain;application/rtf;"
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/x-abiword;"
          "application/vnd.ms-word.document.macroEnabled.12;application/msword;").split(";")


class Linux(unittest.TestCase):
    def test_only_office_types_without_duplicates(self):
        self.assertEqual(lx.office_types(WRITER), [
            "application/vnd.oasis.opendocument.text", "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-word.document.macroEnabled.12"])

    def test_one_xdg_mime_call_per_app_with_hst_launcher_ids(self):
        commands = lx.linux_commands({"writer": WRITER})
        self.assertEqual([c[:3] for c in commands], [
            ["xdg-mime", "default", "vn.hasontech.hstoffice-writer.desktop"],
            ["xdg-mime", "default", "vn.hasontech.hstoffice-calc.desktop"],
            ["xdg-mime", "default", "vn.hasontech.hstoffice-impress.desktop"]])
        self.assertNotIn("text/plain", commands[0])
        # launchers not found: the fallback types still include .docx/.xlsx/.pptx
        for command, probe in zip(commands, lx.PROBE_MIME):
            self.assertIn(probe, command)

    def test_reads_mime_types_from_installed_launcher(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "applications"))
            with open(os.path.join(home, "applications", lx.DESKTOP_IDS["calc"]), "w", encoding="utf-8") as handle:
                handle.write("[Desktop Entry]\nName=HST Sheets\nMimeType=application/vnd.ms-excel;text/csv;\n")
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": home, "XDG_DATA_DIRS": home}):
                self.assertEqual(lx.declared_types(lx.DESKTOP_IDS["calc"]), ["application/vnd.ms-excel", "text/csv", ""])
                self.assertEqual(lx.declared_types("missing.desktop"), [])

    def test_failure_is_raised_with_the_tool_message(self):
        failed = mock.Mock(returncode=4, stderr="xdg-mime: no permission", stdout="")
        with mock.patch.object(lx.shutil, "which", return_value="/usr/bin/xdg-mime"), \
                mock.patch.object(lx, "_run", return_value=failed), \
                mock.patch.object(lx, "declared_types", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "no permission"):
                lx.linux_make_default()

    def test_success_is_verified_with_a_query(self):
        ok = mock.Mock(returncode=0, stderr="", stdout="")
        with mock.patch.object(lx.shutil, "which", return_value="/usr/bin/xdg-mime"), \
                mock.patch.object(lx, "_run", return_value=ok), mock.patch.object(lx, "declared_types", return_value=[]):
            with mock.patch.object(lx, "linux_is_registered", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "mimeapps.list"):
                    lx.linux_make_default()
            with mock.patch.object(lx, "linux_is_registered", return_value=True):
                self.assertEqual(lx.linux_make_default(), (True, ""))

    def test_registered_only_when_every_probe_type_is_hst(self):
        answers = {t: "vn.hasontech.hstoffice-writer.desktop\n" for t in lx.PROBE_MIME}
        run = lambda argv: mock.Mock(stdout=answers[argv[-1]])
        with mock.patch.object(lx.shutil, "which", return_value="/usr/bin/xdg-mime"), mock.patch.object(lx, "_run", run):
            self.assertTrue(lx.linux_is_registered())
            answers[lx.PROBE_MIME[2]] = "other-suite-impress.desktop\n"
            self.assertFalse(lx.linux_is_registered())


class MacAndWindows(unittest.TestCase):
    def test_mac_utis_cover_the_three_apps_and_the_probe(self):
        self.assertTrue(set(osx.MAC_PROBE_UTIS) <= set(osx.MAC_UTIS))
        self.assertEqual(osx.BUNDLE_ID, "vn.hasontech.hstoffice")

    def test_mac_utis_are_declared_by_the_bundle(self):
        plist = os.path.join(_paths.ROOT, "upstream", "libreoffice", "sysui", "desktop", "macosx", "Info.plist.in")
        if not os.path.exists(plist):
            self.skipTest("no upstream tree")
        with open(plist, encoding="utf-8") as handle:
            text = handle.read()
        for uti in osx.MAC_UTIS:
            self.assertIn("<string>%s</string>" % uti, text)

    def test_mac_permanent_locations_count_as_installed(self):
        inside = "/Contents/Resources/extensions/hst-vietnamese-tools/python/hst_office/default_apps_os.py"
        home = "/Users/a"
        for place in ("/Applications/HST Office.app", "/Applications/Office/HST Office.app",
                      "/Users/a/Applications/HST Office.app"):
            self.assertTrue(osx.mac_in_applications(place + inside, home), place)
        for place in ("/Volumes/HST Office/HST Office.app", "/Users/a/Downloads/HST Office.app",
                      "/private/var/folders/x1/T/AppTranslocation/9F3A/d/HST Office.app"):
            self.assertFalse(osx.mac_in_applications(place + inside, home), place)
        self.assertEqual(osx.mac_bundle_of("/Applications/HST Office.app" + inside), "/Applications/HST Office.app")

    def test_mac_action_refuses_a_copy_that_must_move(self):
        with mock.patch.object(osx, "mac_in_applications", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Applications"):
                osx.mac_make_default()

    def test_mac_partial_failure_names_the_formats_left(self):
        accepted = {"org.openxmlformats.wordprocessingml.document"}

        class LS:
            def LSSetDefaultRoleHandlerForContentType(self, ref, roles, bundle):
                return 0 if ref in accepted else -10814

        class CF:
            def CFStringCreateWithCString(self, alloc, text, encoding):
                return text.decode()

            def CFRelease(self, ref):
                pass
        with mock.patch.object(osx, "mac_in_applications", return_value=True), \
                mock.patch.object(osx, "_launch_services", return_value=(None, CF(), LS())):
            with self.assertRaises(RuntimeError) as caught:
                osx.mac_make_default()
        message = str(caught.exception)
        self.assertIn(".xlsx", message)
        self.assertIn(".pptx", message)
        self.assertNotIn(".docx,", message + ",")  # the accepted format is not listed as failed
        accepted.update(osx.MAC_UTIS)
        with mock.patch.object(osx, "mac_in_applications", return_value=True), \
                mock.patch.object(osx, "_launch_services", return_value=(None, CF(), LS())):
            self.assertEqual(osx.mac_make_default(), (True, ""))

    def test_windows_deep_link_keeps_the_registration_hive(self):
        self.assertEqual(osx.windows_settings_uri([("Other Suite 1", "HKLM"), ("HST Office 1.0", "HKLM")]),
                         "ms-settings:defaultapps?registeredAppMachine=HST%20Office%201.0")
        self.assertEqual(osx.windows_settings_uri([("HST Office 1.0", "HKCU")]),
                         "ms-settings:defaultapps?registeredAppUser=HST%20Office%201.0")
        # both (a per-user and a per-machine install): the current user's own registration
        self.assertEqual(osx.windows_settings_uri([("HST Office 1.0", "HKLM"), ("HST Office 1.0", "HKCU")]),
                         "ms-settings:defaultapps?registeredAppUser=HST%20Office%201.0")
        self.assertEqual(osx.windows_settings_uri([("Other Suite", "HKLM")]), "ms-settings:defaultapps")

    def test_unknown_system(self):
        self.assertFalse(osx.is_registered("Haiku"))
        with self.assertRaises(RuntimeError):
            osx.make_default("Haiku")


if __name__ == "__main__":
    unittest.main()
