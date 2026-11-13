# SPDX-License-Identifier: AGPL-3.0-only
"""Online lookup in the citation source form sends something only when one of its two buttons is clicked.

What docs/PRIVACY.md promises, checked on the real form (citation_entry_dialog.run) driven through a fake dialog:
only "Tra cứu" and "Tìm theo dòng đã dán" reach the network, never typing, pasting, changing the type or opening
the form; a result only fills the fields and nothing reaches the library before the form is saved; the
administrator key /org.hasontech.hstoffice.Citations/OnlineLookup switches both off and the form says so; the
line beside each button says what is sent where, in the UI language; the update check's proxy is used."""
import pathlib
import re
import types
import unittest
from unittest import mock

import _paths
import citation_entry_fakes as fakes
from citation_entry_fakes import FakeDialog, Library, Transport

from hst_office import citation_entry_dialog as entry  # noqa: E402 - after the UNO stubs of citation_entry_fakes
from hst_office import citation_lookup, citation_lookup_action, citation_style, citation_texts, citation_ui

PYTHON = pathlib.Path(_paths.ROOT, "extensions", "hst-vietnamese-tools", "python", "hst_office")
XCS = pathlib.Path(_paths.ROOT, "extensions", "hst-vietnamese-tools", "citations.xcs")
HINTS = {
    "vi": ("Mã bạn gõ sẽ được gửi tới dịch vụ tra cứu tương ứng (doi.org, Crossref, NCBI, arXiv, Open Library).",
           "Dòng này (tối đa 500 ký tự) sẽ được gửi tới Crossref (api.crossref.org) để tìm thông tin thư mục."),
    "en": ("The identifier you type will be sent to the matching lookup service (doi.org, Crossref, NCBI, arXiv, "
           "Open Library).",
           "This line (up to 500 characters) will be sent to Crossref (api.crossref.org) to find its bibliographic "
           "record."),
}
LINE = "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444."


