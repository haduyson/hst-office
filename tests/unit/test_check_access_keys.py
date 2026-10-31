# SPDX-License-Identifier: AGPL-3.0-only
"""Static access-key modeling against small source/translation fixtures."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_access_keys", ROOT / "scripts/l10n/check-access-keys.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
UI = MOD.UI_PO
WRITER = "sw/uiconfig/swriter/"


def xcu(commands="", popups=""):
    return (f'<oor:component-data xmlns:oor="{MOD.OOR[1:-1]}" oor:name="GenericCommands">'
            f'<node oor:name="UserInterface"><node oor:name="Commands">{commands}</node>'
            f'<node oor:name="Popups">{popups}</node></node></oor:component-data>')


def command(name, **props):
    return (f'<node oor:name=".uno:{name}">' + "".join(
        f'<prop oor:name="{k}"><value xml:lang="en-US">{v}</value></prop>' for k, v in props.items()) + '</node>')


def ctx(name, prop="Label", section="Commands", config="GenericCommands"):
    return f"{config}.xcu\n..{config}.UserInterface.{section}..uno:{name}\n{prop}\nvalue.text"


def tab(name, label, styles="", controls=""):
    return (f'<child><object class="GtkBox" id="{name}Page">{controls}</object></child>'
            f'<child type="tab"><object class="GtkLabel" id="{name}">'
            f'<property name="label" translatable="yes" context="Tabs|{name}">{label}</property>'
            '<style>' + "".join(f'<class name="context-{s}"/>' for s in styles.split()) + '</style>'
            '</object></child>')


class AccessKeysTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tree = self.base / "tree"
        self.snapshot = self.base / "snapshot.json"
        self.overrides = self.base / "overrides.jsonl"
        self.overrides.write_text("", encoding="utf-8")
        self.exceptions = self.base / "exceptions.json"
        self.addons = self.base / "Addons.xcu"
        self.addons.write_text(f'''<oor:component-data xmlns:oor="{MOD.OOR[1:-1]}">
          <node oor:name="AddonUI"><node oor:name="OfficeMenuBar"><node oor:name="hst">
            <prop oor:name="Title"><value xml:lang="en-US">HST</value><value xml:lang="vi">HST</value></prop>
            <node oor:name="Submenu">
              <node oor:name="writer"><prop oor:name="Title"><value xml:lang="vi">Không dấu</value></prop>
                <prop oor:name="Context"><value>com.sun.star.text.TextDocument</value></prop></node>
              <node oor:name="calc"><prop oor:name="Title"><value xml:lang="vi">~Không được thêm</value></prop>
                <prop oor:name="Context"><value>com.sun.star.sheet.SpreadsheetDocument</value></prop></node>
            </node></node></node>
            <node oor:name="OfficeHelp"><node oor:name="update">
              <prop oor:name="Title"><value xml:lang="vi">Cập nhật</value></prop>
            </node></node></node></oor:component-data>''', encoding="utf-8")
        self.write(WRITER + "menubar/menubar.xml", f'''<menu:menubar xmlns:menu="{MOD.MENU[1:-1]}">
          <menu:menu menu:id=".uno:File"><menu:menupopup>
            <menu:menuitem menu:id=".uno:Open"/><menu:menuseparator/>
            <menu:menuitem menu:id=".uno:Save"/><menu:menuitem menu:id=".uno:Auto"/>
          </menu:menupopup></menu:menu>
          <menu:menu menu:id=".uno:HelpMenu"><menu:menupopup/></menu:menu>
        </menu:menubar>''')
        self.config = "officecfg/registry/data/org/openoffice/Office/UI/GenericCommands.xcu"
        self.commands = command("Open", Label="~Open") + command("Save", Label="~Save") + command("Auto", Label="Auto")
        self.popups = command("File", Label="~File") + command("HelpMenu", Label="~Help")
        self.write(self.config, xcu(self.commands, self.popups))
        self.po(UI, [(ctx("Open"), "~Open", "~Mở"), (ctx("Save"), "~Save", "~Mới")])
        self.po("sw/messages.po", [])
        self.notebook(tab("Home", "~Home", "default any Text") + tab("Table", "~Table", "Table"))

    def write(self, rel, text):
        path = self.tree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def po(self, file, rows):
        self.write("translations/source/vi/" + file, "\n\n".join(
            "\n".join(f'{key} "{MOD.escape(value)}"' for key, value in zip(("msgctxt", "msgid", "msgstr"), row))
            for row in rows))

    def notebook(self, tabs, menus=""):
        self.write(WRITER + "ui/notebookbar.ui", f'<interface>{menus}<object class="sfxlo-NotebookbarTabControl" id="tabs">{tabs}</object></interface>')

    def model(self):
        return MOD.merge_addons(MOD.build_model(self.tree), self.addons)

    def check(self):
        return MOD.check(self.model(), MOD.load_overrides(self.overrides))

    def override(self, context, msgid, msgstr, **extra):
        row = dict(file=UI, msgctxt=MOD.escape(context), msgid=MOD.escape(msgid),
                   msgstr=MOD.escape(msgstr), reason="fixture", **extra)
        self.overrides.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    def test_duplicate_and_override(self):
        result = self.check()
        self.assertEqual(result["strict_problems"], 1)
        problem = result["problems"][0]
        self.assertEqual((problem["container"], problem["key"]), ("Writer > File", "M"))
        self.override(ctx("Save"), "~Save", "~Lưu")
        self.assertEqual(self.check()["strict_problems"], 0)

    def test_non_ascii_includes_punctuation_and_unicode_case_expansion(self):
        for char in ("Đ", "ư", "Ơ", "ê", "Â", "Ă", "Ô", "ấ", "!", "ß", "ſ", "１"):
            with self.subTest(char=char):
                self.override(ctx("Save"), "~Save", "~" + char)
                problems = self.check()["problems"]
                self.assertEqual(len(problems), 1)
                self.assertEqual(problems[0]["kind"], "non-ascii")
                self.assertTrue(problems[0]["strict"])

    def test_ascii_digits_are_typable_and_keys_are_case_insensitive(self):
        for char in "0123456789":
            self.override(ctx("Save"), "~Save", "~" + char)
            self.assertEqual(self.check()["problems"], [])
        self.po(UI, [(ctx("Open"), "~Open", "~1"), (ctx("Save"), "~Save", "~1")])
        self.overrides.write_text("", encoding="utf-8")
        self.assertEqual(self.check()["problems"][0]["key"], "1")
        self.po(UI, [(ctx("Open"), "~Open", "~m"), (ctx("Save"), "~Save", "~M")])
        self.assertEqual(self.check()["problems"][0]["key"], "M")

    def test_exception_matches_exact_collision_and_stale_fails_strict(self):
        MOD.load_model(self.tree, self.snapshot, True, self.addons)
        entry = dict(container="Writer > File", key="M", labels=["~Mới", "~Mở"],
                     reason="needs native reviewer: fixture")
        self.exceptions.write_text(json.dumps([entry]), encoding="utf-8")
        args = ["--tree", str(self.base / "absent"), "--snapshot", str(self.snapshot),
                "--overrides", str(self.overrides), "--exceptions", str(self.exceptions)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MOD.main(args + ["--strict"]), 0)
            for replacement in (dict(labels=["~Mở", "~Mở"]), dict(key="N"),
                                dict(container="Calc > File")):
                self.exceptions.write_text(json.dumps([dict(entry, **replacement)]), encoding="utf-8")
                self.assertEqual(MOD.main(args + ["--strict"]), 1)
            self.exceptions.write_text(json.dumps([entry]), encoding="utf-8")
            self.override(ctx("Save"), "~Save", "~Lưu")
            self.assertEqual(MOD.main(args), 0)
            self.assertEqual(MOD.main(args + ["--strict"]), 1)
        stale = MOD.check(self.model(), MOD.load_overrides(self.overrides), [entry])
        self.assertEqual(stale["stale_exceptions"], [entry])

    def test_invalid_and_duplicate_exceptions_are_rejected(self):
        self.assertEqual(MOD.load_exceptions(self.exceptions), [])
        entry = dict(container="Writer > File", key="M", labels=["~Mở", "~Mới"], reason="review")
        for value in ({}, [dict(entry, reason="")], [dict(entry, key="m")],
                      [dict(entry, labels="~Mở")], [dict(entry, labels=["~Mở"])],
                      [dict(entry, kind="unknown")], [dict(entry, kind="non-ascii")],
                      [dict(entry, kind="non-ascii", labels=[])],
                      [entry, dict(entry, kind="collision")],
                      [entry, dict(entry, labels=entry["labels"][::-1])]):
            self.exceptions.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                MOD.load_exceptions(self.exceptions)

    def test_non_ascii_exception_matches_exact_problem_and_stale_fails_strict(self):
        MOD.load_model(self.tree, self.snapshot, True, self.addons)
        self.override(ctx("Save"), "~Save", "~Ô")
        entry = dict(container="Writer > File", kind="non-ascii", key="Ô", labels=["~Ô"],
                     reason="needs native reviewer: one-letter label Ô has no ASCII letter")
        self.exceptions.write_text(json.dumps([entry]), encoding="utf-8")
        exceptions = MOD.load_exceptions(self.exceptions)
        result = MOD.check(self.model(), MOD.load_overrides(self.overrides), exceptions)
        self.assertEqual(result["strict_problems"], 0)
        self.assertEqual(result["stale_exceptions"], [])
        self.assertEqual(result["problems"][0]["exception"], entry["reason"])
        self.assertEqual(result["summary"]["Writer menus"]["non-ascii"], 1)
        args = ["--tree", str(self.base / "absent"), "--snapshot", str(self.snapshot),
                "--overrides", str(self.overrides), "--exceptions", str(self.exceptions), "--strict"]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(MOD.main(args), 0)
        self.assertIn("Excepted problems: 1", stdout.getvalue())
        for replacement in (dict(labels=["Ô~"]), dict(key="Ơ"), dict(container="Calc > File")):
            with self.subTest(replacement=replacement):
                changed = dict(entry, **replacement)
                result = MOD.check(self.model(), MOD.load_overrides(self.overrides), [changed])
                self.assertEqual(result["stale_exceptions"], [changed])
                self.assertEqual(result["strict_problems"], 2)
                self.exceptions.write_text(json.dumps([changed]), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(MOD.main(args), 1)
        self.exceptions.write_text(json.dumps([entry]), encoding="utf-8")
        self.override(ctx("Save"), "~Save", "~Lưu")
        result = MOD.check(self.model(), MOD.load_overrides(self.overrides), exceptions)
        self.assertEqual(result["stale_exceptions"], [entry])
        self.assertEqual(result["strict_problems"], 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MOD.main(args), 1)

    def test_automatic_addon_titles_and_context_filter(self):
        model = self.model()
        hst = next(c for c in model["containers"] if c["path"] == "Writer > HST")
        self.assertEqual([i["id"] for i in hst["items"]], ["writer"])
        info = self.check()["info"]
        self.assertTrue(any(i["label"] == "Không dấu" and i["kind"] == "auto" for i in info))
        self.assertTrue(any(i["container"] == "Writer > Help" and i["label"] == "Cập nhật" for i in info))
        self.assertFalse(any("HST" in p["container"] for p in self.check()["problems"]))

    def test_escaped_markers_and_only_first_explicit_mnemonic(self):
        for text, markers, expected in (("~~A", "~", ""), ("~~~b", "~", "b"),
                                        ("__A _B", "~_", "B"), ("~A ~B", "~", "A"),
                                        ("lone~", "~", ""), ("_A", "~", "")):
            self.assertEqual(MOD.mnemonic(text, markers), expected)

    def test_contextual_tabs(self):
        self.notebook(tab("Home", "~H", "default any Text") + tab("Table", "~T", "Table") + tab("Draw", "~T", "Draw"))
        tabs = [p for p in self.check()["problems"] if p["type"] == "tab-bars"]
        self.assertEqual(len(tabs), 1)
        self.assertFalse(tabs[0]["strict"])
        self.po("sw/messages.po", [("Tabs|Home", "~H", "~T")])
        tabs = [p for p in self.check()["problems"] if p["type"] == "tab-bars"]
        self.assertTrue(tabs[0]["strict"])
        self.po("sw/messages.po", [("Tabs|Table", "~T", "~Đ")])
        self.assertTrue(any(p["kind"] == "non-ascii" and p["strict"] for p in self.check()["problems"]))

    def test_tabs_without_context_classes_are_always_visible(self):
        self.notebook(tab("Layout", "~Bố trí") + tab("Table", "~Bảng", "Table")
                      + tab("Object", "Đối tượn~g", "Frame OLE"))
        result = self.check()
        tabs = [p for p in result["problems"] if p["type"] == "tab-bars"]
        self.assertEqual([(p["key"], p["strict"]) for p in tabs], [("B", True)])
        self.po("sw/messages.po", [("Tabs|Table", "~Bảng", "Bản~g")])
        tabs = [p for p in self.check()["problems"] if p["type"] == "tab-bars"]
        self.assertEqual([(p["key"], p["strict"]) for p in tabs], [("G", False)])

    def test_context_label_module_precedence_and_both_nodes(self):
        self.write("officecfg/registry/data/org/openoffice/Office/UI/WriterCommands.xcu",
                   xcu(command("Open", Label="~Long", ContextLabel="~Short", PopupLabel="~Popup"),
                       command("Open", Label="~Wrong")))
        self.po(UI, [(ctx("Open", "ContextLabel", config="WriterCommands"), "~Short", "~Ngắn")])
        items = next(c["items"] for c in self.model()["containers"] if c["path"] == "Writer > File")
        item = next(i for i in items if i["id"] == ".uno:Open")
        self.assertEqual(MOD.resolve(item, {})[0], "~Ngắn")
        self.override(ctx("Open", "ContextLabel", config="WriterCommands"), "~Short", "~Xem")
        self.assertEqual(MOD.resolve(item, MOD.load_overrides(self.overrides))[0], "~Xem")

    def test_empty_and_fuzzy_translations_fall_back_to_english(self):
        self.po(UI, [(ctx("Open"), "~Open", ""), (ctx("Save"), "~Save", "~Mới")])
        self.assertEqual(self.check()["strict_problems"], 0)
        path = self.tree / "translations/source/vi" / UI
        self.po(UI, [(ctx("Open"), "~Open", "~Mở")])
        path.write_text("#, fuzzy\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.check()["strict_problems"], 0)
        self.override(ctx("Open"), "~Open", "~Đọc")
        self.assertEqual(self.check()["strict_problems"], 1)

    def test_override_new_msgid_and_po_escaping(self):
        self.override(ctx("Save"), "Old save", '~Lưu "tệp"', msgid_new="~Save")
        result = self.check()
        self.assertEqual(result["strict_problems"], 0)
        self.assertEqual(MOD.unescape(MOD.escape('Việt "tệp" \\n\n')), 'Việt "tệp" \\n\n')

    def test_explicit_menu_label_and_container_boundaries(self):
        path = self.tree / (WRITER + "menubar/menubar.xml")
        path.write_text(path.read_text().replace('menu:id=".uno:Save"', 'menu:id=".uno:Save" menu:label="~S"'), encoding="utf-8")
        self.assertEqual(self.check()["strict_problems"], 0)

    def test_nested_popups_are_independent(self):
        self.write(WRITER + "menubar/menubar.xml", f'''<menu:menubar xmlns:menu="{MOD.MENU[1:-1]}">
          <menu:menu menu:id=".uno:File"><menu:menupopup>
            <menu:menu menu:id="first" menu:label="~A"><menu:menupopup>
              <menu:menuitem menu:id="one" menu:label="~N"/>
            </menu:menupopup></menu:menu>
            <menu:menu menu:id="second" menu:label="~B"><menu:menupopup>
              <menu:menuitem menu:id="two" menu:label="~N"/>
            </menu:menupopup></menu:menu>
          </menu:menupopup></menu:menu></menu:menubar>''')
        self.assertEqual(self.check()["strict_problems"], 0)
        paths = {c["path"] for c in self.model()["containers"]}
        self.assertTrue({"Writer > File > A", "Writer > File > B"} <= paths)

    def test_help_addons_identified_by_command_not_english_title(self):
        self.write(self.config, xcu(self.commands, self.popups.replace("~Help", "~Assistance")))
        self.assertTrue(any(i["container"] == "Writer > Assistance" and i["label"] == "Cập nhật"
                            for i in self.check()["info"]))

    def test_module_command_does_not_inherit_generic_properties(self):
        self.write("officecfg/registry/data/org/openoffice/Office/UI/WriterCommands.xcu", xcu(command("Open", PopupLabel="~Popup")))
        items = {i["id"]: i for c in self.model()["containers"] for i in c["items"]}
        self.assertEqual(MOD.resolve(items[".uno:Open"], {})[0], "")

    def test_ui_override_can_add_mnemonic_without_changing_snapshot_structure(self):
        self.notebook(tab("Home", "Home") + tab("Other", "~H"))
        model = self.model()
        self.assertFalse(any(p["type"] == "tab-bars" for p in MOD.check(model, {})["problems"]))
        overrides = {("sw/messages.po", "Tabs|Home", "Home"): "~Home"}
        self.assertTrue(any(p["type"] == "tab-bars" and p["strict"]
                            for p in MOD.check(model, overrides)["problems"]))

    def test_controls_and_separate_popup_containers(self):
        controls = '''<child><object class="GtkButton" id="one"><property name="label" translatable="yes" context="one">_A</property></object></child>
          <child><object class="GtkButton" id="two"><property name="label" translatable="yes" context="two">_Again</property></object></child>
          <child><object class="GtkButton" id="unicode"><property name="label" translatable="yes" context="unicode">_Đọc</property></object></child>
          <child><object class="GtkToolButton" id="tool"><property name="action-name">.uno:Open</property><property name="label">~A ignored</property></object></child>'''
        menu = '''<object class="GtkMenu" id="popup"><child><object class="GtkMenuItem" id="item"><property name="label">_A</property></object></child></object>'''
        self.notebook(tab("Home", "~Home", controls=controls), menu)
        warnings = [p for p in self.check()["problems"] if p["type"] == "controls"]
        self.assertEqual([p["kind"] for p in warnings], ["non-ascii", "collision"])
        self.assertTrue(all(not p["strict"] for p in warnings))
        self.assertEqual(len(warnings[1]["items"]), 2)
        items = next(c["items"] for c in self.model()["containers"] if c["path"] == "Writer > Ribbon > Home")
        self.assertEqual(MOD.resolve(next(i for i in items if i["id"] == "tool"), {}), ("Mở", ""))

    def test_popup_uses_popup_label_and_tool_falls_back_to_ui(self):
        self.write(self.config, xcu(self.commands + command("Popup", Label="~Long", ContextLabel="~Short", PopupLabel="~Popup"), self.popups))
        self.notebook(tab("Home", "~Home", controls='''<child><object class="GtkToolButton" id="extension"><property name="action-name">hst:Unknown</property><property name="label">~HST</property></object></child>'''),
                      '''<object class="GtkMenu" id="popup"><child><object class="GtkMenuItem" id="item"><property name="action-name">.uno:Popup</property></object></child></object>''')
        items = {i["id"]: i for c in self.model()["containers"] for i in c["items"]}
        self.assertEqual(MOD.resolve(items["item"], {})[0], "~Popup")
        self.assertEqual(MOD.resolve(items["extension"], {})[0], "~HST")

    def test_snapshot_round_trip_stability_and_override(self):
        model = MOD.load_model(self.tree, self.snapshot, True, self.addons)
        before = self.snapshot.read_bytes()
        MOD.load_model(self.tree, self.snapshot, True, self.addons)
        self.assertEqual(before, self.snapshot.read_bytes())
        offline = MOD.load_model(self.base / "absent", self.snapshot, addons=self.addons)
        self.assertEqual(model, offline)
        packed = json.loads(before)
        self.assertTrue(all(isinstance(index, int) for c in packed["containers"]
                            for item in c["items"] for index in item["labels"]))
        self.assertLess(len(before), len(json.dumps(model, ensure_ascii=False, indent=1).encode()))
        self.override(ctx("Save"), "~Save", "~Lưu")
        overrides = MOD.load_overrides(self.overrides)
        self.assertEqual(MOD.check(model, overrides), MOD.check(offline, overrides))
        self.assertEqual(MOD.check(offline, overrides)["strict_problems"], 0)

    def test_snapshot_ignores_translation_changes_but_not_structure(self):
        MOD.load_model(self.tree, self.snapshot, True, self.addons)
        self.po(UI, [(ctx("Save"), "~Save", "~Lưu")])
        MOD.load_model(self.tree, self.snapshot, addons=self.addons)
        for replacement in ("~Changed", "~Save"):
            if replacement == "~Save":
                self.commands += command("New", Label="New")
                path = self.tree / (WRITER + "menubar/menubar.xml")
                path.write_text(path.read_text().replace('<menu:menuseparator/>', '<menu:menuitem menu:id=".uno:New"/>'), encoding="utf-8")
            self.write(self.config, xcu(self.commands.replace("~Save", replacement), self.popups))
            with self.assertRaisesRegex(ValueError, r"snapshot stale \(.*Writer.*--write-snapshot"):
                MOD.load_model(self.tree, self.snapshot, addons=self.addons)

    def test_cli_offline_exit_status_json_and_verbose(self):
        MOD.load_model(self.tree, self.snapshot, True, self.addons)
        output = self.base / "result.json"
        args = ["--tree", str(self.base / "absent"), "--snapshot", str(self.snapshot),
                "--overrides", str(self.overrides), "--exceptions", str(self.exceptions),
                "--addons", str(self.addons), "--json", str(output), "--verbose"]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(MOD.main(args), 0)
            self.assertEqual(MOD.main(args + ["--strict"]), 1)
        self.assertIn("auto: HST", stdout.getvalue())
        self.assertIn("Writer menus", stdout.getvalue())
        self.assertEqual(json.loads(output.read_text())["strict_problems"], 1)
        self.override(ctx("Save"), "~Save", "~Lưu")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MOD.main(args + ["--strict"]), 0)

    def test_addons_are_read_live_and_never_stale_the_snapshot(self):
        MOD.load_model(self.tree, self.snapshot, True, self.addons)
        self.assertNotIn("HST", self.snapshot.read_text(encoding="utf-8"))
        self.addons.write_text(self.addons.read_text(encoding="utf-8").replace("HST", "HSX"), encoding="utf-8")
        model = MOD.load_model(self.tree, self.snapshot, addons=self.addons)
        offline = MOD.load_model(self.base / "absent", self.snapshot, addons=self.addons)
        self.assertEqual(model, offline)
        labels = [MOD.resolve(i, {})[0] for c in model["containers"] for i in c["items"]]
        self.assertTrue(any("HSX" in label for label in labels))

    def test_snapshot_missing_or_generation_without_tree_fails(self):
        with self.assertRaisesRegex(ValueError, "snapshot .* missing; regenerate it with .*--write-snapshot"):
            MOD.load_model(self.tree, self.snapshot, addons=self.addons)
        with self.assertRaisesRegex(ValueError, "requires an upstream tree"):
            MOD.load_model(self.base / "absent", self.snapshot, True)


if __name__ == "__main__":
    unittest.main()
