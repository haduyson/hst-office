# SPDX-License-Identifier: AGPL-3.0-only
"""The Slides and Draw edits of the ribbon rework (generate-ribbon-ux-impress-draw.py)."""
import ribbon_ux_lib as L
from ribbon_ux_impress_draw_data import ND30_LABEL, ND30_TOOLTIP, SELECT_MENU, SHAPE_MENU


# --- edits shared by both applications ---------------------------------------------------------------------

def home_common(b, shapes):
    """Trang đầu: Bản vẽ (with "Hình dạng ▾" when shapes), Chỉnh sửa after it; Find/Select All leave Đoạn văn."""
    replace, = b.take("btnHomeHstSearchDialog")
    b.take("btnHstSelectAll")  # in the Chọn ▾ menu
    arrange, align = b.take("btnLayoutObjectPosition", "btnLayoutObjectAlign")
    fill, line = b.take("btnHstShapeFill0", "btnHstShapeFill1")
    columns = []
    if shapes:
        b.menu("Menu HstShapes", "MenuHstShapes-", SHAPE_MENU)
        b.image("imgHstShapes", "cmd/32/basicshapes.diamond.png")
        columns.append(("L", b.menu_button("btnHstHomeShapes", "Menu HstShapes", "shapes", "imgHstShapes")))
    columns += [("S", [arrange], [align], "both-horiz"), ("S", [fill], [line], "both-horiz")]
    b.refill("gdHomeDrawing", columns, "lbHomeDrawing")
    for bid, key in (("btnLayoutObjectPosition", "arrange"), ("btnLayoutObjectAlign", "align"),
                     ("btnHstShapeFill0", "fill"), ("btnHstShapeFill1", "outline")):
        b.ribbon_label(bid, key)
    b.menu("Menu HstSelect", "MenuHstSelect-", SELECT_MENU)
    find = b.button("btnHstHomeFind", "vnd.sun.star.findbar:FocusToFindbar", "find")
    editing = b.new_group("gdHomeHstEditing", "lbHomeHstEditing", "lbHomeHstEditing",
                          [("S", [find], [replace], "both-horiz"),
                           ("S", b.menu_button("btnHstHomeSelect", "Menu HstSelect", "select"), None, None)])
    b.insert_group("pmhbHome", editing, after="gdHomeDrawing")
    b.ribbon_label("btnHomeHstSearchDialog", "replace")


def insert_shapes(b):
    """Chèn ▸ Minh họa: "Hình dạng ▾" and Biểu đồ in place of 23 shape icons."""
    chart, = b.take("btnInsertInsertObjectChart")
    b.menu("Menu HstInsertShapes", "MenuHstInsertShapes-", SHAPE_MENU)
    b.image("imgHstInsertShapes", "cmd/32/basicshapes.diamond.png")
    b.refill("gdInsertDrawingObjects", [
        ("L", b.menu_button("btnHstInsertShapes", "Menu HstInsertShapes", "shapes", "imgHstInsertShapes")),
        ("L", [chart])])


def review_view_extension_common(b):
    b.drop("bxReviewHyphenation")
    b.caption("lbReviewRedact", "lbReviewRedact")
    b.label_command(".uno:RedactDoc", "redact")
    b.drop("gdViewHstMacros")  # Macro lives in Phần mở rộng ▸ Nhà phát triển only
    b.caption("lbViewColor", "lbViewColor")
    b.label_command(".uno:OutputQualityGrayscale", "grayscale")
    b.label_command(".uno:InsertAVMedia", "audio_video")
    b.label_command(".uno:InsertObject", "other_object")
    # Phần mở rộng: Vietnamese utilities, other HST groups, then one developer group
    nd30 = L.find(b.root, "btnExtensionHstNd30")
    L.set_prop(nd30, "label", ND30_LABEL)
    L.set_prop(nd30, "tooltip-text", ND30_TOOLTIP)
    run, edit, manage, security = b.take("btnToolsRunMacro", "btnToolsMacroDialog", "btnToolsBasicIDEAppear",
                                         "btnHstMacroSecurity")
    controls = b.take("btnHstFormControls0", "btnHstFormControls1")
    design = b.take("btnHstDesignMode0", "btnHstDesignMode1")
    b.drop("gdToolsMacro", "gdExtensionHstControls")
    developer = b.new_group("gdExtensionHstDeveloper", "lbExtensionHstDeveloper", "lbExtensionHstDeveloper", [
        ("L", [run]), ("S", [edit], [manage], "both-horiz"), ("S", [security], None, "both-horiz"),
        ("S", controls, design, "icons")])
    b.insert_group("pmhbExtension", developer, after="gdExtensionHstAddins")
    for bid, key in (("btnToolsRunMacro", "run_macro"), ("btnToolsMacroDialog", "edit_macros"),
                     ("btnToolsBasicIDEAppear", "manage_macros"), ("btnHstMacroSecurity", "macro_security")):
        b.ribbon_label(bid, key)


