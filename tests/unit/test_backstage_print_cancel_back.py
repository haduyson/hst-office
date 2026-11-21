# SPDX-License-Identifier: AGPL-3.0-only
""""Hủy" (Cancel) and "Quay lại" (Back) next to the "In" button of the Print page of the File panel
(hst-backstage-print-cancel-back.patch). Read from the patches: the panel .ui of hst-backstage-print.patch with this
patch's hunk applied, the Vietnamese strings and the hooks."""
import json
import os
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT
from patch_sections import added, po_entries, sections

PATCH = "hst-backstage-print-cancel-back.patch"
BASE = "hst-backstage-print.patch"
PANEL_UI = "vcl/uiconfig/ui/hstprintpanel.ui"
DIALOG = "vcl/source/window/printdlg.cxx"
DIALOG_HXX = "vcl/inc/printdlg.hxx"
PAGE = "sfx2/source/backstage/hstbackstageprint.cxx"
CANCEL = "sfx2/source/backstage/hstbackstageprintcancel.cxx"
CANCEL_HXX = "sfx2/source/backstage/hstbackstageprintcancel.hxx"
VCL_PO = "translations/source/vi/vcl/messages.po"
PATCH_DIR = os.path.join(ROOT, "patches", "libreoffice")


def panel_ui():
    """The panel .ui as the series leaves it: the print patch's new file with this patch's hunk."""
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, PANEL_UI)
        os.makedirs(os.path.dirname(target))
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(added(BASE, PANEL_UI) + "\n")
        hunk = "--- a/%s\n+++ b/%s\n%s\n" % (PANEL_UI, PANEL_UI, "\n".join(sections(PATCH)[PANEL_UI]))
        subprocess.run(["patch", "-s", "-p1", "--fuzz=0", "-d", tmp], input=hunk, text=True, check=True)
        with open(target, encoding="utf-8") as handle:
            return ET.fromstring(handle.read().encode("utf-8"))


def by_id(root, oid):
    return next(o for o in root.iter("object") if o.get("id") == oid)


def props(obj):
    return {p.get("name"): p for p in obj.findall("property")}


def vi_strings():
    """msgctxt -> Vietnamese label: the series' vcl po entries, l10n/vi/vcl.jsonl, then vi-overrides.jsonl."""
    strings = {}
    for name in (BASE, PATCH):
        strings.update({ctx: value[1] for ctx, value in po_entries(added(name, VCL_PO)).items()})
    for path in (os.path.join(ROOT, "l10n", "vi", "vcl.jsonl"), os.path.join(ROOT, "l10n", "vi-overrides.jsonl")):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line) if line.strip() else {}
                if row.get("file") == "vcl/messages.po" and row.get("msgstr"):
                    strings[row["msgctxt"]] = row["msgstr"]
    return strings


def access_key(label):
    match = re.search(r"_(.)", label or "")
    return match.group(1).upper() if match else None


