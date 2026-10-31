# SPDX-License-Identifier: AGPL-3.0-only
"""UI language resolution, menu/catalog contract and actions without an office process."""
import os
import string
import sys
import unittest
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import _paths
from hst_office import ui_language as ui
from hst_office.data_files import load_locale

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR, XML = "{http://openoffice.org/2001/registry}", "{http://www.w3.org/XML/1998/namespace}"
INSTALLED = ("en-US", "vi")


class ResolutionTest(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(ui.COMMANDS, {"UILanguageVi": "vi", "UILanguageEn": "en-US", "UILanguageSystem": ""})

    def test_resolution_and_choice_with_and_without_vietnamese(self):
        for installed in (INSTALLED, ("en-US",)):
            vi = "vi" if "vi" in installed else ""
            cases = {"": "", "en-US": "en-US", "en": "en-US", "en-GB": "en-US", "EN-us": "en-US",
                     "en_GB": "en-US", "vi": vi, "vi-VN": vi, "VI_vn": vi, "de": "", "garbage": ""}
            for raw, expected in cases.items():
                with self.subTest(raw=raw, installed=installed):
                    self.assertEqual(ui.resolve(raw, installed), expected)
                    self.assertEqual(ui.current_choice(raw, installed), expected)

    def test_exact_then_case_insensitive_then_first_primary_match(self):
        installed = ("en-GB", "EN-us", "en-US", "vi_VN", "de")
        for raw, expected in (("en-US", "en-US"), ("en-us", "EN-us"), ("en-AU", "en-GB"), ("vi", "vi_VN"), ("de", "de")):
            with self.subTest(raw=raw):
                self.assertEqual(ui.resolve(raw, installed), expected)
        self.assertEqual(ui.current_choice("en-GB", installed), "en-US")
        self.assertEqual(ui.current_choice("vi", installed), "vi")
        self.assertEqual(ui.current_choice("de", installed), "")
        self.assertEqual(ui.resolve("vi", ()), "")


class CatalogTest(unittest.TestCase):
    def test_catalog_keys_and_placeholders_match(self):
        vi, en = (load_locale(code)["uiLanguage"] for code in ("vi", "en"))

        def compare(left, right):
            self.assertEqual(set(left), set(right))
            for key, value in left.items():
                if isinstance(value, dict):
                    compare(value, right[key])
                else:
                    self.assertTrue(value)
                    self.assertTrue(right[key])
                    fields = lambda text: {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}
                    self.assertEqual(fields(value), fields(right[key]), key)

        compare(vi, en)
        self.assertEqual(vi["names"], {"vi": "Tiếng Việt", "en-US": "English", "": "Theo máy"})
        self.assertEqual(set(vi), {"title", "locked", "selected", "saveError", "restart", "names"})

    def test_menu_titles_urls_contexts_and_placement(self):
        root = ET.parse(os.path.join(EXT, "Addons.xcu")).getroot()
        menu = root.find("./node/node[@%sname='OfficeMenuBar']/node[@%sname='org.hst.office.vi']/node" % (OOR, OOR))
        m9 = menu.find("node[@%sname='m9']" % OOR)
        self.assertEqual([node.get(OOR + "name") for node in menu][-2:], ["m8", "m9"])
        children = m9.findall("node/node")
        labels = ("Ngôn ngữ giao diện", "Tiếng Việt", "English", "Theo máy")
        self.assertEqual([node.find("prop[@%sname='URL']/value" % OOR).text for node in children],
                         ["org.hst.office.vi:" + command for command in ui.COMMANDS])
        context = menu.find("node[@%sname='m7']/prop[@%sname='Context']/value" % (OOR, OOR)).text
        for node, title in zip([m9] + children, labels):
            self.assertEqual({value.get(XML + "lang", ""): value.text for value in node.findall("prop[@%sname='Title']/value" % OOR)},
                             {"": title, "en-US": title, "vi": title})
            self.assertEqual(node.find("prop[@%sname='Context']/value" % OOR).text, context)
            self.assertEqual(node.find("prop[@%sname='Target']/value" % OOR).text, "_self")
        notebook = root.find("./node/node[@%sname='OfficeNotebookBar']" % OOR)
        self.assertFalse(any("UILanguage" in (value.text or "") for value in notebook.iter("value")))
        for code in ("vi", "en"):
            catalog = load_locale(code)["menu"]
            self.assertEqual(tuple(catalog[key] for key in ("uiLanguage", "uiLanguageVi", "uiLanguageEn", "uiLanguageSystem")), labels)


class ActionTest(unittest.TestCase):
    def setUp(self):
        self.ctx, self.frame = Mock(), Mock()
        self.state = {"raw": "vi", "installed": INSTALLED, "locked": False}
        self.box = Mock(return_value=False)
        patches = ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(patch.dict(sys.modules, {"hst_office.dialogs": SimpleNamespace(message_box=self.box)}))
        self.read = patches.enter_context(patch.object(ui, "read_state", return_value=self.state))
        self.write = patches.enter_context(patch.object(ui, "write_choice"))
        self.restart = patches.enter_context(patch.object(ui, "request_restart"))
        self.strings = load_locale("vi")["uiLanguage"]

    def test_locked_does_not_write_or_restart(self):
        self.state["locked"] = True
        ui.run(self.ctx, self.frame, "UILanguageEn")
        self.write.assert_not_called()
        self.restart.assert_not_called()
        self.box.assert_called_once_with(self.ctx, self.frame.getContainerWindow(), self.strings["title"], self.strings["locked"])

    def test_same_choice_including_aliases_does_not_write(self):
        for command, raw in (("UILanguageVi", "vi-VN"), ("UILanguageEn", "en-GB"), ("UILanguageSystem", "")):
            with self.subTest(command=command):
                self.state["raw"] = raw
                self.box.reset_mock()
                ui.run(self.ctx, self.frame, command)
                self.box.assert_called_once_with(self.ctx, self.frame.getContainerWindow(), self.strings["title"],
                                                 self.strings["selected"].format(name=self.strings["names"][ui.COMMANDS[command]]))
        self.write.assert_not_called()
        self.restart.assert_not_called()

    def test_write_failure_shows_error_without_restart(self):
        self.write.side_effect = RuntimeError("write denied")
        ui.run(self.ctx, self.frame, "UILanguageEn")
        self.write.assert_called_once_with(self.ctx, "en-US")
        self.box.assert_called_once_with(self.ctx, self.frame.getContainerWindow(), self.strings["title"],
                                         "Không lưu được lựa chọn ngôn ngữ giao diện: write denied", error=True)
        self.restart.assert_not_called()

    def test_success_restarts_only_after_yes_and_supports_no_frame(self):
        def answer_restart_prompt(*args, **kwargs):
            self.write.assert_called_once_with(self.ctx, "en-US")
            return self.box.return_value

        self.box.side_effect = answer_restart_prompt
        for answer in (True, False):
            with self.subTest(answer=answer):
                self.box.reset_mock()
                self.box.return_value = answer
                self.write.reset_mock()
                self.restart.reset_mock()
                ui.run(self.ctx, None, "UILanguageEn")
                self.box.assert_called_once_with(self.ctx, None, self.strings["title"], self.strings["restart"], ask=True)
                if answer:
                    self.restart.assert_called_once_with(self.ctx)
                else:
                    self.restart.assert_not_called()

    def test_system_clears_unresolvable_preference(self):
        self.state["raw"] = "garbage"
        ui.run(self.ctx, self.frame, "UILanguageSystem")
        self.write.assert_called_once_with(self.ctx, "")
        self.assertTrue(self.box.call_args.kwargs["ask"])

    def test_status_reads_fresh_and_handles_read_failure(self):
        for locked in (True, False):
            self.state["locked"] = locked
            self.assertEqual(ui.status(self.ctx, "UILanguageVi"), (not locked, True))
            self.assertEqual(ui.status(self.ctx, "UILanguageEn"), (not locked, False))
        self.state["raw"] = "de"
        self.assertEqual(ui.status(self.ctx, "UILanguageSystem"), (True, True))
        self.read.side_effect = RuntimeError("read failed")
        self.assertEqual(ui.status(self.ctx, "UILanguageVi"), (True, False))


class UnoBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.ctx = Mock()
        patches = ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(patch.dict(sys.modules, {"uno": SimpleNamespace(createUnoStruct=lambda name: SimpleNamespace()),
                                                      "com.sun.star.beans.PropertyAttribute": SimpleNamespace(READONLY=16)}))

    def test_config_access_lock_and_write_commit(self):
        provider = self.ctx.ServiceManager.createInstanceWithContext.return_value
        read, installed, write = Mock(), Mock(), Mock()
        read.getPropertyValue.return_value = "en-GB"
        installed.getElementNames.return_value = INSTALLED
        write.getPropertySetInfo.return_value.getPropertyByName.return_value.Attributes = 16 | 2
        provider.createInstanceWithArguments.side_effect = (read, installed, write, write)
        self.assertEqual(ui.read_state(self.ctx), {"raw": "en-GB", "installed": INSTALLED, "locked": True})
        ui.write_choice(self.ctx, "")
        accesses = provider.createInstanceWithArguments.call_args_list
        self.assertEqual([call.args[0].rsplit(".", 1)[1] for call in accesses],
                         ["ConfigurationAccess", "ConfigurationAccess", "ConfigurationUpdateAccess", "ConfigurationUpdateAccess"])
        self.assertEqual([(call.args[1][0].Name, call.args[1][0].Value) for call in accesses],
                         [("nodepath", path) for path in (ui.CONFIG_PATH, "/org.openoffice.Setup/Office/InstalledLocales", ui.CONFIG_PATH, ui.CONFIG_PATH)])
        write.setPropertyValue.assert_called_once_with("UILocale", "")
        write.commitChanges.assert_called_once_with()

    def test_unknown_lock_is_unlocked_but_raw_read_failure_raises(self):
        node = self.ctx.ServiceManager.createInstanceWithContext.return_value.createInstanceWithArguments.return_value
        node.getPropertyValue.return_value = "vi"
        node.getElementNames.return_value = INSTALLED
        node.getPropertySetInfo.side_effect = RuntimeError("no metadata")
        self.assertFalse(ui.read_state(self.ctx)["locked"])
        node.getPropertyValue.side_effect = RuntimeError("read failed")
        with self.assertRaisesRegex(RuntimeError, "read failed"):
            ui.read_state(self.ctx)

    def test_restart_dispatches_parsed_url_asynchronously(self):
        parsed = object()
        transformer = self.ctx.ServiceManager.createInstanceWithContext.return_value
        transformer.parseStrict.return_value = (True, parsed)
        ui.request_restart(self.ctx)
        self.ctx.ServiceManager.createInstanceWithContext.assert_called_once_with("com.sun.star.util.URLTransformer", self.ctx)
        self.assertEqual(transformer.parseStrict.call_args.args[0].Complete, "vnd.sun.star.autorecovery:/doSessionRestart")
        self.ctx.getValueByName.assert_called_once_with("/singletons/com.sun.star.frame.theAutoRecovery")
        url, args = self.ctx.getValueByName.return_value.dispatch.call_args.args
        self.assertIs(url, parsed)
        self.assertEqual([(arg.Name, arg.Value) for arg in args], [("DispatchAsynchron", True)])


if __name__ == "__main__":
    unittest.main()
