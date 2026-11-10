# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon ladder generator (scripts/patches/generate-ribbon-scale.py): validation and stable output."""
import copy
import importlib.util
import json
import os
import subprocess
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
        self.assertIn('{ u"gdHomeStyle", 3 }', first)

    def test_committed_patch_is_current(self):
        # the first ladders stay as committed; the follow-up patch changes them to the current data
        base = os.path.join(ROOT, "patches/libreoffice/hst-ribbon-scale-ladders.patch")
        with open(os.path.join(ROOT, "patches/libreoffice/hst-ribbon-scale-ladders-collapse.patch"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), gen.follow_up_text(gen.base_header(base), gen.header(gen.stage(DATA))))

    def test_draw_follow_up_is_current_and_applies_after_the_committed_ladders(self):
        # HST Draw's ladder came later: its own follow-up patch adds it on top of the committed header
        old, new = gen.header(gen.stage(DATA)), gen.header(gen.stage(DATA, "draw"))
        text = gen.follow_up_text(old, new, gen.FOLLOW_UPS["draw"])
        with open(os.path.join(ROOT, "patches/libreoffice", gen.STAGES["draw"]), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), text)
        self.assertNotIn("draw_pmhbHome", old)
        self.assertIn("draw_pmhbHome", new)
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, gen.HEADER)
            os.makedirs(os.path.dirname(target))
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(old)
            run = subprocess.run(["patch", "-p1", "--fuzz=0", "-s", "-d", tmp], input=text, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(open(target, encoding="utf-8").read(), new)

    def test_draw_home_is_slides_home_without_the_slide_group(self):
        impress = next(l for l in DATA["ladders"] if l["app"] == "impress")
        draw = next(l for l in DATA["ladders"] if l["app"] == "draw")
        self.assertEqual(draw["groups"], [g for g in impress["groups"] if g != "gdHomeSlide"])
        self.assertEqual(draw["steps"], [s for s in impress["steps"] if s[0] != "gdHomeSlide"])
        with self.assertRaises(gen.LadderError):
            gen.stage(DATA, "nope")

    def test_follow_up_applies_to_the_base_header(self):
        base = os.path.join(ROOT, "patches/libreoffice/hst-ribbon-scale-ladders.patch")
        old = gen.base_header(base)
        with open(base, encoding="utf-8") as handle:
            self.assertEqual(gen.patch_text(old), handle.read())  # the base patch is read back exactly
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, gen.HEADER)
            os.makedirs(os.path.dirname(target))
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(old)
            run = subprocess.run(["patch", "-p1", "--fuzz=0", "-s", "-d", tmp],
                                 input=gen.follow_up_text(old, gen.header(gen.stage(DATA))), text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(open(target, encoding="utf-8").read(), gen.header(gen.stage(DATA)))

    def test_collapse_steps(self):
        # Home: Tools gives way first (PriorityHBox), then the ladder; Styles collapses into its
        # button before Paragraph shrinks and before anything folds
        writer = next(l for l in DATA["ladders"] if l["app"] == "writer")
        steps = [tuple(s) for s in writer["steps"]]
        self.assertLess(steps.index(("gdHomeFont", "S")), steps.index(("gdHomeStyle", "C")))
        self.assertLess(steps.index(("gdHomeClipboard", "S")), steps.index(("gdHomeStyle", "C")))
        self.assertIn('{ u"gdHomeStyle", 3 }', gen.header(DATA))
        for ladder in DATA["ladders"]:
            self.assertTrue(any(state == "C" for _group, state in ladder["steps"]), ladder["app"])

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
