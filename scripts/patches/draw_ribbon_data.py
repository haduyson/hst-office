# SPDX-License-Identifier: AGPL-3.0-only
"""What generate-draw-ribbon.py builds: the files it changes, Draw's tabs, the groups and commands it keeps, drops
or adds, the HST look of a group, and the new strings."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMPRESS_UI = "sd/uiconfig/simpress/ui/notebookbar.ui"
DRAW_UI = "sd/uiconfig/sdraw/ui/notebookbar.ui"
DRAW_SUPPR = "solenv/sanitizers/ui/modules/sdraw.suppr"
IMPRESS_SUPPR = "solenv/sanitizers/ui/modules/simpress.suppr"
TOOLBAR_MODE = "officecfg/registry/data/org/openoffice/Office/UI/ToolbarMode.xcu"
VI_PO = "translations/source/vi/sd/messages.po"
OPEN_IN_HST_PDF = "org.hst.office.vi:OpenInHstPdf"

# Tab pages in Draw's order: the Slides tabs and the new Arrange, Page and Export.
# Xem comes last of the main tabs, after Xem lại, as in Writer, Sheets and Slides; the contextual tabs come
# after Phần mở rộng, so that showing one never pushes Trợ giúp and Phần mở rộng along the tab row.
TAB_ORDER = ["File", "Home Tab", "Insert", "Arrange", "Page", "Export", "Review", "View", "Help Tab", "Extension",
             "TableDesign", "Table", "Image", "ChartDesign", "ChartFormat", "Draw", "Object", "Media", "Form",
             "Master", "3D"]
# The right-hand block of a tab ("<tab> ▾" and a few icons, a sfxlo-DropdownBox) is left out: every command it
# holds is in the tab's groups or another tab. Phần mở rộng keeps its block: it lists the menus of installed
# extensions, which no group holds.
KEEP_TAB_BLOCKS = {"Extension-Menu"}
# Draw commands that only the dropped blocks' menus held, placed in groups: deleting and importing pages
# (Trang ▸ Trang), and the page, date, time and author fields (Chèn ▸ Trường, after Văn bản).
PAGES_GROUP = ("gdPagePages", "lbHomePage", (".uno:InsertPage", "btnPageInsertPage"),
               [(".uno:DuplicatePage", "btnPageDuplicatePage"), (".uno:DeletePage", "btnPageDeletePage"),
                (".uno:ImportFromFile", "btnPageImportFromFile")])
FIELDS_GROUP = ("gdInsertHstFields", "lbInsertHstFields", (".uno:InsertPageField", "btnInsertHstPageField"),
                [(".uno:InsertPagesField", "btnInsertHstPagesField"), (".uno:InsertDateFieldVar", "btnInsertHstDateField"),
                 (".uno:InsertTimeFieldVar", "btnInsertHstTimeField"), (".uno:InsertAuthorField", "btnInsertHstAuthorField")])
FIELDS_AFTER = "gdInsertText"
# Slides-only groups and commands (slides, layouts, transitions, header and footer, interaction).
DROP_GROUPS = {"gdHomeSlide", "gdInsertSlide", "gdViewMode", "gdViewMaster"}
# Slide show, slide views and animation (in the Tools block and the tab menus Draw takes from Slides); Draw has
# no slot for hiding a page either: HidePage/ShowPage of its own Layout tab never worked.
DROP_COMMANDS = {".uno:PhotoAlbumDialog", ".uno:AnimationEffects", ".uno:HeaderAndFooter", ".uno:SlideChangeWindow",
                 ".uno:PresentationCurrentSlide", ".uno:HideSlide", ".uno:ShowSlide", ".uno:HidePage", ".uno:ShowPage",
                 ".uno:Presentation", ".uno:PresentationDialog", ".uno:PresentationLayout", ".uno:PresentationMinimizer",
                 ".uno:RehearseTimings", ".uno:CustomShowDialog", ".uno:CustomAnimation", ".uno:AnimationObjects",
                 ".uno:NotesMode", ".uno:NotesMasterPage", ".uno:HandoutMode", ".uno:OutlineMode"}
# Slide commands of the Slides menus and groups, as Draw names them for pages.
SWAP_COMMANDS = {".uno:LeftPaneImpress": ".uno:LeftPaneDraw", ".uno:InsertSlide": ".uno:InsertPage",
                 ".uno:DuplicateSlide": ".uno:DuplicatePage", ".uno:DeleteSlide": ".uno:DeletePage",
                 ".uno:RenameSlide": ".uno:RenamePage", ".uno:MoveSlideUp": ".uno:MovePageUp",
                 ".uno:MoveSlideDown": ".uno:MovePageDown", ".uno:SlideSetup": ".uno:PageSetup",
                 ".uno:SlideMasterPage": ".uno:MasterPage", ".uno:InsertSlideField": ".uno:InsertPageField",
                 ".uno:InsertSlidesField": ".uno:InsertPagesField", ".uno:ImportSlideFromFile": ".uno:ImportFromFile",
                 ".uno:InsertSlideTitleField": ".uno:InsertPageTitleField"}
# Sắp xếp: the arrange groups of Shape Format, in Office's order (arrange and align, group, rotate).
ARRANGE_GROUPS = ["gdDrawPositioning", "gdDrawGrouping", "gdDraw", "gdDrawCombination"]
ARRANGE_DROP_COMMANDS = {".uno:FontworkGalleryFloater"}
# Shape Format's "Drawing Object" group holds rotation, flipping and slanting; on Sắp xếp it says so.
ARRANGE_ROTATE_GROUP = "gdArrange"
# Chèn's audio and video group: Draw's own string, in the suite's term "Đa phương tiện".
INSERT_MEDIA_GROUP = "gdInsertMedia"
# Trang: Draw's page groups (pages first, then page setup and background).
PAGE_GROUPS = [("gdHomePage", "gdPagePages"), ("gdLayoutFormat", "gdPageSetup"), ("gdLayoutPage", "gdPageOrder")]
PAGE_DROP_COMMANDS = {".uno:DrawingLayout"}
# The master view's page setup group is "Slide" in Slides; Draw has pages, so it takes Trang's caption.
MASTER_PAGE_GROUP = "gdMasterSlide"
# The look of the groups HST has redone in Writer, Sheets and Slides: an upright caption and margins 4/2.
# Every group of Draw's ribbon gets it, so no group keeps the older italic caption and margins 3/6.
HST_GROUP_GRID = (("margin-start", "4"), ("margin-end", "2"), ("margin-top", "6"), ("margin-bottom", "6"),
                  ("row-spacing", "3"), ("column-spacing", "4"))
HST_CAPTION_STYLE = "normal"

# New strings: (msgctxt, English msgid, Vietnamese msgstr).
STRINGS = [
    ("TabbedDraw|ArrangeTabLabel", "~Arrange", "~Sắp xếp"),
    ("TabbedDraw|PageTabLabel", "~Page", "Tra~ng"),
    ("TabbedDraw|ExportTabLabel", "Export/~PDF", "Xuất/P~DF"),
    ("TabbedDraw|labelPagePages", "Pages", "Trang"),
    ("TabbedDraw|labelPageSetup", "Page Setup", "Thiết lập trang"),
    ("TabbedDraw|labelPageOrder", "Order", "Thứ tự"),
    ("TabbedDraw|labelExportPdf", "PDF", "PDF"),
    ("TabbedDraw|labelExportSign", "Sign", "Ký số"),
    ("TabbedDraw|labelExportHstPdf", "HST PDF", "HST PDF"),
    ("TabbedDraw|labelInsertFields", "Fields", "Trường"),
    ("TabbedDraw|labelArrangeRotate", "Rotate and Flip", "Xoay và lật"),
    ("TabbedDraw|labelInsertMedia", "Media", "Đa phương tiện"),
]
BUTTON_CLASSES = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkMenuItem", "GtkRadioMenuItem",
                  "GtkCheckMenuItem")


class DrawRibbonError(Exception):
    pass


DESCRIPTION = """HST Office: HST Draw gets the HST ribbon, like Writer, Sheets and Slides (generated).

