# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon ladder generator (scripts/patches/generate-ribbon-scale.py): validation and stable output."""
import copy
import importlib.util
import json
import os
import tempfile
import unittest

from _paths import ROOT

spec = importlib.util.spec_from_file_location("generate_ribbon_scale", os.path.join(ROOT, "scripts/patches/generate-ribbon-scale.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
DATA = json.load(open(os.path.join(ROOT, "data/ribbon/scaling-ladders.json"), encoding="utf-8"))


def fixture_tree(tmp, data):
    """A tree with one merged group box per ladder, holding exactly its groups."""
    for ladder in data["ladders"]:
        children = "".join(f'<child><object class="GtkGrid" id="{g}"/></child>' for g in ladder["groups"])
        path = os.path.join(tmp, gen.UI[ladder["app"]])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f'<interface><object class="sfxlo-PriorityMergedHBox" id="{ladder["box"]}">{children}</object></interface>')
    return tmp


class GenerateRibbonScaleTest(unittest.TestCase):
    def test_data_is_valid_and_output_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen.validate(DATA, fixture_tree(tmp, DATA))
        first, second = gen.patch_text(gen.header(DATA)), gen.patch_text(gen.header(copy.deepcopy(DATA)))
        self.assertEqual(first, second)
        self.assertIn("+++ b/vcl/inc/HstRibbonLadders.hxx", first)
        self.assertIn('{ u"gdHomeParagraph", 1 }', first)

    def test_committed_patch_is_current(self):
        with open(os.path.join(ROOT, "patches/libreoffice/hst-ribbon-scale-ladders.patch"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), gen.patch_text(gen.header(DATA)))

    def test_mismatches_fail_loudly(self):
        cases = []
        moved = copy.deepcopy(DATA); moved["ladders"][0]["groups"].reverse(); cases.append(("order", moved, DATA))
        unknown = copy.deepcopy(DATA); unknown["ladders"][1]["steps"].append(["gdNope", "S"]); cases.append(("step", unknown, unknown))
        state = copy.deepcopy(DATA); state["ladders"][2]["steps"][0][1] = "X"; cases.append(("state", state, state))
        fold = copy.deepcopy(DATA); fold["ladders"][0]["fold"].pop(); cases.append(("fold", fold, fold))
        box = copy.deepcopy(DATA); box["ladders"][0]["box"] = "pmhbNope"; cases.append(("box", box, DATA))
        for label, data, tree_data in cases:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(gen.LadderError):
                    gen.validate(data, fixture_tree(tmp, tree_data))


if __name__ == "__main__":
    unittest.main()
