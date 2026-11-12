# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon groups are as wide as their controls, not wider (hst-ribbon-group-gaps.patch).

- VclGrid: a ribbon group's caption wider than its controls no longer stretches their columns (which left
  the controls at the left and empty room on their right); the columns are centred under the caption.
- The merged group box (PriorityMergedHBox) turns that on for its groups, and on tabs without a ladder of
  their own it skips states whose controls would be narrower than the caption (a large button turned into
  a small icon under a long caption) and grows shrunk groups back into room the last ladder step left free.

Reads the patches; the regrow pass is compiled with the ladder header (skipped without a C++ compiler).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from test_ribbon_group_button import added, sections
from test_ribbon_scaling import header_from_patch

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
PATCH = os.path.join(PATCHES, "hst-ribbon-group-gaps.patch")
MERGED = "vcl/source/control/PriorityMergedHBox.cxx"
LAYOUT = "vcl/source/window/layout.cxx"
HEADER = "include/vcl/layout.hxx"


def series():
    with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


def function(text, signature):
    """The full text of a function definition that starts with `signature`, up to its closing brace."""
    start = text.index(signature)
    depth, index = 0, text.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
        if depth == 0:
            return text[start:index]


DRIVER = r"""
#include "HstRibbonScaling.hxx"
#include <cstdio>
#include <vector>
using namespace hst::ribbon;
%s
static int fails = 0;
static void expect(bool ok, const char* what) { if (!ok) { std::printf("FAIL %%s\n", what); ++fails; } }
int main()
{
    // a References-like row at 1080 px: the right group's small state frees far more than was missing
    std::vector<Group> groups{ { { 400, 400, 400 } }, { { 159, 159, 159 } }, { { 216, 216, 216 } },
                               { { 207, 240, 57 } }, { { 119, 119, 110 } } };
    Layout layout = select(groups, {}, 1080, 25);
    expect(layout.overflow.empty(), "fits without overflow");
    expect(layout.states[3] == 2 && layout.states[4] == 2, "the default ladder shrinks both right groups");
    lcl_HstRegrow(groups, defaultLadder(groups), 1080, layout);
    expect(layout.states[3] == 2, "the group whose large state does not fit stays small");
    expect(layout.states[4] == 0, "the group shrunk before it grows back to large");
    expect(rowWidth(groups, layout.states) <= 1080, "the row still fits");
    // nothing to give back: the row is unchanged
    Layout tight = select(groups, {}, 1000, 25);
    lcl_HstRegrow(groups, defaultLadder(groups), 1000, tight);
    expect(rowWidth(groups, tight.states) <= 1000, "a tight row still fits");
    // a group grows back into its largest state that fits, medium when large does not
    std::vector<Group> mid{ { { 300, 200, 100 } }, { { 300, 200, 100 } } };
    Layout two = select(mid, {}, 400, 0);
    lcl_HstRegrow(mid, defaultLadder(mid), 400, two);
    expect(rowWidth(mid, two.states) <= 400 && rowWidth(mid, two.states) >= 400, "regrow fills the row");
    return fails;
}
"""


