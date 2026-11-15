# SPDX-License-Identifier: AGPL-3.0-only
"""The privacy policy link in the About dialog, Tùy chọn ▸ HST Office ▸ Cập nhật, the error report dialog and the
citation source form: the right page and UTM per place, the UI-language label, and a browser hand-off only on a click
(no URL of their own on the controls, so nothing opens or loads before the click)."""
import os
import re
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from install_id_support import DLG, EXT, FakeConfig  # noqa: F401 - UNO stubs before any hst_office import
import citation_entry_fakes as fakes
import _paths

from hst_office import error_report_dialog, privacy_link, update_logic, update_options  # noqa: E402
from hst_office import error_report_info as info  # noqa: E402

TAIL = "?utm_source=hst-office&utm_medium=%s&utm_campaign=hst-office-1-0"
PAGE = "https://office.hasontech.vn/quyen-rieng-tu/"
PATCHES = os.path.join(_paths.ROOT, "patches", "libreoffice")


def read(*parts):
    with open(os.path.join(_paths.ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


class PrivacyLinkTest(unittest.TestCase):
    def setUp(self):
        self.opened = []
        patcher = mock.patch("hst_office.update_ui.open_url", lambda ctx, url: self.opened.append(url))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(privacy_link.OPENED.clear)

    def test_urls_follow_the_utm_convention_and_pass_the_link_check(self):
        for medium in ("about", "options", "error-report", "citations"):
            url = privacy_link.url(medium)
            self.assertEqual(PAGE + TAIL % medium, url)
            self.assertTrue(update_logic.is_safe_link(url), url)
        with self.assertRaises(ValueError):
            privacy_link.url("somewhere-else")

    def test_label_in_the_ui_language(self):
        self.assertEqual("Chính sách quyền riêng tư", privacy_link.label("vi-VN"))
        self.assertEqual("Privacy policy", privacy_link.label("en-US"))
        self.assertEqual("Privacy policy", privacy_link.label(None))

    def test_open_hands_the_url_to_the_browser_and_survives_a_missing_browser(self):
        self.assertTrue(privacy_link.open_policy(None, "options"))
        self.assertEqual([PAGE + TAIL % "options"], self.opened)
        with mock.patch("hst_office.update_ui.open_url", side_effect=RuntimeError("no browser")), \
                mock.patch("hst_office.diag_log.exception") as logged:
            self.assertFalse(privacy_link.open_policy(None, "options"))
        logged.assert_called_once()

    def test_options_page_link_is_wired_once_and_opens_only_on_click(self):
        root = ET.parse(os.path.join(EXT, "dialogs", "Update.xdl")).getroot()
        link = next(c for c in root.iter() if c.get(DLG + "id") == "privacy")
        self.assertEqual(DLG + "linklabel", link.tag)
        self.assertIsNone(link.get(DLG + "url"))  # no URL of its own: only the handler's click action opens it
        self.assertEqual("Chính sách quyền riêng tư", link.get(DLG + "value"))
        FakeConfig().patch(self)
        controls = {name: mock.Mock() for name in ("sendInstallId", "locked", "privacy")}
        window = mock.Mock()
        window.getControl.side_effect = controls.__getitem__
        handler = update_options.UpdateOptionsHandler(None)
        handler.callHandlerMethod(window, "initialize", "external_event")
        handler.callHandlerMethod(window, "back", "external_event")
        listener = controls["privacy"].addActionListener
        listener.assert_called_once()
        self.assertEqual("Privacy policy", controls["privacy"].getModel().Label)  # no office: English fallback
        self.assertEqual([], self.opened)
        listener.call_args[0][0].actionPerformed(None)
        self.assertEqual([PAGE + TAIL % "options"], self.opened)

    def test_error_report_dialog_link_beside_the_buttons(self):
        with mock.patch.object(error_report_dialog, "Dialog", fakes.FakeDialog), \
                mock.patch.object(error_report_dialog.info, "environment", lambda ctx, frame: ({"version": "1.0.2", "build": "1"}, info.os_info(), "vi-VN", "writer")), \
                mock.patch.object(error_report_dialog, "release_info", lambda: {"release": "1.0.2"}), \
                mock.patch.object(error_report_dialog, "proxy", lambda ctx: None):
            report = error_report_dialog.ReportDialog(None, None)
            fakes.FakeDialog.script = [lambda d: d.click("privacy")]
            self.addCleanup(setattr, fakes.FakeDialog, "script", [])
            report.run()
        controls = report.dialog.controls
        link, preview, send = controls["privacy"], controls["preview"], controls["send"]
        self.assertEqual("link", link.kind)
        self.assertLessEqual(preview.x + preview.w, link.x)
        self.assertLessEqual(link.x + link.w, send.x)
        self.assertTrue(preview.y <= link.y < preview.y + preview.h)
        self.assertEqual([PAGE + TAIL % "error-report"], self.opened)

    def test_about_patch_links_the_same_page_with_a_vietnamese_label(self):
        patch = read("patches", "libreoffice", "hst-about-privacy-link.patch")
        self.assertIn('u"%s"\n+                              "%s"_ustr' % (PAGE, TAIL % "about"), patch)
        self.assertIn('+                    <property name="label" translatable="yes" context="aboutdialog|privacy">'
                      'Privacy policy</property>', patch)
        self.assertRegex(patch, r'\+msgctxt "aboutdialog\|privacy"\n\+msgid "Privacy policy"\n'
                                r'\+msgstr "Chính sách quyền riêng tư"')
        self.assertNotIn("<property name=\"uri\">", patch)  # the URL is set in code, with its UTM
        series = [line for line in read("patches", "libreoffice", "series").splitlines() if line.strip()]
        self.assertLess(series.index("hst-about.patch"), series.index("hst-about-privacy-link.patch"))

    def test_privacy_doc_points_to_the_public_page_and_lists_the_mediums(self):
        doc = read("docs", "PRIVACY.md")
        self.assertIn(PAGE, doc)
        for medium in ("options", "error-report", "citations"):
            self.assertIn("`%s`" % medium, doc)

    def test_no_other_product_named(self):
        texts = " ".join(privacy_link.LABELS.values()) + read("patches", "libreoffice", "hst-about-privacy-link.patch")
        self.assertIsNone(re.search(r"Microsoft|\bWord\b|Excel|PowerPoint", texts))


if __name__ == "__main__":
    unittest.main()