# --- HST Slides --------------------------------------------------------------------------------------------

def edit_impress(b):
    # Trang đầu
    b.take("btnHomeInsertSlide", "btnHomeDuplicatePage", "btnHomePresentationLayout")
    b.refill("gdHomeSlide", [
        ("L", [b.button("btnHomeInsertSlide", ".uno:InsertPage", "new_slide", "GtkMenuToolButton")]),
        ("S", [b.button("btnHstHomeLayout", ".uno:AssignLayout", "layout", "GtkMenuToolButton")], None,
         "both-horiz")], "lbHomeSlide")
    home_common(b, shapes=True)
    b.drop("Home-Menu")

    # Chèn
    imported, = b.take("btnInsertImportSlideFromFile")
    b.take("btnInsertInsertSlide", "btnInsertDuplicatePage", "btnLayoutMoveSlideUp", "btnLayoutMoveSlideDown",
           "btnLayoutRenameSlide")
    b.refill("gdInsertSlide", [
        ("L", [b.button("btnInsertInsertSlide", ".uno:InsertPage", "new_slide", "GtkMenuToolButton")]),
        ("S", [imported], None, "both-horiz")], "lbInsertSlide")
    b.ribbon_label("btnInsertImportSlideFromFile", "from_file")
    insert_shapes(b)
    text, fontwork, vertical, header, other = b.take(
        "btnInsertText", "btnInsertFontworkGalleryFloater", "btnInsertVerticalText", "btnHstHeaderAndFooter4",
        "btnHstInsertObject")
    shape_type, same_height, align, spacing = b.take(
        "btnInsertFontworkShapeType", "btnInsertFontworkSameLetterHeights", "btnInsertFontworkAlignmentFloater",
        "btnInsertFontworkCharacterSpacingFloater")
    b.drop("gdInsertFontwork")
    b.refill("gdInsertText", [
        ("L", [text]), ("L", [fontwork]),
        ("S", [b.button("btnHstInsertSlideNumber", ".uno:InsertSlideField", "slide_number")],
         [b.button("btnHstInsertDateTime", ".uno:InsertDateAndTime", "date_time")], "both-horiz"),
        ("S", [header], [other], "both-horiz"),
        ("S", [vertical, shape_type, same_height], [align, spacing], "icons")], "lbInsertText")
    b.ribbon_label("btnInsertFontworkGalleryFloater", "fontwork")
    b.caption("lbInsertLinks", "lbInsertLinks")
    b.ribbon_label("btnHstInteraction", "interaction")
    b.drop("Insert-Menu")

    # Thiết kế
    b.expand_gallery("gdDesignTheme", "bxDesignThemeColorsPanel")
    L.packing(L.holder(b.root, L.find(b.root, "btnDesignThemeColorsPanel"))[0], "expand", "True")
    size, master, master_bg, master_obj = b.take("btnHstSlideSetup5", "btnLayoutPresentationLayout",
                                                 "btnLayoutDisplayMasterBackground", "btnLayoutDisplayMasterObjects")
    b.refill("gdDesignCustomize", [
        ("L", [size]),
        ("L", [b.button("btnHstDesignBackground", ".uno:SidebarDeck.PropertyDeck", "format_background")]),
        ("S", [master], [master_bg], "both-horiz"), ("S", [master_obj], None, "both-horiz")], "lbDesignCustomize")
    for bid, key in (("btnHstSlideSetup5", "slide_size"), ("btnLayoutPresentationLayout", "change_master"),
                     ("btnLayoutDisplayMasterBackground", "master_background"),
                     ("btnLayoutDisplayMasterObjects", "master_objects")):
        b.ribbon_label(bid, key)
    b.drop("Layout-Menu")

    # Chuyển tiếp, Hiệu ứng
    b.expand_gallery("gdTransitionsSlide", "bxHstSlideChangeWindow6")
    b.ribbon_label("btnHstSlideChangeWindow6", "transition_pane")
    b.expand_gallery("gdAnimationsMain", "bxHstCustomAnimation7")
    L.packing(L.holder(b.root, L.find(b.root, "btnHstAnimationGallery"))[0], "expand", "True")
    b.drop("bxHstAnimationEffects8")  # Tương tác: Chèn ▸ Liên kết
    b.ribbon_label("btnHstCustomAnimation7", "animation_pane")
    effect_buttons(b)

    # Trình chiếu
    first, current, custom = b.take("btnShowPresentation", "btnShowPresentationCurrentSlide",
                                    "btnShowCustomShowDialog")
    b.refill("gdShowSlide", [("L", [first]), ("L", [current]), ("S", [custom], None, "both-horiz")])
    setup, rehearse, hide, show = b.take("btnShowPresentationDialog", "btnShowRehearseTimings", "btnLayoutHideSlide",
                                         "btnLayoutShowSlide")
    b.take("btnShowPresentationMinimizer")  # Tools menu ▸ Nén bản trình chiếu
    b.refill("gdShowSettings", [("L", [setup]), ("L", [rehearse]), ("S", [hide], [show], "both-horiz")])
    for bid, key in (("btnShowPresentation", "from_beginning"), ("btnShowPresentationCurrentSlide", "from_current"),
                     ("btnShowRehearseTimings", "rehearse")):
        b.ribbon_label(bid, key)
    b.drop("Slideshow-Menu")

    # Xem lại, Xem, Phần mở rộng
    review_view_extension_common(b)
    b.drop("Reference-Menu", "View-Menu")
    b.drop("bxViewToggleTabBarVisibility")  # View menu ▸ Thanh thẻ khung xem (Draw's menu bar lacks it: kept there)
    # the View block's Zoom dialog joins the Thu phóng group
    L.insert_child(L.find(b.root, "bxViewZoomMode"), b.button("btnHstViewZoom", ".uno:Zoom"))
    b.caption("lbViewMode", "lbViewModeImpress")
    b.caption("lbViewMaster", "lbViewMaster")
    for bid, key in (("btnViewNormalMultiPaneGUI", "normal"), ("btnViewDiaMode", "slide_sorter"),
                     ("btnViewNotesMode", "notes_page"), ("btnViewOutlineMode", "outline_view"),
                     ("btnViewSlideMasterPage", "slide_master"), ("btnViewNotesMasterPage", "notes_master"),
                     ("btnViewHandoutMode", "handout_master")):
        b.ribbon_label(bid, key)

    # contextual tabs: no trailing blocks; the Slides commands found only there join a captioned group (the
    # Writer-only table and frame commands of the copied menus do nothing in Slides and are left out)
    b.drop("Image-Menu", "Media-Menu", "Outline-Menu", "Table-Menu", "Draw-Menu", "Object-Menu")
    for box, command in (("bxTable", ".uno:TableSort"), ("bxTable", ".uno:TableDialog"),
                         ("bxDrawAlignTop", ".uno:EqualizeWidth"), ("bxDrawAlignBottom", ".uno:EqualizeHeight"),
                         ("bxDrawCombineTop", ".uno:Connect"), ("bxDrawCombineBottom", ".uno:Break"),
                         ("bxDrawCombineBottom", ".uno:Morphing")):
        L.insert_child(L.find(b.root, box), b.button("btnHstCtx" + command.split(":")[1], command))
    b.describe(skip={".uno:ExportTo", ".uno:PageMode", ".uno:MasterPage"})


