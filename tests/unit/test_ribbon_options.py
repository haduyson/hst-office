# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Ribbon: registration, the page's controls and texts, and the handler's calls to the core's
vn.hasontech.hst.RibbonCustomization service (load and save of the recently used tab's switch, clearing the history,
opening the customize dialog, an older core without the service)."""
import os
import re
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from install_id_support import DLG, EXT, OOR
from hst_office import ribbon_options as opts  # noqa: E402


class FakeService:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.calls = []

    def execute(self, arguments):
        arguments = dict(arguments)
        self.calls.append(arguments)
        action = arguments["Action"]
        if action == "getRecentEnabled":
            return self.enabled
        if action == "setRecentEnabled":
            self.enabled = arguments["Enabled"]
        return True


def make_ctx(service):
    ctx = mock.Mock()
    if service is None:
        ctx.ServiceManager.createInstanceWithContext.return_value = None
    else:
        ctx.ServiceManager.createInstanceWithContext.side_effect = (
            lambda name, _ctx: service if name == opts.CORE_SERVICE else None)
    return ctx


def make_window():
    controls = {name: mock.Mock() for name in opts.CONTROLS + ("status",)}
    window = mock.Mock()
    window.getControl.side_effect = controls.__getitem__
    return window, controls


def handler(service):
    # the pairs as they are: the fake service reads them as a list of (name, value)
    return opts.RibbonOptionsHandler(make_ctx(service), to_uno=list)


class Registration(unittest.TestCase):
    def controls(self):
        root = ET.parse(os.path.join(EXT, "dialogs", "Ribbon.xdl")).getroot()
        return {c.get(DLG + "id"): c for c in root.iter() if c.get(DLG + "id")}

    def test_page_is_registered_in_the_hst_office_group(self):
        root = ET.parse(os.path.join(EXT, "OptionsDialog.xcu")).getroot()
        leaf = next(n for n in root.iter("node") if n.get(OOR + "name") == "vn.hasontech.hstoffice.Options.Ribbon")
        props = {p.get(OOR + "name"): p.find("value").text for p in leaf.findall("prop")}
        self.assertEqual(props["Label"], "Ribbon")
        self.assertEqual(props["OptionsPage"], "%origin%/dialogs/Ribbon.xdl")
        self.assertEqual(props["EventHandlerService"], opts.HANDLER_NAME)
        with open(os.path.join(EXT, "python", "hst_office_component.py"), encoding="utf-8") as handle:
            self.assertIn('("ribbon_options", "RibbonOptionsHandler", "%s"' % opts.HANDLER_NAME, handle.read())

    def test_controls_and_their_actions(self):
        controls = self.controls()
        for name in opts.CONTROLS + ("status",):
            self.assertIn(name, controls)
        self.assertEqual(controls["customize"].get(DLG + "value"), "Tùy chỉnh ribbon")
        self.assertEqual(controls["clearHistory"].get(DLG + "value"), "Xóa lịch sử")
        self.assertEqual(controls["recentEnabled"].get(DLG + "value"), "Hiện thẻ Sử dụng gần đây")
        self.assertEqual(controls["recentEnabled"].get(DLG + "checked"), "true")
        script = "{http://openoffice.org/2000/script}"
        for name in ("customize", "clearHistory"):
            event = controls[name].find(script + "event")
            self.assertEqual(event.get(script + "macro-name"), "vnd.sun.star.UNO:" + name)
            self.assertIn(name, opts.METHODS)

    def test_texts_are_vietnamese_and_name_no_other_product(self):
        text = " ".join(c.get(DLG + "value") or "" for c in self.controls().values())
        self.assertIsNone(re.search(r"Microsoft|Word|Excel|PowerPoint|LibreOffice", text))
        self.assertIn("30 ngày", text)
        self.assertIn("trên máy này", text)  # the history stays local


class Pure(unittest.TestCase):
    def test_job_arguments(self):
        self.assertEqual(opts.job_arguments("clearHistory"), [("Action", "clearHistory")])
        self.assertEqual(opts.job_arguments("setRecentEnabled", Enabled=False),
                         [("Action", "setRecentEnabled"), ("Enabled", False)])

    def test_value_to_save(self):
        self.assertIsNone(opts.value_to_save(True, True))
        self.assertIs(opts.value_to_save(False, True), False)
        self.assertIs(opts.value_to_save(1, False), True)


class Handler(unittest.TestCase):
    def test_load_shows_the_switch_and_ok_saves_a_change_only(self):
        service = FakeService(enabled=False)
        page = handler(service)
        window, controls = make_window()
        self.assertTrue(page.callHandlerMethod(window, "initialize", "external_event"))
        controls["recentEnabled"].setState.assert_called_with(0)
        for name in opts.CONTROLS:
            controls[name].setEnable.assert_called_with(True)
        controls["recentEnabled"].getState.return_value = 0
        page.callHandlerMethod(window, "ok", "external_event")
        self.assertNotIn("setRecentEnabled", [c["Action"] for c in service.calls])
        controls["recentEnabled"].getState.return_value = 1
        page.callHandlerMethod(window, "ok", "external_event")
        self.assertEqual(service.calls[-1], {"Action": "setRecentEnabled", "Enabled": True})
        self.assertTrue(service.enabled)

    def test_back_reloads_and_cancel_writes_nothing(self):
        service = FakeService(enabled=True)
        page = handler(service)
        window, controls = make_window()
        page.callHandlerMethod(window, "initialize", "external_event")
        controls["recentEnabled"].getState.return_value = 0
        page.callHandlerMethod(window, "back", "external_event")
        controls["recentEnabled"].setState.assert_called_with(1)
        self.assertEqual([c["Action"] for c in service.calls], ["getRecentEnabled", "getRecentEnabled"])

    def test_clear_history_acts_at_once(self):
        service = FakeService()
        page = handler(service)
        window, controls = make_window()
        self.assertTrue(page.callHandlerMethod(window, None, "clearHistory"))
        self.assertEqual(service.calls, [{"Action": "clearHistory"}])
        controls["status"].setText.assert_called_with(opts.CLEARED)

    def test_customize_passes_the_page_window_as_parent(self):
        service = FakeService()
        page = handler(service)
        window, _ = make_window()
        self.assertTrue(page.callHandlerMethod(window, None, "customize"))
        self.assertEqual(service.calls, [{"Action": "customize", "ParentWindow": window.getPeer()}])

    def test_older_core_greys_the_page_out(self):
        page = handler(None)
        window, controls = make_window()
        self.assertTrue(page.callHandlerMethod(window, "initialize", "external_event"))
        for name in opts.CONTROLS:
            controls[name].setEnable.assert_called_with(False)
        controls["status"].setText.assert_called_with(opts.UNAVAILABLE)
        page.callHandlerMethod(window, "ok", "external_event")  # nothing to save, nothing raised
        self.assertTrue(page.callHandlerMethod(window, None, "clearHistory"))
        controls["status"].setText.assert_called_with(opts.CLEAR_FAILED)

    def test_a_failing_core_never_raises_into_the_dialog(self):
        service = mock.Mock()
        service.execute.side_effect = RuntimeError("core")
        page = handler(service)
        window, _ = make_window()
        with mock.patch.object(opts.diag_log, "exception") as logged:
            self.assertTrue(page.callHandlerMethod(window, "initialize", "external_event"))
            self.assertTrue(page.callHandlerMethod(window, None, "customize"))
        self.assertEqual(logged.call_count, 2)

    def test_unknown_method(self):
        self.assertFalse(handler(FakeService()).callHandlerMethod(None, None, "other"))


if __name__ == "__main__":
    unittest.main()
