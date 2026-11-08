# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon groups that collapse into their button, the Home Tools block, the banner threshold and the Slides
galleries' height (hst-ribbon-group-button.patch, hst-ribbon-scale-ladders-collapse.patch,
hst-ribbon-banner-frame-width.patch, hst-slides-gallery-height.patch). These tests read the patches only."""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
BUTTON = os.path.join(PATCHES, "hst-ribbon-group-button.patch")
LADDERS = os.path.join(PATCHES, "hst-ribbon-scale-ladders-collapse.patch")
BANNER = os.path.join(PATCHES, "hst-ribbon-banner-frame-width.patch")
GALLERIES = os.path.join(PATCHES, "hst-slides-gallery-height.patch")
MERGED = "vcl/source/control/PriorityMergedHBox.cxx"


def sections(path):
    """{file: (added lines, removed lines, new text)} of a unified diff; the new text is context plus added."""
    result, current = {}, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), ([], [], []))
                continue
            if current is None or line.startswith(("--- ", "@@")):
                continue
            if line.startswith("+"):
                current[0].append(line[1:])
                current[2].append(line[1:])
            elif line.startswith("-"):
                current[1].append(line[1:])
            elif line.startswith(" "):
                current[2].append(line[1:])
    return result


def added(path, name):
    return "".join(sections(path)[name][0])


class GroupButton(unittest.TestCase):
    def test_collapsed_is_a_state_of_the_ladder(self):
        self.assertIn("constexpr int GroupCollapsed = 3;", added(BUTTON, "vcl/inc/HstRibbonLadder.hxx"))
        merged = added(BUTTON, MERGED)
        # only groups with a collapse step in their tab's ladder get a button, measured as a 4th width
        self.assertIn("rLadder.steps[i].state == hst::ribbon::GroupCollapsed", merged)
        self.assertIn("hst::ribbon::GroupStateCount + (aCollapsible[i] ? 1 : 0)", merged)
        # the content of a collapsed group stays large for the popup of its button
        self.assertIn("nState == hst::ribbon::GroupCollapsed\n", merged)

    def test_button_opens_the_group_and_is_never_folded(self):
        merged = added(BUTTON, MERGED)
        self.assertIn("IMPL_LINK(PriorityMergedHBox, HstGroupClickHdl, Button*, pButton, void)", merged)
        self.assertIn("pGroup->SetParent(m_pPopup->getBox());", merged)
        self.assertIn("hst::ribbon::SetGroupState(*pGroup, hst::ribbon::GroupLarge);", merged)
        self.assertIn("bool PriorityMergedHBox::HstIsFolded(const vcl::Window* pWindow) const", merged)
        # the chevron popup takes folded groups only: never a group button or a collapsed group
        self.assertNotIn("!pWindow->IsVisible())\n", merged)
        self.assertGreaterEqual(merged.count("HstIsFolded(pWindow)"), 3)
        self.assertIn("xButton.disposeAndClear();", merged)

    def test_gallery_keeps_room_for_previews(self):
        merged = added(BUTTON, MERGED)
        self.assertIn("if (pChild->get_hexpand())", merged)
        self.assertIn("rEntry.second[hst::ribbon::GroupLarge] += 3 * nPreview;", merged)
        self.assertIn("rEntry.second[hst::ribbon::GroupMedium] += nPreview;", merged)

    def test_a_later_collapse_can_bring_an_earlier_one_back(self):
        merged = added(BUTTON, MERGED)
        self.assertIn("for (auto it = aSteps.rbegin(); it != aSteps.rend(); ++it)", merged)
        self.assertIn("if (nNext <= nWidth)", merged)

    def test_caption_comes_from_the_group_label(self):
        helper = added(BUTTON, "vcl/source/control/HstRibbonLadder.cxx")
        self.assertIn("OUString GroupCaption(vcl::Window& rGroup)", helper)
        self.assertIn("GetAccessibleRelationLabeledBy()", helper)
        self.assertIn('replaceAll("~", "")', helper)
        for name in (MERGED, "vcl/source/control/DropdownBox.cxx"):
            text = added(BUTTON, name)
            self.assertIn("hst::ribbon::GroupCaption(", text, name)
            self.assertIn('u" \\u25BE"', text, name)
            self.assertIn("SetAccessibleName(aCaption)", text, name)

    def test_tools_gives_way_before_any_group_shrinks(self):
        prio = added(BUTTON, "vcl/source/control/PriorityHBox.cxx")
        self.assertIn("pMerged->HstFullWidth()", prio)
        self.assertIn("nFull - getLayoutRequisition(*pMerged).Width()", prio)
        self.assertIn("tools::Long HstFullWidth() const;", added(BUTTON, "vcl/inc/PriorityMergedHBox.hxx"))

    def test_collapsed_tools_keeps_the_ribbon_height(self):
        dropdown = added(BUTTON, "vcl/source/control/DropdownBox.cxx")
        self.assertIn("Size DropdownBox::calculateRequisition() const", dropdown)
        self.assertIn("!pChild->IsVisible()", dropdown)
        self.assertIn("Size calculateRequisition() const override;", added(BUTTON, "vcl/inc/DropdownBox.hxx"))


class CollapseLadders(unittest.TestCase):
    def test_every_home_ladder_collapses_before_it_folds(self):
        header = sections(LADDERS)["vcl/inc/HstRibbonLadders.hxx"][2]
        steps = {m.group(1): m.group(2) for m in (re.match(r"inline constexpr Step (\w+)_pmhbHome_steps\[\] = \{(.*)\};", line)
                                                    for line in header) if m}
        self.assertEqual(sorted(steps), ["calc", "impress", "writer"])
        for app, text in steps.items():
            self.assertIn(", 3 }", text, app)
        writer = re.findall(r'u"(\w+)", (\d)', steps["writer"])
        self.assertLess(writer.index(("gdHomeClipboard", "2")), writer.index(("gdHomeStyle", "3")))
        self.assertEqual(writer[-2:], [("gdHomeParagraph", "3"), ("gdHomeClipboard", "3")])


class BannerThreshold(unittest.TestCase):
    def test_threshold_counts_the_window_frame(self):
        text = added(BANNER, "sfx2/source/notebookbar/NotebookbarTabControl.cxx")
        self.assertIn("+ std::lround(16 * fDpi);", text)
        self.assertIn("hst::banner::modeFor(nWindowWidth", "".join(sections(BANNER)["sfx2/source/notebookbar/NotebookbarTabControl.cxx"][2]))


class GalleriesFit(unittest.TestCase):
    def test_paging_buttons_are_small(self):
        for name in ("hsttransitiongallery", "hstanimationgallery"):
            ui = added(GALLERIES, f"sd/uiconfig/simpress/ui/{name}.ui")
            self.assertEqual(ui.count('<class name="small-button"/>'), 3, name)
            self.assertEqual(ui.count('<property name="height-request">20</property>'), 3, name)


if __name__ == "__main__":
    unittest.main()