def effect_buttons(b):
    """Chuyển tiếp: Xem trước and the gallery, then a Thời gian group (Thời lượng, Tự chuyển sau, Áp dụng cho tất
    cả); Hiệu ứng: Xem trước first."""
    for box, bid, command in (("bxHstSlideChangeWindow6", "btnHstTransitionPreview", ".uno:HstPreviewTransition"),
                              ("bxHstCustomAnimation7", "btnHstAnimationPreview", ".uno:HstPreviewAnimation")):
        hold = b.button(bid, command)
        L.set_prop(hold.find("object"), "icon-name", "cmd/32/runbasic.png")
        L.packing(hold, "homogeneous", "False")
        L.insert_child(L.find(b.root, box), hold, 0)
    apply_all = b.button("btnHstTransitionApplyAll", ".uno:HstApplyTransitionToAll")
    L.set_prop(apply_all.find("object"), "icon-name", "cmd/lc_copyobjects.png")
    timing = b.new_group("gdTransitionsHstTiming", "lbTransitionsHstTiming", "lbTransitionsHstTiming", [
        ("S", [b.button("btnHstTransitionDuration", ".uno:HstSetTransitionDuration")],
         [b.button("btnHstTransitionAdvance", ".uno:HstSetTransitionAdvance")], "both-horiz"),
        ("S", [apply_all], None, "both-horiz")])
    b.insert_group("pmhbTransitions", timing, after="gdTransitionsSlide")
