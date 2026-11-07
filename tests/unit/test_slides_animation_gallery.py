# SPDX-License-Identifier: AGPL-3.0-only
"""Slides animations gallery (hst-slides-animation-gallery.patch and its strings patch).

The gallery is a toolbox controller in sd for .uno:HstApplyAnimation, built from a .ui file, and the
command is an sd slot. Its pieces live in different files that must agree: the slot name, the command
label and the controller registration; the component entry and the implementation in C++; the widget
ids of the .ui and the ones the code looks up; every translatable string of the .ui and its
Vietnamese translation. These tests read the patches only, no build is needed.
"""
import os
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
GALLERY = os.path.join(PATCHES, "hst-slides-animation-gallery.patch")
STRINGS = os.path.join(PATCHES, "hst-slides-animation-gallery-strings.patch")
UI = "sd/uiconfig/simpress/ui/hstanimationgallery.ui"
CXX = "sd/source/ui/controller/HstAnimationGallery.cxx"
APPLY = "sd/source/ui/animations/HstAnimationApply.cxx"


def sections(path):
    """{file: (added lines, removed lines)} of a unified diff."""
    result, current = {}, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = result.setdefault(match.group(1), ([], []))
                continue
            if current is None or line.startswith(("--- ", "@@")):
                continue
            if line.startswith("+"):
                current[0].append(line[1:])
            elif line.startswith("-"):
                current[1].append(line[1:])
    return result


def added(path, name):
    return "".join(sections(path)[name][0])


class AnimationGalleryPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = sections(GALLERY)
        cls.ui = ET.fromstring(added(GALLERY, UI))
        cls.cxx = added(GALLERY, CXX)

    def test_only_additions_outside_new_files(self):
        # the wiring adds lines and never removes any, so the patch drops cleanly
        for name, (_plus, minus) in self.files.items():
            self.assertEqual(minus, [], name)

    def test_slot_command_label_and_controller_agree(self):
        sdi = added(GALLERY, "sd/sdi/sdraw.sdi")
        self.assertRegex(sdi, r"SfxStringItem HstApplyAnimation SID_HST_APPLY_ANIMATION\n"
                              r"\(SfxStringItem Effect SID_HST_APPLY_ANIMATION\)")
        for shell in ("sd/sdi/drviewsh.sdi",):
            self.assertIn("SID_HST_APPLY_ANIMATION", added(GALLERY, shell), shell)
        self.assertIn("SID_HST_APPLY_ANIMATION             (SID_SD_START+459)", added(GALLERY, "sd/inc/app.hrc"))
        commands = added(GALLERY, "officecfg/registry/data/org/openoffice/Office/UI/DrawImpressCommands.xcu")
        self.assertIn('<node oor:name=".uno:HstApplyAnimation"', commands)
        self.assertIn('oor:name="Label"', commands)
        controller = added(GALLERY, "officecfg/registry/data/org/openoffice/Office/UI/Controller.xcu")
        self.assertIn("<value>.uno:HstApplyAnimation</value>", controller)
        self.assertIn("<value>com.sun.star.presentation.PresentationDocument</value>", controller)
        self.assertIn("<value>com.sun.star.comp.sd.HstAnimationGalleryControl</value>", controller)
        # the gallery dispatches the same command with the slot's argument name
        self.assertIn('u".uno:HstApplyAnimation"_ustr', self.cxx)
        self.assertIn('makePropertyValue(u"Effect"_ustr', self.cxx)

    def test_component_matches_implementation(self):
        component = added(GALLERY, "sd/util/sd.component")
        name = re.search(r'implementation name="([^"]+)"\s+constructor="([^"]+)"', component)
        self.assertIsNotNone(name)
        self.assertIn(f'return u"{name.group(1)}"_ustr;', self.cxx)
        self.assertIn(f"{name.group(2)}(", self.cxx)
        makefile = added(GALLERY, "sd/Library_sd.mk")
        self.assertIn("sd/source/ui/controller/HstAnimationGallery", makefile)
        self.assertIn("sd/source/ui/animations/HstAnimationApply", makefile)
        self.assertIn("sd/uiconfig/simpress/ui/hstanimationgallery", added(GALLERY, "sd/UIConfig_simpress.mk"))

    def test_ui_has_the_widgets_the_code_uses(self):
        ids = {node.get("id") for node in self.ui.iter("object")}
        for widget in re.findall(r'weld_\w+\(u"([^"]+)"_ustr\)', self.cxx):
            self.assertIn(widget, ids)
        self.assertIn('u"AnimationGalleryBox"_ustr', self.cxx)
        self.assertIn("AnimationGalleryBox", ids)
        self.assertIn('u"modules/simpress/ui/hstanimationgallery.ui"_ustr', self.cxx)

    def test_every_control_has_an_accessible_name(self):
        named = set()
        for node in self.ui.iter("object"):
            for child in node.findall("child"):
                inner = child.find("object")
                if child.get("internal-child") == "accessible" and inner is not None:
                    if any(p.get("name") == "AtkObject::accessible-name" for p in inner.findall("property")):
                        named.add(node.get("id"))
        for widget in ("animations", "prev", "next", "more"):
            self.assertIn(widget, named)

    def test_apply_is_one_undo_action(self):
        apply = added(GALLERY, APPLY)
        self.assertEqual(apply.count("std::make_unique<UndoAnimation>"), 1)
        self.assertEqual(apply.count("AddUndoAction"), 1)
        self.assertLess(apply.index("AddUndoAction"), apply.index("pSequence->remove("))
        self.assertLess(apply.index("pSequence->remove("), apply.index("pSequence->append("))
        self.assertIn("MainSequenceRebuildGuard", apply)
        self.assertIn("SetModified()", apply)
        self.assertLess(apply.index("pSequence->getRootNode()"), apply.index("AddUndoAction"))
        self.assertEqual(apply.count("pSequence->getRootNode()"), 2)
        # The flush scope is constructed first, so it runs after the rebuild guard releases.
        self.assertLess(apply.index("comphelper::ScopeGuard aModified"), apply.index("MainSequenceRebuildGuard aRebuild"))

    def test_rollback_switch(self):
        self.assertIn("SlidesEffectGalleries::get()", self.cxx)
        self.assertIn("HideItem", self.cxx)


