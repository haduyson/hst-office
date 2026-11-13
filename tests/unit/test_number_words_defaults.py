# SPDX-License-Identifier: AGPL-3.0-only
"""Defaults of number and money reading: file > user > program for the dialog, file > program for DOCSO()/DOCTIEN()
with an argument left out, the shortest formula the dialog may write, the user default (profile, options page)."""
import os
import re
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import _paths  # noqa: F401

from hst_office import number_words as nw
from hst_office import number_words_defaults as defaults
from hst_office import number_words_prefs as prefs
from hst_office.number_words_choice import formula

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
OOR = "{http://openoffice.org/2001/registry}"
DLG = "{http://openoffice.org/2000/dialog}"
USER = {"money": True, "formula": True, "unit": "dollar", "sub_unit": "cent", "money_options": "en",
        "number_options": "ngàn linh"}
FILE = {"unit": "đồng", "sub_unit": "xu", "money_options": "tư", "number_options": "linh"}


def choice(money=False, unit="đồng", sub="", options=""):
    return {"money": money, "unit": unit, "sub_unit": sub, "options": nw.parse_options(options)}


class Resolve(unittest.TestCase):
    def test_program_default_is_dong_without_xu(self):
        self.assertEqual(defaults.resolve(), defaults.DEFAULTS)
        self.assertEqual(defaults.resolve(None, None), defaults.DEFAULTS)
        self.assertEqual((defaults.DEFAULTS["unit"], defaults.DEFAULTS["sub_unit"]), ("đồng", ""))

    def test_file_beats_user_beats_program(self):
        self.assertEqual(defaults.resolve(None, USER), USER)
        self.assertEqual(defaults.resolve(FILE, USER), dict(USER, **FILE))
        self.assertEqual(defaults.resolve({"number_options": ""}, USER)["number_options"], "")  # "" is a default too

    def test_a_unit_keeps_its_own_sub_unit(self):
        values = defaults.resolve({"unit": "USD"}, {"unit": "đồng", "sub_unit": "xu"})
        self.assertEqual((values["unit"], values["sub_unit"]), ("USD", ""))
        values = defaults.resolve({"sub_unit": "cent"}, {"unit": "đồng", "sub_unit": "xu"})
        self.assertEqual((values["unit"], values["sub_unit"]), ("đồng", "xu"))

    def test_damaged_layers_fall_back_per_entry(self):
        raw = {"money": "yes", "unit": "x" * 41, "sub_unit": "cent", "number_options": "sai", "formula": 1,
               "money_options": "LINH  Tiếng Anh"}
        self.assertEqual(defaults.resolve(raw), dict(defaults.DEFAULTS, money_options="linh en"))
        self.assertEqual(defaults.resolve({"unit": "a\nb"})["unit"], "đồng")
        self.assertEqual(defaults.resolve("garbage", ["x"]), defaults.DEFAULTS)

    def test_option_indexes_round_trip(self):
        self.assertEqual(defaults.option_indexes("ngàn tư en"), {"thousand": 1, "odd": 0, "four": 1, "language": 1})
        self.assertEqual(defaults.option_indexes("sai"), {"thousand": 0, "odd": 0, "four": 0, "language": 0})
        self.assertEqual(defaults.options_text({"thousand": 1, "odd": 1, "four": 0, "language": 9}), "ngàn linh")


class FunctionArguments(unittest.TestCase):
    """What DOCSO/DOCTIEN read for an argument left out (None): the file's default, never the user's."""

    def test_docso(self):
        self.assertEqual(defaults.number_args(None, None).text(), "")
        self.assertEqual(defaults.number_args(FILE, None).text(), "linh")
        self.assertEqual(defaults.number_args(FILE, "ngàn").text(), "ngàn")  # written: wins entirely
        self.assertEqual(defaults.number_args(FILE, "").text(), "")
        with self.assertRaises(nw.NumberWordsError):
            defaults.number_args(None, "sai")

    def test_doctien(self):
        def args(layer, *given):
            unit, sub_unit, options = defaults.money_args(layer, *given)
            return unit, sub_unit, options.text()
        self.assertEqual(args(None, None, None, None), ("đồng", "", ""))
        self.assertEqual(args(None, None, None, "en"), ("dollar", "cent", "en"))
        self.assertEqual(args(FILE, None, None, None), ("đồng", "xu", "tư"))
        self.assertEqual(args(FILE, "USD", None, None), ("USD", "", "tư"))  # the file's xu never joins USD
        self.assertEqual(args(FILE, None, "", None), ("đồng", "", "tư"))
        self.assertEqual(args(FILE, None, None, ""), ("đồng", "xu", ""))
        self.assertEqual(args({"money_options": "bad"}, None, None, None), ("đồng", "", ""))
        self.assertEqual(nw.read_money(1000.5, *defaults.money_args(FILE, None, None, None)),
                         "Một nghìn đồng năm mươi xu")

    def test_formula_is_the_shortest_that_reads_the_same(self):
        self.assertEqual(formula(choice(), "A1"), "=DOCSO(A1)")
        self.assertEqual(formula(choice(), "A1", FILE), '=DOCSO(A1;"")')
        self.assertEqual(formula(choice(options="linh"), "A1", FILE), "=DOCSO(A1)")
        self.assertEqual(formula(choice(True, "đồng", "xu", "tư"), "A1", FILE), "=DOCTIEN(A1)")
        self.assertEqual(formula(choice(True, "đồng", "xu"), "A1", FILE), '=DOCTIEN(A1;"đồng";"xu";"")')
        self.assertEqual(formula(choice(True), "A1", FILE), '=DOCTIEN(A1;"đồng";"";"")')
        self.assertEqual(formula(choice(True), "A1"), "=DOCTIEN(A1)")
        self.assertEqual(formula(choice(True, "đồng", "xu", "tư"), "A1"), '=DOCTIEN(A1;"đồng";"xu";"tư")')


