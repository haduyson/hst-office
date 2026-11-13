# SPDX-License-Identifier: AGPL-3.0-only
"""Priority ladders of every ribbon tab (scripts/patches/generate-ribbon-priorities.py, data/ribbon/scaling-priorities.json)."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

spec = importlib.util.spec_from_file_location("generate_ribbon_priorities", os.path.join(ROOT, "scripts/patches/generate-ribbon-priorities.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
DATA = json.load(open(os.path.join(ROOT, "data/ribbon/scaling-priorities.json"), encoding="utf-8"))
PATCH = os.path.join(ROOT, "patches/libreoffice/hst-ribbon-scale-ladders-ux.patch")


def fixture_tree(tmp, data):
    """One notebookbar.ui per app holding every listed merged group box with exactly its groups."""
    per_app = {}
    for entry in data["ladders"]:
        children = "".join(f'<child><object class="GtkGrid" id="{g}"/></child>' for g in entry["groups"])
        per_app.setdefault(entry["app"], []).append(f'<object class="sfxlo-PriorityMergedHBox" id="{entry["box"]}">{children}</object>')
    for app, boxes in per_app.items():
        path = os.path.join(tmp, gen.scale.UI[app])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("<interface>" + "".join(f"<child>{b}</child>" for b in boxes) + "</interface>")
    return tmp


class GenerateRibbonPrioritiesTest(unittest.TestCase):
    def test_data_is_valid_and_patch_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen.scale.validate(gen.ladders(DATA), fixture_tree(tmp, DATA))
        with open(PATCH, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), gen.patch_text(DATA))

    def test_every_app_and_main_tab_has_a_ladder(self):
        boxes = {(e["app"], e["box"]) for e in DATA["ladders"]}
        for app in ("writer", "calc", "impress", "draw"):
            for box in ("pmhbHome", "pmhbInsert", "pmhbReview", "pmhbView", "pmhbExtension"):
                self.assertIn((app, box), boxes)

    def test_ladder_order_and_nested_boxes(self):
        ladders = {(l["app"], l["box"]): l for l in gen.ladders(DATA)["ladders"]}
        view = ladders[("calc", "pmhbView")]
        # freeze panes is the most used group of the Sheets View tab: it shrinks and folds last
        self.assertEqual(view["fold"][-1], "gdViewFreeze")
        self.assertEqual(view["steps"][-1], ["gdViewFreeze", "C"])
        extension = ladders[("calc", "pmhbExtension")]
        self.assertNotIn(["pmhbExtensionAddons", "C"], extension["steps"])
        for entry in DATA["ladders"]:
            self.assertEqual(sorted(entry["priority"]), sorted(entry["groups"]), entry["box"])

    def test_bad_priority_fails(self):
        broken = {"ladders": [dict(DATA["ladders"][0], priority=DATA["ladders"][0]["priority"][1:])]}
        with self.assertRaises(gen.PriorityError):
            gen.ladders(broken)

    @unittest.skipUnless(shutil.which("g++") and shutil.which("patch"), "no C++ compiler or patch")
    def test_header_compiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = os.path.join(tmp, gen.scale.HEADER)
            os.makedirs(os.path.dirname(header))
            with open(os.path.join(ROOT, "data/ribbon/scaling-ladders.json"), encoding="utf-8") as handle:
                old = gen.scale.header(gen.scale.stage(json.load(handle), "draw"))
            with open(header, "w", encoding="utf-8") as handle:
                handle.write(old)
            run = subprocess.run(["patch", "-p1", "--fuzz=0", "-s", "-d", tmp, "-i", PATCH], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            driver = os.path.join(tmp, "t.cxx")
            with open(driver, "w", encoding="utf-8") as handle:
                handle.write('#include "HstRibbonLadders.hxx"\nint main() { return std::size(hst::ribbon::ladders::all) == %d ? 0 : 1; }\n'
                             % len(DATA["ladders"]))
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", os.path.dirname(header), driver,
                                    "-o", os.path.join(tmp, "t")], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertEqual(subprocess.run([os.path.join(tmp, "t")]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