class AnimationGalleryStrings(unittest.TestCase):
    def test_every_ui_string_is_translated(self):
        ui = ET.fromstring(added(GALLERY, UI))
        wanted = {(p.get("context"), p.text) for p in ui.iter("property") if p.get("translatable") == "yes"}
        self.assertTrue(wanted)
        po = added(STRINGS, "translations/source/vi/sd/messages.po")
        found = set(re.findall(r'msgctxt "([^"]+)"\nmsgid "([^"]+)"\nmsgstr "([^"]+)"', po))
        have = {(ctx, en) for ctx, en, vi in found if vi and vi != en}
        self.assertEqual(wanted - have, set())

    def test_command_label_is_translated(self):
        po = added(STRINGS, "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po")
        self.assertIn('..DrawImpressCommands.UserInterface.Commands..uno:HstApplyAnimation\\n"\n"Label\\n"', po)
        labels = re.findall(r'oor:name="Label".*?<value xml:lang="en-US">([^<]+)</value>', added(
            GALLERY, "officecfg/registry/data/org/openoffice/Office/UI/DrawImpressCommands.xcu"), re.S)
        for label in labels:
            self.assertIn(f'msgid "{label}"', po)


# Fixed order and only the four alternatives authorized by the gallery contract.
PRESETS = [
    ("ooo-entrance-appear", "", "ENTRANCE"),
    ("ooo-entrance-fade-in", "", "ENTRANCE"),
    ("ooo-entrance-fly-in", "", "ENTRANCE"),
    ("ooo-entrance-float", "ooo-entrance-ascend", "ENTRANCE"),
    ("ooo-entrance-split", "", "ENTRANCE"),
    ("ooo-entrance-wipe", "", "ENTRANCE"),
    ("ooo-entrance-wheel", "ooo-entrance-spoke-wheel", "ENTRANCE"),
    ("ooo-entrance-random-bars", "", "ENTRANCE"),
    ("ooo-entrance-zoom", "ooo-entrance-grow-and-turn", "ENTRANCE"),
    ("ooo-entrance-bounce", "ooo-entrance-boomerang", "ENTRANCE"),
    ("ooo-emphasis-spin", "", "EMPHASIS"),
    ("ooo-emphasis-grow-and-shrink", "", "EMPHASIS"),
    ("ooo-emphasis-transparency", "", "EMPHASIS"),
    ("ooo-emphasis-blink", "", "EMPHASIS"),
    ("ooo-exit-disappear", "", "EXIT"),
    ("ooo-exit-fade-out", "", "EXIT"),
    ("ooo-exit-fly-out", "", "EXIT"),
    ("ooo-exit-split", "", "EXIT"),
    ("ooo-exit-zoom", "", "EXIT"),
]