class Buttons(unittest.TestCase):
    def test_series_order(self):
        with open(os.path.join(PATCH_DIR, "series"), encoding="utf-8") as handle:
            series = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertIn(PATCH, series)
        for earlier in (BASE, "hst-print-job-printer-release.patch"):  # the panel and its test file
            self.assertLess(series.index(earlier), series.index(PATCH))

    def test_print_cancel_back_in_one_group(self):
        root = panel_ui()
        group = by_id(root, "printbuttons")
        ids = [c.find("object").get("id") for c in group.findall("child")]
        self.assertEqual(ids, ["ok", "cancel", "back"])  # also the tab order
        row = by_id(root, "printrow")
        self.assertEqual([c.find("object").get("id") for c in row.findall("child")], ["printbuttons", "copiesbox"])
        hidden = {o.get("id") for o in by_id(root, "hiddenbox").iter("object")}
        self.assertNotIn("cancel", hidden)

    def test_secondary_buttons_are_visible_and_labelled(self):
        root = panel_ui()
        ok = props(by_id(root, "ok"))
        for oid in ("cancel", "back"):
            with self.subTest(id=oid):
                obj = by_id(root, oid)
                prop = props(obj)
                self.assertEqual(prop["visible"].text, "True")
                self.assertEqual(prop["height-request"].text, ok["height-request"].text)  # as tall as "In"
                self.assertEqual(prop["use-underline"].text, "True")
                self.assertEqual(prop["label"].get("context"), "hstprintpanel|" + oid)
                self.assertTrue(prop["tooltip-text"].text)
                self.assertEqual(prop["image-position"].text, "top")  # an icon above the label, as "In"
                image = props(by_id(root, prop["image"].text))
                self.assertTrue(image["icon-name"].text.startswith("cmd/lc_"))
                # the secondary look: not the accent of the print button
                self.assertIsNone(obj.find("style"))
                description = obj.find("child/object[@class='AtkObject']/property")
                self.assertEqual(description.get("name"), "AtkObject::accessible-description")
                self.assertTrue(description.text)

    def test_english_access_keys_are_free(self):
        root = panel_ui()
        keys = {}
        for obj in root.iter("object"):
            prop = props(obj)
            if "label" in prop and prop.get("use-underline") is not None and prop["use-underline"].text == "True":
                if obj.get("id") not in ("help", "previewbox"):  # hidden in the panel
                    keys.setdefault(access_key(prop["label"].text), []).append(obj.get("id"))
        self.assertEqual(keys["E"], ["cancel"])
        self.assertEqual(keys["B"], ["back"])

    def test_vietnamese_labels_and_access_keys(self):
        strings = vi_strings()
        self.assertEqual(strings["hstprintpanel|cancel"], "Hủ_y")
        self.assertEqual(strings["hstprintpanel|back"], "_Quay lại")
        for ctx in ("canceltip", "backtip", "extended_tip|cancel", "extended_tip|back"):
            self.assertTrue(strings["hstprintpanel|" + ctx])
        root = panel_ui()
        others = set()
        for obj in root.iter("object"):
            prop = props(obj)
            if obj.get("id") in ("cancel", "back", "help", "previewbox") or "label" not in prop:
                continue
            if prop.get("use-underline") is not None and prop["use-underline"].text == "True":
                others.add(access_key(strings.get(prop["label"].get("context")) or prop["label"].text))
        # Sheets' scaling label of the application's options ("T_hu phóng") is in the panel too
        others.add("H")
        self.assertNotIn("Y", others)
        self.assertNotIn("Q", others)


class Hooks(unittest.TestCase):
    def test_dialog_hooks(self):
        code = added(PATCH, DIALOG)
        self.assertIn('weld_button(u"back"_ustr)', code)
        self.assertIn("maPanelCancelHdl.Call(*this);", code)
        self.assertIn("maPanelBackHdl.Call(*this);", code)
        # the panel's Cancel does not store the last printer/collate choice; Print and the dialog still do
        self.assertIn("if (m_xDialog || &rButton == mxOKButton.get())", code)
        self.assertIn("void setPanelCloseHdls(", added(PATCH, DIALOG_HXX))

    def test_page_closes_and_cancel_undoes_margins(self):
        code = added(PATCH, PAGE)
        self.assertIn("m_xJob->SetCloseHdls(", code)
        self.assertIn("UndoPrintPageMargins(m_xFrame, std::exchange(m_nMarginSteps, 0));", code)
        self.assertIn("m_aClosePanel(); // cancels the job (Deactivate), as Esc does", code)
        undo = added(PATCH, CANCEL)
        self.assertIn("getCurrentUndoActionTitle() == aTitle", undo)  # only the page's own steps
        self.assertIn("SfxResId(STR_HST_BS_PRINT_MARGINS)", undo)

    def test_hst_owned_logic_and_thin_hooks(self):
        for path in (CANCEL, CANCEL_HXX):
            self.assertIn("SPDX-License-Identifier: LicenseRef-HST-Proprietary", added(PATCH, path))
        # the modified LibreOffice files only get small hooks
        hook = sum(1 for line in sections(PATCH)[DIALOG] + sections(PATCH)[DIALOG_HXX]
                   if line.startswith("+") and line[1:].strip())
        self.assertLessEqual(hook, 30)


if __name__ == "__main__":
    unittest.main()
