# SPDX-License-Identifier: AGPL-3.0-only
"""C++ and dialog edits of the Writer ribbon UX rework (generate-ribbon-ux-writer.py, written into
hst-ribbon-ux-writer-commands.patch):
- "Viền trang": .uno:BorderDialog takes an optional Page argument (FN_PARAM_1) naming the first tab of the
  Borders and Shading dialog (hst-dlg-borders.patch); the ribbon opens it on "hstpageborder".
- Lề ▾: the margin popup offers "Văn bản hành chính" (Decree 30/2020/ND-CP: left 3 cm, right 1.5 cm, top and
  bottom 2 cm) after its presets.
Each edit is (old, new) on the file's text; old must occur once. Files the series does not touch are read from the
pinned tarball when the tree lacks them."""
import os
import subprocess
import tempfile

import ribbon_ux_lib as lib

TARBALL = "libreoffice-26.8.1.1.tar.xz"
PREFIX = "libreoffice-26.8.1.1/"
ND30_PO = ("pagemargincontrol|hstnd30", "Administrative Document", "Văn bản hành chính")
SET_END = "                FN_FORMAT_BACKGROUND_DLG, FN_FORMAT_BACKGROUND_DLG>(rSh.GetAttrPool()));\n"
BACKGROUND = "                aSet.Put(SfxBoolItem(FN_FORMAT_BACKGROUND_DLG, true));\n"
SHADING = '        SetCurPageId(u"shading"_ustr);\n}\n'
MARGIN_DIR = "sw/source/uibase/sidebar/"
ND30_BUTTON = """        <child>
          <!-- HST Office: the margins of Vietnamese administrative documents (Decree 30/2020/ND-CP) -->
          <object class="GtkButton" id="hstnd30">
            <property name="label" translatable="yes" context="pagemargincontrol|hstnd30">Administrative Document</property>
            <property name="can-focus">True</property>
            <property name="receives-default">True</property>
            <property name="image">hstnd30Img</property>
            <property name="relief">none</property>
            <property name="use-underline">True</property>
            <property name="xalign">0</property>
            <property name="always-show-image">True</property>
          </object>
          <packing>
            <property name="expand">False</property>
            <property name="fill">True</property>
            <property name="position">10</property>
          </packing>
        </child>
"""
ND30_IMAGE = """  <object class="GtkImage" id="hstnd30Img">
    <property name="visible">True</property>
    <property name="can-focus">False</property>
    <property name="icon-name">sw/res/sidebar/pageproppanel/format_L_nomal_24x24.png</property>
  </object>
"""
POSITION = '\n            <property name="position">{}</property>'
ND30_TIP = """
    SetMetricValue( *m_xWidthHeightField, SWPAGE_HST_ND30_LEFT, m_eUnit );
    aHelpText = aLeft + m_xWidthHeightField->get_text();
    SetMetricValue( *m_xWidthHeightField, SWPAGE_HST_ND30_RIGHT, m_eUnit );
    aHelpText += aRight + m_xWidthHeightField->get_text();
    SetMetricValue( *m_xWidthHeightField, SWPAGE_HST_ND30_TOP_BOTTOM, m_eUnit );
    aHelpText += aTop + m_xWidthHeightField->get_text() + aBottom + m_xWidthHeightField->get_text();
    m_xHstNd30->set_tooltip_text( aHelpText );
"""
ND30_SELECT = """    if( &rControl == m_xHstNd30.get() )
    {
        m_nPageLeftMargin = SWPAGE_HST_ND30_LEFT;
        m_nPageRightMargin = SWPAGE_HST_ND30_RIGHT;
        m_nPageTopMargin = SWPAGE_HST_ND30_TOP_BOTTOM;
        m_nPageBottomMargin = SWPAGE_HST_ND30_TOP_BOTTOM;
        bMirrored = false;
    }
"""
ND30_VALUES = """// HST: Decree 30/2020/ND-CP margins in twips: left 3 cm, right 1.5 cm, top and bottom 2 cm
constexpr tools::Long SWPAGE_HST_ND30_LEFT = o3tl::toTwips(30, o3tl::Length::mm);
constexpr tools::Long SWPAGE_HST_ND30_RIGHT = o3tl::toTwips(15, o3tl::Length::mm);
constexpr tools::Long SWPAGE_HST_ND30_TOP_BOTTOM = o3tl::toTwips(20, o3tl::Length::mm);
"""
LAST_LINK = "    m_xLast->connect_clicked( LINK( this, PageMarginControl, SelectMarginHdl ) );\n"