HST Draw is what "Chỉnh sửa bằng HST Draw" of HST PDF opens, so its ribbon is laid out for editing PDFs:
Tệp tin, Trang đầu, Chèn, Sắp xếp, Trang, Xuất/PDF, Xem lại, Xem, Trợ giúp, Phần mở rộng, then the
contextual tabs (Xem last of the main tabs, as in the other apps; a contextual tab never moves Trợ giúp).
No tab has the right-hand "<tab> ▾" block: its commands are all in the groups. Phần mở rộng keeps it, as it
lists the menus of installed extensions. Generated by scripts/patches/generate-draw-ribbon.py from the Slides ribbon of the series
(Draw and Slides share the sd code): the slide-only tabs (Thiết kế, Chuyển tiếp, Hiệu ứng, Trình chiếu,
Dàn ý), groups and commands are left out; Sắp xếp copies the arrange groups of Shape Format; Trang takes
Draw's own page groups; Xem uses Draw's view modes and page pane; Xuất/PDF holds Export as PDF, the PDF
signature and "Mở trong HST PDF" (org.hst.office.vi:OpenInHstPdf, hst-vietnamese-tools). The whole HST
engine (ladders, compact banner, tab search, keytips, launchers, accessibility groups) applies as is.
Every group has the look of the groups HST redid in the other apps (upright caption, margins 4/2), and
the master view's page group is "Thiết lập trang", not the slide caption of Slides.

- sd/uiconfig/sdraw/ui/notebookbar.ui: the new ribbon; solenv sdraw.suppr: its unlabelled buttons take
  their accessible name from their command.
- ToolbarMode.xcu: the ribbon is Draw's active UI mode, as hst-defaults.patch sets it for the other apps, and
  without the menu bar that upstream keeps in Draw's Tabbed mode only.
- translations/source/vi/sd/messages.po: the new strings.

License: these upstream files remain under their original license (MPL-2.0).
---
"""

