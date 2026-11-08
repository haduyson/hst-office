# SPDX-License-Identifier: AGPL-3.0-only
"""Slides animations gallery: the contract of the effects, selection, undo and paging, and the gallery's
place on the Animation tab (hst-slides-animation-gallery.patch, hst-ribbon-animation-gallery-ui.patch).
Split from test_slides_animation_gallery.py, whose patch readers it shares; no build is needed."""
import os
from pathlib import Path
import re
import unittest

from _paths import ROOT
from test_slides_animation_gallery import APPLY, CXX, GALLERY, PLACEMENT, STRINGS, UI, added, sections


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

    def test_no_empty_undo_step_for_none(self):
        apply = added(GALLERY, APPLY)
        self.assertLess(apply.index("if (bNone && aRemove.empty())"), apply.index("AddUndoAction"))

    def test_late_status_never_reaches_a_disposed_window(self):
        # the toolbox can dispose the item window before its controller (the style box crash)
        cxx = added(GALLERY, CXX)
        status = cxx[cxx.index("void SAL_CALL statusChanged"):cxx.index("createItemWindow")]
        self.assertIn("if (!m_xWindow || m_xWindow->isDisposed())", status)
        self.assertLess(status.index("isDisposed()"), status.index("m_xWindow->Enable("))
        self.assertIn("m_aRefill.Stop();", cxx)
        self.assertIn("m_xWindow.disposeAndClear();", cxx)

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


class AnimationGalleryPlacement(unittest.TestCase):
    def test_gallery_leads_the_animation_group(self):
        ui = added(PLACEMENT, "sd/uiconfig/simpress/ui/notebookbar.ui")
        self.assertIn('id="btnHstAnimationGallery"', ui)
        self.assertIn("<property name=\"action-name\">.uno:HstApplyAnimation</property>", ui)
        self.assertIn("<property name=\"expand\">True</property>", ui)
        with open(PLACEMENT, encoding="utf-8") as handle:
            text = handle.read()
        # inserted right before the Custom Animation button of the Animations tab
        self.assertRegex(text, r"btnHstAnimationGallery[\s\S]*\n \s*<object class=\"GtkToolButton\" id=\"btnHstCustomAnimation7\">")
        self.assertEqual(sections(PLACEMENT)["sd/uiconfig/simpress/ui/notebookbar.ui"][1], [])

    def test_sanitizer_knows_the_label_less_item(self):
        suppr = added(PLACEMENT, "solenv/sanitizers/ui/modules/simpress.suppr")
        self.assertEqual(suppr, "sd/uiconfig/simpress/ui/notebookbar.ui://GtkToolButton[@id='btnHstAnimationGallery'] button-no-label\n")


if __name__ == "__main__":
    unittest.main()