EDITS = [
    ("sw/sdi/swriter.sdi", [("SfxVoidItem BorderDialog FN_FORMAT_BORDER_DLG\n()",
                             "SfxVoidItem BorderDialog FN_FORMAT_BORDER_DLG\n(SfxStringItem Page FN_PARAM_1)")]),
    ("sw/source/uibase/shells/basesh.cxx", [
        (SET_END, SET_END.replace(">(rSh", ",\n                FN_PARAM_1, FN_PARAM_1>(rSh")),
        (BACKGROUND, BACKGROUND
         + '            // HST: .uno:BorderDialog?Page:string=hstpageborder (ribbon "Viền trang") opens on that tab\n'
         + "            if (const SfxStringItem* pPage = rReq.GetArg<SfxStringItem>(FN_PARAM_1))\n"
         + "                aSet.Put(SfxStringItem(FN_PARAM_1, pPage->GetValue()));\n")]),
    ("sw/source/ui/frmdlg/uiborder.cxx", [
        ("#include <svl/intitem.hxx>\n", "#include <svl/intitem.hxx>\n#include <svl/stritem.hxx>\n"),
        (SHADING, SHADING[:-2]
         + '    // HST: the "Page" argument of .uno:BorderDialog names the first tab (the ribbon\'s "Viền trang")\n'
         + "    if (const SfxStringItem* pPage = rSet.GetItemIfSet(TypedWhichId<SfxStringItem>(FN_PARAM_1), false))\n"
         + "    {\n        const OUString& rPage = pPage->GetValue();\n"
         + '        if (rPage == "borders" || rPage == "hstpageborder" || rPage == "shading")\n'
         + "            SetCurPageId(rPage);\n    }\n}\n")]),
    (MARGIN_DIR + "PageMarginControl.hxx", [
        ("#define SWPAGE_WIDE_VALUE3     1800\n", "#define SWPAGE_WIDE_VALUE3     1800\n" + ND30_VALUES),
        ("    std::unique_ptr<weld::Button> m_xLast;\n", "    std::unique_ptr<weld::Button> m_xLast;\n"
         "    // HST: administrative documents (Decree 30/2020/ND-CP)\n"
         "    std::unique_ptr<weld::Button> m_xHstNd30;\n")]),
    (MARGIN_DIR + "PageMarginControl.cxx", [
        ('    , m_xMoreButton(m_xBuilder->weld_button(u"moreoptions"_ustr))\n',
         '    , m_xMoreButton(m_xBuilder->weld_button(u"moreoptions"_ustr))\n'
         '    , m_xHstNd30(m_xBuilder->weld_button(u"hstnd30"_ustr))\n'),
        ("    m_xLast->show();\n", "    m_xLast->show();\n    m_xHstNd30->show();\n"),
        (LAST_LINK, LAST_LINK + LAST_LINK.replace("m_xLast", "m_xHstNd30")),
        ("    m_xMirrored->set_tooltip_text( aHelpText );\n", "    m_xMirrored->set_tooltip_text( aHelpText );\n"
         + ND30_TIP),
        ("    if( &rControl == m_xLast.get() )\n", ND30_SELECT + "    if( &rControl == m_xLast.get() )\n")]),
    ("sw/uiconfig/swriter/ui/pagemargincontrol.ui", [
        (POSITION.format(12), POSITION.format(13)), (POSITION.format(11), POSITION.format(12)),
        (POSITION.format(10), POSITION.format(11)),
        (POSITION.format(9) + "\n          </packing>\n        </child>\n",
         POSITION.format(9) + "\n          </packing>\n        </child>\n" + ND30_BUTTON),
        ('  <object class="GtkImage" id="lastImg">\n', ND30_IMAGE + '  <object class="GtkImage" id="lastImg">\n')]),
]


def sources(tree, tarballs):
    """Text of every edited file: from the tree, else from the pinned tarball."""
    texts, missing = {}, []
    for path, _edits in EDITS:
        if os.path.exists(os.path.join(tree, path)):
            texts[path] = lib.read(tree, path)
        else:
            missing.append(path)
    if missing:
        tarball = os.path.join(tarballs, TARBALL)
        if not os.path.exists(tarball):
            raise lib.RibbonUxError(f"{', '.join(missing)}: not in the tree and no {tarball} (--tarballs)")
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["tar", "-xJf", tarball, "-C", tmp] + [PREFIX + p for p in missing], check=True)
            for path in missing:
                texts[path] = lib.read(os.path.join(tmp, PREFIX), path)
    return texts


def diffs(tree, tarballs):
    texts = sources(tree, tarballs)
    out = []
    for path, edits in EDITS:
        new = texts[path]
        for old, replacement in edits:
            if new.count(old) != 1:
                raise lib.RibbonUxError(f"{path}: {old.strip()[:60]!r} found {new.count(old)} times")
            new = new.replace(old, replacement)
        out.append(lib.file_diff(path, texts[path], new))
    return out