class AnimationGalleryContract(unittest.TestCase):
    def test_exact_preset_order_and_fallbacks(self):
        cxx = added(GALLERY, CXX)
        presets = re.search(r'const PresetSpec PRESETS\[\] = \{(.*?)\n\};', cxx, re.S).group(1)
        found = re.findall(r'\{ u"([^"]+)"_ustr, (?:u"([^"]+)"_ustr|OUString\(\)), STR_HST_ANIM_(\w+) \}', presets)
        self.assertEqual(found, PRESETS)
        self.assertIn('AnimationNone = u"None"_ustr', added(GALLERY, "sd/source/ui/inc/HstAnimationApply.hxx"))
        self.assertLess(cxx.index("sd::hst::AnimationNone"), cxx.index("for (const auto& rSpec : PRESETS)"))
        self.assertIn("getEffectDescriptor(rSpec.aId)", cxx)
        self.assertIn("getEffectDescriptor(rSpec.aFallback)", cxx)
        self.assertRegex(cxx, r"if \(!pPreset\)\s+continue;")
        self.assertIn("pPreset->getLabel()", cxx)
        self.assertNotIn("TODO", cxx + added(GALLERY, APPLY))

    def test_named_icons_exist_in_colibre(self):
        source = Path(os.environ.get("HST_LO_SRC", os.path.join(ROOT, "upstream/libreoffice")))
        theme = source / "icon-themes/colibre"
        if not theme.is_dir() and not os.environ.get("HST_LO_SRC"):
            self.skipTest("no upstream tree; set HST_LO_SRC to check the Colibre icons")
        self.assertTrue(theme.is_dir(), f"Missing Colibre theme: {theme}")
        links = {word for line in (theme / "links.txt").read_text().splitlines()
                 if line and not line.startswith("#") for word in line.split()}
        icons = set(re.findall(r'(?:u")?((?:cmd|sd)/[^"<>\s]+\.(?:png|svg))',
                               added(GALLERY, CXX) + added(GALLERY, UI)))
        self.assertTrue(icons)
        for icon in sorted(icons):
            with self.subTest(icon=icon):
                self.assertTrue((theme / icon).is_file() or icon in links, icon)

    def test_normal_view_selection_and_state(self):
        files = sections(GALLERY)
        self.assertNotIn("sd/sdi/SlideSorterController.sdi", files)
        self.assertNotIn("sd/source/ui/slidesorter/shell/SlideSorterViewShell.cxx", files)
        apply = added(GALLERY, APPLY)
        for invariant in ("dynamic_cast<DrawViewShell*>", "GetMarkedObjectList()", "GetMark(i)",
                          "IsReadOnly()", "DisableItem(SID_HST_APPLY_ANIMATION)", "getMainSequence()",
                          "getTargetShape() == xShape", "return pEffect->getPresetId()", "return AnimationNone;",
                          "FirstEffect(pSequence, xShape) != aFirst"):
            self.assertIn(invariant, apply)
        self.assertIn("ExecuteApplyAnimation", added(GALLERY, "sd/source/ui/view/drviews2.cxx"))
        self.assertIn("GetApplyAnimationState", added(GALLERY, "sd/source/ui/view/drviews7.cxx"))

    def test_replacement_none_and_text_group_rules(self):
        apply = added(GALLERY, APPLY)
        self.assertIn("pEffect->getTargetShape()) != aSelection.aShapes.end()", apply)
        self.assertLess(apply.index("if (!bNone && !pDescriptor)"), apply.index("AddUndoAction"))
        self.assertLess(apply.index("if (bNone)\n            return true;"), apply.index("pSequence->append("))
        self.assertIn("pSequence->append(pDescriptor, aTarget, pDescriptor->getDuration())", apply)
        self.assertIn("aSelection.aShapes", apply)
        self.assertIn("rSelection.aShapes.size() != 1", apply)
        self.assertIn("xText->getString().isEmpty()", apply)
        self.assertIn("drawing::FillStyle_NONE && eLine == drawing::LineStyle_NONE", apply)
        self.assertIn("createTextGroup(pCreated, 1, -1.0, false, false)", apply)
        self.assertRegex(apply, r"if \(!bFirst\)\s+pCreated->setNodeType\(presentation::EffectNodeType::WITH_PREVIOUS\)")
        self.assertGreaterEqual(apply.count("catch (const uno::Exception&)"), 3)

    def test_paging_and_accessible_effect_classes(self):
        cxx = added(GALLERY, CXX)
        for invariant in ("ITEM_WIDTH = 130", "void Resize() override", "GetSizePixel().Width()",
                          "connect_selection_changed", "connect_item_activated", "if (!m_bFilling)",
                          "SdResId(rSpec.aClass)", "set_item_accessible_name(nPos, rEntry.aAccessibleName)",
                          "set_item_tooltip_text(nPos, rEntry.aAccessibleName)",
                          ".uno:SidebarDeck.SdCustomAnimationDeck", "#include <vcl/weld/Builder.hxx>"):
            self.assertIn(invariant, cxx)
        self.assertNotIn("rPresetId == m_aCurrent", cxx)
        self.assertNotIn("set_columns(", cxx)
        self.assertNotIn('name="columns"', added(GALLERY, UI))
        po = added(STRINGS, "translations/source/vi/sd/messages.po")
        for kind, en, vi in (("ENTRANCE", "Entrance", "Vào"), ("EMPHASIS", "Emphasis", "Nhấn mạnh"),
                             ("EXIT", "Exit", "Thoát")):
            self.assertIn(f'NC_("STR_HST_ANIM_{kind}", "{en}")', added(GALLERY, "sd/inc/strings.hrc"))
            self.assertIn(f'msgctxt "STR_HST_ANIM_{kind}"\nmsgid "{en}"\nmsgstr "{vi}"', po)

    def test_vietnamese_labels_and_tooltip(self):
        po = added(STRINGS, "translations/source/vi/sd/messages.po")
        for label in ("Hiệu ứng hoạt hình", "Các hiệu ứng trước", "Các hiệu ứng tiếp theo",
                      "Tất cả hiệu ứng và tùy chọn", "Tất cả hiệu ứng"):
            self.assertIn(f'msgstr "{label}"', po)
        po = added(STRINGS, "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po")
        self.assertIn('msgid "Animation Styles"\nmsgstr "Hiệu ứng hoạt hình"', po)
        self.assertIn('msgid "Applies an animation to the selected objects"\n'
                      'msgstr "Áp dụng hiệu ứng hoạt hình cho các đối tượng đã chọn"', po)


if __name__ == "__main__":
    unittest.main()
