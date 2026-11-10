# SPDX-License-Identifier: AGPL-3.0-only
"""hst-msi-app-desktop-shortcuts.patch: the Windows installer puts HST Writer, HST Sheets and HST Slides on the desktop
when "Tạo lối tắt trên màn hình nền" (CREATEDESKTOPLINK) is ticked on the setup-type page.

Offline: the scp2 items, helper files and dialog rows the patch adds. With HST_LO_SRC set to a patched tree, the
SetupType page of that tree is checked as a whole (tab order, layout, the one box bound to CREATEDESKTOPLINK).
scripts/windows/check-app-shortcuts.ps1 checks an installed MSI in windows-smoke."""
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-msi-app-desktop-shortcuts.patch"
# module dir -> (shortcut name, launcher file gid, AppUserModelID suffix, helper file name, brand module)
APPS = {
    "writer": ("HST Writer", "auto_writer_brand_exe_swriter", "Writer", "desktophelper_writer.txt", "gid_Module_Brand_Prg_Wrt"),
    "calc": ("HST Sheets", "auto_calc_brand_exe_scalc", "Calc", "desktophelper_calc.txt", "gid_Module_Brand_Prg_Calc"),
    "impress": ("HST Slides", "auto_impress_brand_exe_simpress", "Impress", "desktophelper_impress.txt",
                "gid_Module_Brand_Prg_Impress"),
}
IDT = "instsetoo_native/inc_openoffice/windows/msi_templates/"