class GroupGapsPatch(unittest.TestCase):
    def test_in_series_after_the_ribbon_engine(self):
        names = series()
        self.assertIn("hst-ribbon-group-gaps.patch", names)
        mine = names.index("hst-ribbon-group-gaps.patch")
        for engine in ("hst-ribbon-ladder-best-fit.patch", "hst-ribbon-tools-bare.patch",
                       "hst-ribbon-group-button.patch", "hst-ribbon-ladder-nested-box.patch"):
            self.assertLess(names.index(engine), mine, engine)

    def test_grid_centres_columns_under_a_wider_caption(self):
        header = added(PATCH, HEADER)
        self.assertIn("void set_hst_centre_spanned(bool bCentre)", header)
        self.assertIn("bool m_bHstCentreSpanned = false;", header)  # off for every other grid
        self.assertIn("tools::Long get_hst_caption_room() const;", header)
        layout = added(PATCH, LAYOUT)
        # the caption is a label (or a box holding one, with the launcher) in the last row
        self.assertIn("if (y + nHeight != nMaxY)", layout)
        self.assertIn("rChild.GetType() == WindowType::FIXEDTEXT", layout)
        # its extra width goes before and after the columns instead of into them
        self.assertIn("pPads->aLead[x] += nExtraWidth / 2;", layout)
        self.assertIn("pPads->aTrail[x+nWidth-1] += nExtraWidth - nExtraWidth / 2;", layout)
        # an expanding column (a gallery) still takes the extra as before
        self.assertIn("if (nExtraWidth > 0 && bCaption && !bExpandable)", layout)
        # every child but the caption keeps to its columns
        self.assertIn("aChildPos.AdjustX(nLead);", layout)
        self.assertIn("aChildAlloc.AdjustWidth(-(nLead + nTrail));", layout)
        removed = sections(PATCH)[LAYOUT][1]
        self.assertEqual([line.strip() for line in removed if "setLayoutAllocation" in line],
                         ["setLayoutAllocation(*pChild, aAllocPos, aChildAlloc);"])

    def test_merged_box_uses_it_for_its_groups(self):
        merged = added(PATCH, MERGED)
        self.assertIn("pGrid->set_hst_centre_spanned(true);", merged)
        self.assertIn("return pGrid ? pGrid->get_hst_caption_room() : 0;", merged)
        # the authored ladders (the Home tabs) keep every state and their own order
        self.assertIn("bOwnLadder = true;", merged)
        self.assertIn("if (nState > 0 && !bOwnLadder)", merged)
        self.assertIn("if (aLayout.overflow.empty() && !bOwnLadder)", merged)

    def test_default_ladder_is_medium_then_button_then_chevron(self):
        merged = added(PATCH, MERGED)
        # every group of a tab without its own ladder can show as its button (not a nested merged box)
        self.assertIn("aCollapsible[i] = !dynamic_cast<PriorityMergedHBox*>(aWindows[i]);", merged)
        # Small is no rung, nor a step that saves less than 24 px (scaled) or no more than the empty room
        self.assertIn("const tools::Long nMinGain = std::lround(24 * GetDPIScaleFactor());", merged)
        self.assertIn("bSkip = nState == hst::ribbon::GroupSmall || nGain < nMinGain", merged)
        self.assertIn("|| nGain <= lcl_HstCaptionRoom(*pChild);", merged)
        self.assertIn("rEntry.second.push_back(bSkip ? rEntry.second.back() : nMeasured);", merged)
        self.assertIn("nNarrowest - nButton < nMinGain ? rEntry.second.back() : nButton", merged)
        # collapsed groups come back and shrunk ones grow back with the ladder select() used
        self.assertIn("aSteps.empty() ? hst::ribbon::defaultLadder(aGroups) : aSteps;", merged)
        self.assertIn("lcl_HstUncollapse(aGroups, aUsed, nWidth, aLayout);", merged)
        self.assertIn("lcl_HstUncollapse(aShownGroups, aShownUsed, nRoom, aRefill);", merged)

    def test_one_command_group_stays_large(self):
        ladder = added(PATCH, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("(bOnlyCommand && rData.meHstAuthoredSize == ToolBoxButtonSize::Large)", ladder)
        self.assertIn("aToolBoxes.size() == 1 && holdsOneCommand(*aToolBoxes.front())", ladder)
        self.assertIn("rToolBox.GetItemType(i) == ToolBoxItemType::BUTTON", ladder)

    def test_one_button_groups_are_large(self):
        for ui, box in (("sw/uiconfig/swriter/ui/notebookbar.ui", "bxInsertInsertAVMedia"),
                        ("sd/uiconfig/simpress/ui/notebookbar.ui", "bxInsertInsertAVMedia"),
                        ("sc/uiconfig/scalc/ui/notebookbar.ui", "bxLayoutChooseDesign")):
            text = "".join(sections(PATCH)[ui][2])
            props = text[text.index(f'id="{box}"'):]
            props = props[:props.index("<child>")]
            for prop in ('<property name="toolbar-style">both</property>', '<property name="icon_size">3</property>',
                         '<property name="valign">center</property>'):
                self.assertIn(prop, props, (ui, box))

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_regrow(self):
        regrow = function(added(PATCH, MERGED), "void lcl_HstRegrow(")
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonScaling.hxx"), "w", encoding="utf-8") as handle:
                handle.write(header_from_patch())
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER % re.sub(r"hst::ribbon::", "", regrow).replace(
                    "static_cast<size_t>(GroupStateCount)", "static_cast<size_t>(3)"))
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", exe,
                                    os.path.join(tmp, "driver.cxx")], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
