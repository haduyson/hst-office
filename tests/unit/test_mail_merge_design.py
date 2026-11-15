# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư design features without UNO: the Vietnamese address block and greeting, the rules (Nếu…Thì…Khác,
Bỏ qua bản ghi nếu, Hỏi, Đặt số thứ tự) as computed staging columns, Kiểm tra lỗi, the ▾ menu items, the list
editor's column parsing, the vi/en texts and the handler's command table."""
import sys
import types
import unittest

import _paths  # noqa: F401

from hst_office import mail_merge_address as address
from hst_office import mail_merge_check as check
from hst_office import mail_merge_format as fmt
from hst_office import mail_merge_rules as rules
from hst_office import mail_merge_table as mt
from hst_office import mail_merge_texts as texts

HEADERS = ["Danh xưng", "Họ và tên", "Chức vụ", "Đơn vị", "Địa chỉ", "Giới tính", "Số tiền", "Email"]
KINDS = ["text"] * 6 + ["number", "text"]
ROWS = [("", "Nguyễn Văn An", "Trưởng phòng", "Phòng Kế toán", "12 Lê Lợi, Huế", "Nam", 1500000.0, "an@example.vn"),
        ("Chị", "Trần Thị Bích Ngọc", "Nhân viên", None, None, "Nữ", 250000.0, "ngoc-at-example"),
        ("", "Lê Hoàng Ánh", None, "Ban Giám đốc", None, "", 9800000.0, "anh@example.vn")]


def table():
    return mt.Table(HEADERS, KINDS, ROWS)


def stub_uno():
    for name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.frame", "com.sun.star.lang",
                 "com.sun.star.awt"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["unohelper"].Base = type("Base", (), {})
    for module, names in (("com.sun.star.frame", ("XDispatch", "XDispatchProvider", "XPopupMenuController")),
                          ("com.sun.star.lang", ("XInitialization", "XServiceInfo")),
                          ("com.sun.star.awt", ("XMenuListener", "XTextListener", "XActionListener", "XItemListener"))):
        for name in names:
            setattr(sys.modules[module], name, type(name, (), {}))


class Address(unittest.TestCase):
    def test_roles_from_vietnamese_headers(self):
        roles = address.guess_roles(HEADERS)
        self.assertEqual((roles["title"], roles["name"], roles["unit"], roles["address"]),
                         ("Danh xưng", "Họ và tên", "Đơn vị", "Địa chỉ"))

    def test_block_in_vietnamese_order_without_empty_lines(self):
        t = table()
        conf = address.settings({}, t.headers, address.BLOCK_DEFAULT)
        self.assertEqual(address.address_block(t, t.rows[0], conf),
                         "Kính gửi: Ông Nguyễn Văn An\nTrưởng phòng\nPhòng Kế toán\n12 Lê Lợi, Huế")
        self.assertEqual(address.address_block(t, t.rows[1], conf), "Kính gửi: Chị Trần Thị Bích Ngọc\nNhân viên")
        conf["one_line"] = True
        self.assertEqual(address.address_block(t, t.rows[0], conf).split("\n")[1], "Trưởng phòng, Phòng Kế toán")

    def test_greeting_by_given_name_and_gender(self):
        t = table()
        conf = address.settings({}, t.headers, address.GREETING_DEFAULT)
        self.assertEqual(address.greeting(t, t.rows[0], conf), "Kính gửi ông An,")
        self.assertEqual(address.greeting(t, t.rows[1], conf), "Kính gửi chị Ngọc,")  # the title column wins
        self.assertEqual(address.greeting(t, t.rows[2], conf), "Kính gửi ông/bà Ánh,")  # ông before bà (owner)
        nameless = mt.Table(["Họ và tên"], ["text"], [("",)])
        self.assertEqual(address.greeting(nameless, nameless.rows[0], address.settings({}, ["Họ và tên"],
                                                                                         address.GREETING_DEFAULT)),
                         "Kính gửi ông/bà,")
        conf.update(given=False, capital=True, style="friendly", opening="Thân gửi", ending="")
        self.assertEqual(address.greeting(t, t.rows[0], conf), "Thân gửi Anh Nguyễn Văn An")

    def test_unknown_columns_are_dropped(self):
        conf = address.settings({"name": "Không có", "lead": 5}, HEADERS, address.BLOCK_DEFAULT)
        self.assertEqual((conf["name"], conf["lead"]), ("", "Kính gửi:"))


class Rules(unittest.TestCase):
    def test_conditions(self):
        t = table()
        self.assertTrue(rules.matches(t, t.rows[1], {"column": "Giới tính", "op": "eq", "value": "nu"}))
        self.assertTrue(rules.matches(t, t.rows[1], {"column": "Đơn vị", "op": "empty"}))
        self.assertTrue(rules.matches(t, t.rows[0], {"column": "Số tiền", "op": "gt", "value": "1.000.000"}))
        self.assertFalse(rules.matches(t, t.rows[1], {"column": "Số tiền", "op": "gt", "value": "1.000.000"}))
        self.assertTrue(rules.matches(t, t.rows[0], {"column": "Đơn vị", "op": "contains", "value": "ke toan"}))
        self.assertFalse(rules.matches(t, t.rows[0], {"column": "Không có", "op": "empty"}))

    def test_computed_columns_in_staging(self):
        t = table()
        meta = {"rules": [{"type": "if", "name": "Mời", "column": "Giới tính", "op": "eq", "value": "Nam",
                           "then": "Kính mời anh {Họ và tên}", "else": "Kính mời chị {Họ và tên}"},
                          {"type": "ask", "name": "Ngày họp", "prompt": "?", "value": "20/11/2026"},
                          {"type": "seq", "name": "Số thứ tự", "start": 5}, {"type": "bad"}]}
        headers, _kinds, rows = mt.staging(t, [1, 0], extra=rules.extra_columns(meta, t))
        get = dict(zip(headers, rows[0]))
        self.assertEqual(get["Nếu: Mời"], "Kính mời chị Trần Thị Bích Ngọc")
        self.assertEqual((get["Hỏi: Ngày họp"], get["Số thứ tự"]), ("20/11/2026", "5"))
        self.assertEqual(dict(zip(headers, rows[1]))["Số thứ tự"], "6")
        self.assertEqual(get[rules.GREETING_COLUMN], "Kính gửi chị Ngọc,")
        self.assertEqual(headers[-1], mt.FILE_COLUMN)

    def test_computed_name_avoids_a_header(self):
        self.assertEqual(mt.computed_name("Dòng chào", ["Dòng chào"]), "Dòng chào (HST)")
        self.assertNotIn(mt.FILE_COLUMN, mt.insertable(["A", "A (bằng chữ)", mt.FILE_COLUMN]))

    def test_upsert_replaces_same_name(self):
        merged = rules.upsert([{"type": "ask", "name": "X", "value": "1"}], {"type": "ask", "name": "X", "value": "2"})
        self.assertEqual(merged, [{"type": "ask", "name": "X", "value": "2"}])


class Check(unittest.TestCase):
    def test_problems(self):
        t = table()
        found = check.problems(t, ["Họ và tên", "Đơn vị", "Không có", "Số tiền (bằng chữ)"], "Email", ["A", "B", "a"])
        codes = [(code, position) for code, position, _c, _v in found]
        self.assertIn(("missing-column", 0), codes)
        self.assertIn(("empty", 2), codes)
        self.assertIn(("bad-mail", 2), codes)
        self.assertIn(("same-file", 3), codes)
        self.assertNotIn(("empty", 1), codes)

    def test_no_recipient_and_no_field(self):
        self.assertEqual(check.problems(mt.Table(["A"], ["text"], []), ["A"]), [("no-recipient", 0, "", "")])
        self.assertEqual(check.problems(table(), [])[0][0], "no-field")

    def test_lines_are_readable(self):
        found = [("empty", 2, "Đơn vị", ""), ("missing-column", 0, "X", "")]
        lines = check.lines(found, texts.VI, lambda position: "Ngọc")
        self.assertEqual(lines, ["Người 2 (Ngọc): trường «Đơn vị» trống", "Cả văn bản: trường «X» không có trong danh sách"])


class MenusAndTexts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stub_uno()
        from hst_office import mail_merge_handler, mail_merge_list_editor, mail_merge_menu
        cls.handler, cls.editor, cls.menu = mail_merge_handler, mail_merge_list_editor, mail_merge_menu

    def test_menu_items(self):
        start = self.menu.menu_items("Start", texts.VI, doc_type="email")
        self.assertEqual([i[0] for i in start][-1], "Wizard")
        self.assertEqual([i[3] for i in start if i[0] == "StartEmail"], [True])
        fields = self.menu.menu_items("InsertField", texts.VI, ["Họ và tên"])
        self.assertEqual(fields[0][:3], ("InsertColumn", "Họ và tên", {"Column": "Họ và tên"}))
        self.assertEqual(fields[-1][0], "FieldFormat")
        self.assertEqual(self.menu.menu_items("InsertField", texts.VI)[0][0], "")

    def test_every_menu_item_is_a_command(self):
        for items in self.menu.MENUS.values():
            for command, key in items:
                self.assertIn(command, self.handler.COMMANDS)
                self.assertIn(key, texts.VI)

    def test_list_editor_columns(self):
        self.assertEqual(self.editor.parse_columns(" Họ và tên ;Đơn vị,, Họ và tên; ;Email"), ["Họ và tên", "Đơn vị", "Email"])
        self.assertEqual(len(self.editor.parse_columns(";".join("C%d" % i for i in range(12)))), self.editor.MAX_COLUMNS)

    def test_vi_and_en_texts_match(self):
        self.assertEqual(set(texts.VI), set(texts.EN))
        for key in texts.VI:
            self.assertEqual(texts.VI[key].count("%("), texts.EN[key].count("%("), key)
        for op in rules.OPS:
            self.assertIn("op." + op, texts.VI)
        joined = " ".join(texts.VI.values()).lower()
        self.assertNotIn("phối thư", joined)
        self.assertNotIn("bà/ông", joined.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