def added_lines():
    """{path: [lines the patch adds]} and {path: [lines it removes]}."""
    added, removed, current = {}, {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            added.setdefault(current, [])
            removed.setdefault(current, [])
        elif current and line.startswith("+"):
            added[current].append(line[1:])
        elif current and line.startswith("-") and not line.startswith("---"):
            removed[current].append(line[1:])
    return added, removed


def scp_items(text, kind):
    """{gid: {key: value}} of the `kind` (File, FolderItem, FolderItemProperty) blocks in scp text."""
    items = {}
    for match in re.finditer(r"^%s (\w+)\n(.*?)^End$" % kind, text, re.M | re.S):
        props = {}
        for line in match.group(2).splitlines():
            prop = re.match(r"\s*(\w+)\s*=\s*(.*?);\s*$", line)
            if prop:
                props[prop.group(1)] = prop.group(2).strip('"')
        items[match.group(1)] = props
    return items


def idt_rows(text, table_columns):
    """Data rows of an .idt file (three header lines) as dicts."""
    rows = []
    for line in text.splitlines()[3:]:
        if line.strip():
            cells = line.split("\t")
            rows.append(dict(zip(table_columns, cells + [""] * (len(table_columns) - len(cells)))))
    return rows


CONTROL = ("Dialog_", "Control", "Type", "X", "Y", "Width", "Height", "Attributes", "Property", "Text", "Control_Next",
           "Help")


class DesktopShortcutItems(unittest.TestCase):
    def setUp(self):
        self.added, self.removed = added_lines()

    def test_appended_to_the_series(self):
        series = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
        self.assertIn(PATCH.name, series)

    def test_one_desktop_shortcut_per_app_like_its_start_menu_entry(self):
        for module, (name, exe, appid, helper, _brand) in APPS.items():
            text = "\n".join(self.added["scp2/source/%s/folderitem_%s.scp" % (module, module)]) + "\n"
            items = scp_items(text, "FolderItem")
            self.assertEqual(len(items), 1, module)
            (gid, item), = items.items()
            self.assertEqual(item["Name"], name)
            self.assertEqual(item["FolderID"], "PREDEFINED_DESKTOP")
            self.assertEqual((item["FileID"], item["IconFile"], item["IconID"]), (exe, exe, "0"))
            self.assertEqual(item["Parameter"], "")
            self.assertEqual(item["Styles"], "(NON_ADVERTISED,USE_HELPER_FILENAME)")
            self.assertEqual(item["ComponentCondition"], "CREATEDESKTOPLINK=1")
            # the component is this app's own helper file, not the shared one of the Start Center link
            files = scp_items(text, "File")
            self.assertEqual(set(files), {item["ComponentIDFile"]}, module)
            helper_file = files[item["ComponentIDFile"]]
            self.assertEqual(helper_file["Name"], helper)
            self.assertEqual(helper_file["ComponentCondition"], "CREATEDESKTOPLINK=1")
            self.assertEqual(helper_file["Dir"], "gid_Brand_Dir_Program")
            props = scp_items(text, "FolderItemProperty")
            self.assertEqual([(p["ShortcutID"], p["Key"], p["Value"]) for p in props.values()],
                             [(gid, "System.AppUserModel.ID", "HASONTECH.HSTOffice." + appid)])

    def test_same_name_as_the_start_menu_entry(self):
        # hst-packaging-scp2.patch names the Start menu entries; the desktop must use the same words.
        start_menu = (ROOT / "patches/libreoffice/hst-packaging-scp2.patch").read_text(encoding="utf-8")
        for name, *_ in APPS.values():
            self.assertIn('+    Name = "%s";' % name, start_menu)

    def test_helper_files_are_packaged_and_in_their_app_module(self):
        package = "\n".join(self.added["setup_native/Package_misc.mk"])
        for module, (_name, _exe, appid, helper, brand) in APPS.items():
            self.assertIn("$(LIBO_BIN_FOLDER)/%s,win32/desktophelper.txt" % helper, package)
            module_lines = self.added["scp2/source/%s/module_%s.scp" % (module, module)]
            self.assertIn("             , gid_Brand_File_Desktophelper_%s_Txt" % appid, module_lines)
            self.assertIn("#ifdef WNT", module_lines)
            removed = self.removed["scp2/source/%s/module_%s.scp" % (module, module)]
            self.assertEqual(len(removed), 1)
            self.assertIn("auto_%s_brand_ALL" % module, removed[0])

    def test_box_moves_to_the_setup_type_page(self):
        rows = idt_rows("h\nh\nh\n" + "\n".join(self.added[IDT + "Control.idt"]), CONTROL)
        boxes = [r for r in rows if r["Property"] == "CREATEDESKTOPLINK"]
        self.assertEqual([(r["Dialog_"], r["Control"], r["Type"], r["Text"]) for r in boxes],
                         [("SetupType", "DesktopLink", "CheckBox", "OOO_CONTROL_HST_DESKTOP_SHORTCUTS")])
        gone = [line for line in self.removed[IDT + "Control.idt"] if "\tCREATEDESKTOPLINK\t" in line]
        self.assertEqual(len(gone), 1)
        self.assertTrue(gone[0].startswith("ReadyToInstall\tDesktopLink\t"))
        self.assertEqual(self.removed[IDT + "ControlC.idt"], ["ReadyToInstall\tDesktopLink\tHide\tNOT DESKTOPLINKEXISTS"])

    def test_box_text_in_english_and_vietnamese(self):
        ulf = "\n".join(self.added["instsetoo_native/inc_openoffice/windows/msi_languages/Control.ulf"])
        self.assertIn('[OOO_CONTROL_HST_DESKTOP_SHORTCUTS]\nen-US = "Create desktop shortcuts"', ulf)
        po = "\n".join(self.added["translations/source/vi/instsetoo_native/inc_openoffice/windows/msi_languages.po"])
        self.assertIn('"OOO_CONTROL_HST_DESKTOP_SHORTCUTS\\n"', po)
        self.assertIn('msgid "Create desktop shortcuts"\nmsgstr "Tạo lối tắt trên màn hình nền"', po)


@unittest.skipUnless(os.environ.get("HST_LO_SRC"), "HST_LO_SRC (a patched tree) not set")
class PatchedSetupTypePage(unittest.TestCase):
    def setUp(self):
        tree = Path(os.environ["HST_LO_SRC"])
        self.rows = idt_rows((tree / IDT / "Control.idt").read_text(encoding="latin-1"), CONTROL)
        self.conditions = (tree / IDT / "ControlC.idt").read_text(encoding="latin-1")

    def page(self, dialog):
        return {r["Control"]: r for r in self.rows if r["Dialog_"] == dialog}

    def test_only_the_setup_type_page_asks(self):
        self.assertEqual([(r["Dialog_"], r["Control"]) for r in self.rows if r["Property"] == "CREATEDESKTOPLINK"],
                         [("SetupType", "DesktopLink")])
        self.assertNotIn("DesktopLink", self.page("ReadyToInstall"))
        self.assertNotIn("ReadyToInstall\tDesktopLink", self.conditions)
        # shown for Typical and Custom alike: no show/hide condition
        self.assertNotIn("SetupType\tDesktopLink", self.conditions)

    def test_tab_order_is_one_cycle_through_every_control_that_takes_focus(self):
        for dialog in ("SetupType", "ReadyToInstall"):
            page = self.page(dialog)
            focus = {name for name, r in page.items() if r["Control_Next"]}
            start = next(iter(sorted(focus)))
            seen, name = [], start
            while name not in seen:
                self.assertIn(name, page, "%s: tab order names a missing control %s" % (dialog, name))
                seen.append(name)
                name = page[name]["Control_Next"]
            self.assertEqual(name, start, dialog)
            self.assertEqual(set(seen), focus, dialog)
        order = []
        name = "RadioGroup"
        while name not in order:
            order.append(name)
            name = self.page("SetupType")[name]["Control_Next"]
        self.assertEqual(order[:4], ["RadioGroup", "DefaultApps", "DesktopLink", "Back"])

    def test_boxes_fit_between_the_choices_and_the_buttons(self):
        page = self.page("SetupType")
        bottom = lambda r: int(r["Y"]) + int(r["Height"])  # noqa: E731
        radio, apps, links, line = page["RadioGroup"], page["DefaultApps"], page["DesktopLink"], page["DlgLine"]
        self.assertLessEqual(bottom(page["CustText"]), int(apps["Y"]))
        self.assertLessEqual(bottom(radio), int(apps["Y"]))
        self.assertLessEqual(bottom(apps), int(links["Y"]))
        self.assertLessEqual(bottom(links), int(line["Y"]))


if __name__ == "__main__":
    unittest.main()
