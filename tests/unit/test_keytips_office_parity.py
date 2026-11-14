# SPDX-License-Identifier: AGPL-3.0-only
"""KeyTip, tab access key and shortcut parity with the familiar office suite (scripts/check-keytips-parity.py).

The committed tables must pass the offline check, the check must fail on a regression (a tab letter changed, a tab label
that shows another letter, a later patch rebinding a parity key), and the generated C++ (HstKeyTipOffice.hxx) must
behave as its Python twin: the suite's letter wins on its tab, a general letter that clashes gives way.
"""
import copy
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from _paths import ROOT

sys.path[:0] = [os.path.join(ROOT, "scripts", "ribbon"), os.path.join(ROOT, "scripts", "l10n")]
import keytips_model as model  # noqa: E402

SPEC = importlib.util.spec_from_file_location("check_keytips_parity", os.path.join(ROOT, "scripts", "check-keytips-parity.py"))
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)

DRIVER = r"""
#include "HstKeyTipOffice.hxx"
#include <cstdio>
using namespace hst::keytips;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %d %s\n", __LINE__, #c); ++failures; } } while (0)
int main()
{
    CHECK(moduleOf("modules/swriter/ui/notebookbar.ui") == "swriter");
    CHECK(moduleOf("modules/sdraw/ui/notebookbar.ui") == "sdraw");
    CHECK(moduleOf("modules/scalc/ui/notebookbar_compact.ui") == "scalc");
    CHECK(moduleOf("swriterx/ui").empty());
    CHECK(preferred("swriter", "ReviewLabel", "InsertAnnotation") == "!C"); // New Comment on Review
    CHECK(preferred("simpress", "HomeLabel", "InsertPage") == "!I");        // New Slide on Home
    CHECK(preferred("simpress", "InsertLabel", "InsertPage") == "!SI");     // New Slide on Insert
    CHECK(preferred("swriter", "NoSuchTab", "Bold") == "1");                 // the general table
    CHECK(preferred("swriter", "HomeLabel", "NoSuchCommand").empty());
    const auto tips = prioritise({ "!C", "C", "L", "!AL", "A", "AC", "" });
    CHECK(tips[0] == "C" && tips[1].empty() && tips[2] == "L" && tips[3] == "AL" && tips[4].empty());
    CHECK(tips[5] == "AC" && tips[6].empty());
    const auto assigned = assign(tips);
    CHECK(assigned[0] == "C" && assigned[3] == "AL" && assigned[5] == "AC" && assigned[1] != "C");
    std::printf("%d failures\n", failures);
    return failures != 0;
}
"""


class OfflineCheck(unittest.TestCase):
    def setUp(self):
        self.table = CHECK.read_json(CHECK.KEYTIPS)
        self.rows = CHECK.read_json(CHECK.SHORTCUTS)["rows"]

    def test_committed_tables_pass(self):
        self.assertEqual(CHECK.main([]), 0)

    def test_tab_letters_are_the_suites(self):
        self.assertEqual(self.table["tabs"]["impress"]["AnimationsLabel"], "A")
        self.assertEqual(self.table["tabs"]["writer"]["HomeLabel"], "H")
        errors = []
        CHECK.check_tabs(self.table, {"HomeLabel": "R"}, errors)
        self.assertTrue(any("HomeLabel" in e for e in errors))

    def test_clashing_command_letters_fail(self):
        table = copy.deepcopy(self.table)
        table["commands"]["swriter"]["HomeLabel"]["Bold"] = ["11", "Bold"]
        table["commands"]["swriter"]["HomeLabel"]["Italic"] = ["1", "Italic"]
        errors = []
        CHECK.check_commands(table, errors)
        self.assertTrue(any("cannot both" in e for e in errors), errors)

    def test_tab_label_with_another_access_key_fails(self):
        snapshot = CHECK.read_json(os.path.join(ROOT, "l10n", "access-keys-snapshot.json"))
        overrides = CHECK.load_overrides(os.path.join(ROOT, "l10n", "vi-overrides.jsonl"))
        errors = []
        CHECK.check_tab_labels(self.table, snapshot, overrides, errors)
        self.assertEqual(errors, [])
        # "~Hiệu ứng" would show H, but Alt+H opens Trang đầu
        key = ("sd/messages.po", "TabbedImpress|AnimationsTabLabel", "~Animations")
        overrides = dict(overrides)
        overrides[key] = "~Hiệu ứng"
        CHECK.check_tab_labels(self.table, snapshot, overrides, errors)
        self.assertTrue(any("Hiệu ứng" in e and "Alt+H" in e for e in errors), errors)

    def test_rebinding_a_parity_key_fails(self):
        row = next(r for r in self.rows if r["app"] == "impress" and r["office"] == "F5")
        self.assertEqual(row["uno"], ["Presentation"])
        later = ('--- a/x\n+++ b/x\n@@ -1,1 +1,4 @@\n         <node oor:name="F5" oor:op="replace">\n'
                 '+          <prop oor:name="Command">\n+            <value xml:lang="en-US">.uno:Navigator</value>\n'
                 '+          </prop>\n')
        bound = CHECK.accel.patch_bindings(later)
        self.assertIn(("F5", "Navigator"), bound)
        errors = []
        CHECK.later_conflicts(self.rows, {"hst-later.patch": bound}, errors)
        self.assertTrue(any("hst-later.patch binds F5 to Navigator" in e for e in errors), errors)

    def test_changed_rows_are_in_the_patch(self):
        changed = [r for r in self.rows if r["status"] == "changed"]
        self.assertGreater(len(changed), 20)
        self.assertTrue(all(r.get("was") is not None or r["key"] for r in changed))
        deviations = [r for r in self.rows if r["status"] == "deviation"]
        self.assertTrue(all(r["reason"] for r in deviations))


class Accelerators(unittest.TestCase):
    def test_a_key_defined_twice_in_a_module_fails(self):
        xcu = ('<oor:component-data xmlns:oor="http://openoffice.org/2001/registry"><node oor:name="PrimaryKeys">'
               '<node oor:name="Modules"><node oor:name="m">' + '<node oor:name="9_MOD1" oor:op="replace"/>' * 2
               + "</node></node></node></oor:component-data>")
        with tempfile.NamedTemporaryFile("w", suffix=".xcu", delete=False) as handle:
            handle.write(xcu)
        try:
            with self.assertRaisesRegex(ValueError, "9_MOD1 twice"):
                CHECK.accel.load([handle.name])
        finally:
            os.unlink(handle.name)


class Simulation(unittest.TestCase):
    def test_python_twin(self):
        self.assertEqual(model.prioritise(["!C", "C", "L", "!AL", "A", ""]), ["C", "", "L", "AL", "", ""])
        tips = model.assign(model.prioritise(["!C", "C", "", "!AL"]))
        self.assertEqual(tips[0], "C")
        self.assertEqual(tips[3], "AL")
        self.assertNotIn(tips[1], ("C", "A"))


@unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch")
class GeneratedHeader(unittest.TestCase):
    def test_lookup_and_priority(self):
        with tempfile.TemporaryDirectory() as work:
            tree = os.path.join(work, "tree")
            for path in (model.TABLE_HEADER, "sfx2/source/notebookbar/HstKeyTipOffice.hxx"):
                model.header_from_series(CHECK.PATCHES, path, tree)
            driver = os.path.join(work, "driver.cpp")
            with open(driver, "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            binary = os.path.join(work, "driver")
            subprocess.run(["g++", "-std=c++20", "-I", os.path.join(tree, "sfx2/source/notebookbar"), driver, "-o",
                            binary], check=True)
            result = subprocess.run([binary], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
