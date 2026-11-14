# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Cập nhật: the "Gửi mã máy ẩn danh khi kiểm tra cập nhật và báo lỗi" box, its registration, default,
administrator lock, and that unticking it stops the ID."""
import os
import re
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from install_id_support import DLG, EXT, FakeConfig, OOR, cfg
from hst_office import update_install_id as iid  # noqa: E402
from hst_office import update_options as opts  # noqa: E402


class OptionsPage(unittest.TestCase):
    def controls(self):
        root = ET.parse(os.path.join(EXT, "dialogs", "Update.xdl")).getroot()
        return {c.get(DLG + "id"): c for c in root.iter() if c.get(DLG + "id")}

    def test_page_is_registered_in_the_hst_office_group(self):
        root = ET.parse(os.path.join(EXT, "OptionsDialog.xcu")).getroot()
        leaf = next(n for n in root.iter("node") if n.get(OOR + "name") == "vn.hasontech.hstoffice.Options.Update")
        props = {p.get(OOR + "name"): p.find("value").text for p in leaf.findall("prop")}
        self.assertEqual(props["Label"], "Cập nhật")
        self.assertEqual(props["OptionsPage"], "%origin%/dialogs/Update.xdl")
        self.assertEqual(props["EventHandlerService"], opts.HANDLER_NAME)
        with open(os.path.join(EXT, "python", "hst_office_component.py"), encoding="utf-8") as handle:
            self.assertIn('("update_options", "UpdateOptionsHandler", "%s"' % opts.HANDLER_NAME, handle.read())

    def test_checkbox_label_and_default(self):
        box = self.controls()["sendInstallId"]
        self.assertEqual(box.tag, DLG + "checkbox")
        self.assertEqual(box.get(DLG + "value"),
                         "Gửi mã máy ẩn danh khi kiểm tra cập nhật và báo lỗi (giúp HASON TECH biết số máy đang dùng)")
        self.assertEqual(box.get(DLG + "checked"), "true")

    def test_texts_name_no_other_product(self):
        text = " ".join(c.get(DLG + "value") or "" for c in self.controls().values())
        self.assertIsNone(re.search(r"Microsoft|Word|Excel|PowerPoint|LibreOffice", text))

    def test_page_state_and_save(self):
        values = dict(cfg.DEFAULTS)
        self.assertEqual(opts.page_state(values, set()), (True, True))
        self.assertEqual(opts.page_state(dict(values, SendInstallId=False), {"SendInstallId"}), (False, False))
        self.assertIs(opts.value_to_save(False, values, set()), False)
        self.assertIsNone(opts.value_to_save(True, values, set()))  # unchanged
        self.assertIsNone(opts.value_to_save(False, values, {"SendInstallId"}))  # locked

    def test_handler_loads_and_saves(self):
        config = FakeConfig().patch(self)
        self.addCleanup(iid.set_sending, True)
        controls = {name: mock.Mock() for name in ("sendInstallId", "locked")}
        window = mock.Mock()
        window.getControl.side_effect = controls.__getitem__
        handler = opts.UpdateOptionsHandler(None)
        self.assertTrue(handler.callHandlerMethod(window, "initialize", "external_event"))
        controls["sendInstallId"].setState.assert_called_with(1)
        controls["sendInstallId"].setEnable.assert_called_with(True)
        controls["locked"].setVisible.assert_called_with(False)
        controls["sendInstallId"].getState.return_value = 0
        handler.callHandlerMethod(window, "ok", "external_event")
        self.assertEqual(config.saves, [("SendInstallId", False)])
        self.assertIsNone(iid.for_check(None))  # unticked: the next check sends nothing
        self.assertIsNone(iid.current("3f2b8c1e-9a4d-4e6f-8b7a-0c1d2e3f4a5b"))  # nor a retry of a check under way
        controls["sendInstallId"].getState.return_value = 1
        handler.callHandlerMethod(window, "ok", "external_event")
        self.assertEqual(config.saves[-1], ("SendInstallId", True))
        self.assertEqual(iid.current("x"), "x")

    def test_locked_page_is_greyed_out_and_writes_nothing(self):
        config = FakeConfig(locked={"SendInstallId"}, SendInstallId=False).patch(self)
        controls = {name: mock.Mock() for name in ("sendInstallId", "locked")}
        window = mock.Mock()
        window.getControl.side_effect = controls.__getitem__
        handler = opts.UpdateOptionsHandler(None)
        handler.callHandlerMethod(window, "initialize", "external_event")
        controls["sendInstallId"].setState.assert_called_with(0)
        controls["sendInstallId"].setEnable.assert_called_with(False)
        controls["locked"].setVisible.assert_called_with(True)
        controls["sendInstallId"].getState.return_value = 1
        handler.callHandlerMethod(window, "ok", "external_event")
        self.assertEqual(config.saves, [])


if __name__ == "__main__":
    unittest.main()