class UserDefault(unittest.TestCase):
    def test_from_choice_updates_the_kind_it_read(self):
        accepted = dict(choice(True, "dollar", "cent", "en"), formula=True)
        self.assertEqual(prefs.from_choice(accepted, True), {"money": True, "unit": "dollar", "sub_unit": "cent",
                                                             "money_options": "en", "formula": True})
        number = dict(choice(options="ngàn"), formula=False)
        self.assertNotIn("formula", prefs.from_choice(number, False))  # Writer has no text/formula choice
        self.assertEqual(prefs.from_choice(number, False)["number_options"], "ngàn")

    def test_load_and_save_use_the_profile_node(self):
        stored = {prefs.KEYS[key]: value for key, value in USER.items()}
        node = mock.Mock(getPropertyValue=stored.__getitem__)
        with mock.patch.object(prefs, "_access", return_value=node):
            self.assertEqual(prefs.load(None), USER)
            self.assertTrue(prefs.save(None, {"number_options": "tư", "unit": "", "money": "bad"}))
        self.assertEqual([c.args for c in node.setPropertyValue.call_args_list], [("NumberOptions", "tư")])
        node.commitChanges.assert_called_once()

    def test_unreadable_profile_gives_program_default(self):
        with mock.patch.object(prefs, "_access", side_effect=RuntimeError("no schema")), \
                mock.patch.object(prefs.diag_log, "exception"):
            self.assertEqual(prefs.load(None), defaults.DEFAULTS)
            self.assertFalse(prefs.save(None, USER))

    def test_schema_matches_the_keys_and_program_default(self):
        root = ET.parse(os.path.join(EXT, "numberwords.xcs")).getroot()
        self.assertEqual("/%s.%s" % (root.get(OOR + "package"), root.get(OOR + "name")), prefs.CONFIG_PATH)
        stored = {p.get(OOR + "name"): p.findtext("value") or "" for p in root.iter("prop")}
        expected = {name: str(defaults.DEFAULTS[key]).lower() if isinstance(defaults.DEFAULTS[key], bool)
                    else defaults.DEFAULTS[key] for key, name in prefs.KEYS.items()}
        self.assertEqual(stored, expected)
        with open(os.path.join(EXT, "META-INF", "manifest.xml"), encoding="utf-8") as manifest:
            self.assertIn('full-path="numberwords.xcs"', manifest.read())


class OptionsPageAndAddIn(unittest.TestCase):
    def test_page_registered_with_every_list(self):
        from hst_office import number_words_options as page
        root = ET.parse(os.path.join(EXT, "OptionsDialog.xcu")).getroot()
        leaf = next(n for n in root.iter("node") if n.get(OOR + "name") == "vn.hasontech.hstoffice.Options.NumberWords")
        props = {p.get(OOR + "name"): p.find("value").text for p in leaf.findall("prop")}
        self.assertEqual((props["Label"], props["EventHandlerService"]), ("Đọc số và tiền", page.HANDLER_NAME))
        ids = {e.get(DLG + "id") for e in ET.parse(os.path.join(EXT, "dialogs", "NumberWords.xdl")).getroot().iter()}
        wanted = {"%s_%s" % (prefix, key) for prefix in page.COLUMNS for key in defaults.CHOICES}
        self.assertLessEqual(wanted | {"m_unit", "m_sub"}, ids)
        self.assertEqual(page.page_layer({"n": {"thousand": 1}, "m": {"language": 1}}, " USD ", " cent "),
                         {"number_options": "ngàn", "money_options": "en", "unit": "USD", "sub_unit": "cent"})

    def test_docso_doctien_take_the_hidden_caller_first(self):
        with open(os.path.join(EXT, "idl", "XCalcFunctions.idl"), encoding="utf-8") as idl:
            text = idl.read()
        for name in ("docso", "doctien"):
            first = re.search(r"string\s+%s\s*\(\s*\[in\]\s+([\w:]+)\s+(\w+)" % name, text)
            self.assertEqual(first.groups(), ("com::sun::star::beans::XPropertySet", "Document"))


if __name__ == "__main__":
    unittest.main()