class SourceFormLookupTest(unittest.TestCase):
    def setUp(self):
        self.texts = citation_texts.load_language("vi")
        self.style = citation_style.load_style("vn-so")
        self.transport, self.library = Transport(fakes.crossref_replies()), Library()
        self.enabled = True
        for name in ("choose", "inform", "ask", "save_library"):
            self.addCleanup(setattr, citation_ui, name, getattr(citation_ui, name))
        self.shown = fakes.ui_recorder(citation_ui)
        for target, attribute, value in (
                (entry, "Dialog", FakeDialog),
                (citation_lookup, "http_transport", lambda timeout=None: self.transport),
                (citation_lookup, "_GATE", citation_lookup.RateGate(clock=lambda: 1e9)),
                (citation_lookup_action, "config", lambda ctx: citation_lookup.LookupConfig(enabled=self.enabled))):
            patcher = mock.patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_form(self, *actions):
        FakeDialog.script = list(actions)
        self.addCleanup(setattr, FakeDialog, "script", [])
        captured = {}
        original = FakeDialog.execute

        def execute(dialog, peer=None):
            captured["dialog"] = dialog
            return original(dialog, peer)
        with mock.patch.object(FakeDialog, "execute", execute):
            saved = entry.run(None, None, self.texts, None, self.library, self.style)
        return saved, captured["dialog"]

    def test_opening_typing_pasting_and_offline_split_send_nothing(self):
        def edit_everything(dialog):
            for name, control in list(dialog.controls.items()):
                if control.kind == "edit":  # a real identifier where one goes: a lookup would reach the network
                    dialog.type_into(name, "10.1038/nature14539" if name == "lookupText" else LINE)
            dialog.select("type", 2)
            for _name, callback in dialog.watchers:  # every change, selection and check listener of the form
                callback()
            dialog.click("paste")  # "Tách thành các trường" splits offline
        saved, dialog = self.run_form(edit_everything, lambda d: d.click("cancel"))
        self.assertIsNone(saved)
        self.assertEqual([], self.transport.requests)
        online = {n for n, c in dialog.controls.items() if c.kind == "button"} - {"lookup", "lookupLine"}
        self.assertEqual({"paste", "ok", "cancel"}, online)

    def test_tra_cuu_fills_the_form_and_stores_nothing_until_saved(self):
        def look_up(dialog):
            dialog.type_into("lookupText", "10.1038/nature14539")
            dialog.click("lookup")
            self.assertEqual("Deep learning", dialog.get("f_title"))
            self.assertEqual(([], []), (self.library.added, [s for s in self.shown if s == "saved library"]))
        saved, _dialog = self.run_form(look_up, lambda d: d.click("cancel"))
        self.assertIsNone(saved)
        self.assertEqual(["doi.org"], [r["url"].split("/")[2] for r in self.transport.requests])
        self.assertEqual([], self.library.added)

        saved, _dialog = self.run_form(look_up, lambda d: d.click("ok"))
        self.assertEqual("Deep learning", saved["title"])
        self.assertEqual(["Deep learning"], [item["title"] for item in self.library.added])

    def test_pasted_line_goes_to_crossref_only_on_its_button(self):
        def find(dialog):
            dialog.type_into("pasteText", LINE)
            self.assertEqual([], self.transport.requests)
            dialog.click("lookupLine")
        saved, dialog = self.run_form(find, lambda d: d.click("cancel"))
        self.assertIsNone(saved)
        [request] = self.transport.requests
        self.assertTrue(request["url"].startswith("https://api.crossref.org/works?"))
        self.assertIn("query.bibliographic=LeCun", request["url"])
        self.assertEqual("Deep learning", dialog.get("f_title"))  # the first match, picked in the question
        self.assertTrue(any("1. " in text and "2. " in text for text in self.shown))
        self.assertEqual([], self.library.added)

    def test_administrator_switch_blocks_both_buttons_and_the_form_says_so(self):
        self.enabled = False

        def click_both(dialog):
            dialog.type_into("lookupText", "10.1038/nature14539")
            dialog.type_into("pasteText", LINE)
            dialog.click("lookup")
            dialog.click("lookupLine")
        _saved, dialog = self.run_form(click_both, lambda d: d.click("cancel"))
        off = self.texts["entry"]["lookupOff"]
        self.assertEqual([], self.transport.requests)
        self.assertEqual((off, off), (dialog.controls["lookupHint"].Label, dialog.controls["lineHint"].Label))
        self.assertEqual(2, self.shown.count(off))

    def test_hint_beside_each_button_in_the_ui_language(self):
        for language, (id_hint, line_hint) in HINTS.items():
            self.texts = citation_texts.load_language(language)
            _saved, dialog = self.run_form(lambda d: d.click("cancel"))
            controls = dialog.controls
            self.assertEqual((id_hint, line_hint), (controls["lookupHint"].Label, controls["lineHint"].Label))
            lookup, line = controls["lookup"], controls["lookupLine"]
            self.assertLessEqual(controls["lookupHint"].y - (lookup.y + lookup.h), 4)  # right under "Tra cứu"
            self.assertLessEqual(abs(controls["lineHint"].y - line.y), 2)  # on the row of its button
            self.assertLessEqual(line.x + line.w, controls["lineHint"].x)
        self.assertEqual("Tra cứu", citation_texts.load_language("vi")["entry"]["lookupButton"])
        self.assertEqual("Tìm theo dòng đã dán", citation_texts.load_language("vi")["entry"]["lineButton"])


class LookupSettingsTest(unittest.TestCase):
    def test_key_and_proxy_reach_the_lookup_settings(self):
        node = types.SimpleNamespace(getPropertyValue={"OnlineLookup": False, "LookupContact": ""}.get)
        with mock.patch("hst_office.update_config._node", lambda ctx, path: node), \
                mock.patch("hst_office.office_proxy.proxy", lambda ctx: {"https": "proxy.lan:3128"}):
            settings = citation_lookup_action.config(None)
        self.assertEqual((False, {"https": "proxy.lan:3128"}), (settings.enabled, settings.proxy))
        self.assertEqual(citation_lookup.DEFAULT_CONTACT, settings.contact)
        self.assertEqual("/org.hasontech.hstoffice.Citations/OnlineLookup", citation_lookup_action.KEY)
        schema = XCS.read_text(encoding="utf-8")
        self.assertRegex(schema, r'oor:name="OnlineLookup" oor:type="xs:boolean"[^>]*>\s*<info>[\s\S]*?'
                                 r'<value>true</value>')

    def test_only_the_lookup_action_calls_the_network_and_only_the_form_calls_it(self):
        callers, actions = set(), set()
        for path in PYTHON.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            if re.search(r"citation_lookup\.(lookup|lookup_reference|http_transport)\(", source):
                callers.add(path.name)
            if re.search(r"lookup_action\.(lookup|lookup_line)\b|citation_lookup_action import", source):
                actions.add(path.name)
        self.assertEqual({"citation_lookup_action.py"}, callers)
        self.assertEqual({"citation_entry_dialog.py"}, actions)


if __name__ == "__main__":
    unittest.main()
