# SPDX-License-Identifier: AGPL-3.0-only
"""The HST Draw edits of the ribbon rework (generate-ribbon-ux-impress-draw.py); Draw's ribbon is the Slides one
(generate-draw-ribbon.py), so it shares the Trang đầu, Chèn, Xem lại, Xem and Phần mở rộng edits."""
import ribbon_ux_lib as L
from ribbon_ux_impress_draw_data import SNAP_TOGGLES, TRANSFORM_MENU
from ribbon_ux_impress_draw_edits import home_common, insert_shapes, review_view_extension_common


# --- HST Draw ----------------------------------------------------------------------------------------------

SLIDES_ONLY_DESCRIPTIONS = {
    ".uno:InsertPage", ".uno:AssignLayout", ".uno:ImportSlideFromFile", ".uno:SlideSetup", ".uno:HstApplyTransition",
    ".uno:HstApplyAnimation", ".uno:CustomAnimation", ".uno:Presentation", ".uno:PresentationCurrentSlide",
    ".uno:RehearseTimings", ".uno:HideSlide", ".uno:NormalMultiPaneGUI", ".uno:DiaMode", ".uno:SlideMasterPage"}


def edit_draw(b):
    # Trang đầu: "Sửa PDF" first; the shapes stay in the vertical drawing bar and Chèn ▸ Hình dạng ▾
    b.take("btnHstBasicShapes1", "btnHstArrowShapes2", "btnLayoutToggleObjectRotateMode", "btnHstShapeShadow")
    home_common(b, shapes=False)
    pdf = b.new_group("gdHomeHstPdfEdit", "lbHomeHstPdfEdit", "lbHomeHstPdfEdit", [
        ("L", [b.button("btnHstPdfEditText", ".uno:Text", "text_box")]),
        ("L", [b.button("btnHstPdfEditImage", ".uno:InsertGraphic", "image")]),
        ("S", [b.button("btnHstPdfEditRedact", ".uno:RedactDoc", "redact")],
         [b.button("btnHstPdfEditExport", ".uno:ExportDirectToPDF", "export_pdf")], "both-horiz")])
    b.insert_group("pmhbHome", pdf, first=True)

    # Chèn
    insert_shapes(b)
    for bid, key in (("btnInsertHstPageField", "page_number"), ("btnInsertHstDateField", "date"),
                     ("btnInsertHstTimeField", "time")):
        b.ribbon_label(bid, key)

    # Sắp xếp
    front, back, forward, backward = b.take("btnArrangeBringToFront", "btnArrangeSendToBack",
                                            "btnArrangeObjectForwardOne", "btnArrangeObjectBackOne")
    b.take("btnArrangeObjectAlignLeft", "btnArrangeAlignCenter", "btnArrangeObjectAlignRight", "btnArrangeAlignUp",
           "btnArrangeAlignMiddle", "btnArrangeAlignDown")  # in Căn chỉnh ▾
    b.refill("gdArrangePositioning", [
        ("L", [b.button("btnHstArrangeAlign", ".uno:ObjectAlign", "align", "GtkMenuToolButton")]),
        ("S", [front], [back], "both-horiz"), ("S", [forward], [backward], "icons")], "lbArrangePositioning")
    b.ribbon_label("btnArrangeBringToFront", "bring_front")
    b.ribbon_label("btnArrangeSendToBack", "send_back")
    transform, mode, rotate, flip_v, flip_h = b.take(
        "btnArrangeTransformDialog", "btnArrangeToggleObjectBezierMode", "btnArrangeToggleObjectRotateMode",
        "btnArrangeFlipVertical", "btnArrangeFlipHorizontal")
    b.take("btnArrangeShear", "btnArrangeCrookSlant")  # in Biến đổi ▾
    b.menu("Menu HstTransform", "MenuHstTransform-", TRANSFORM_MENU)
    b.refill("gdArrange", [
        ("L", [transform]), ("S", [mode, rotate], [flip_v, flip_h], "icons"),
        ("S", b.menu_button("btnHstArrangeTransform", "Menu HstTransform", "transform"), None, None)])
    b.caption("lbArrangeCombination", "lbArrangeCombination")
    b.ribbon_label("btnArrangeCombine", "combine_shapes")
    b.ribbon_label("btnArrangeMerge", "merge_shapes")

    # PDF
    b.caption("ExportLabel", "ExportLabel")
    direct, options, image = b.take("btnExportDirectToPDF", "btnExportToPDF", "btnExportExportTo")
    b.refill("gdExportPdf", [("L", [direct]), ("S", [options], [image], "both-horiz")], "lbExportPdf")
    for bid, key in (("btnExportDirectToPDF", "export_pdf"), ("btnExportToPDF", "pdf_options"),
                     ("btnExportExportTo", "export_image"), ("btnExportSignPDF", "sign_pdf"),
                     ("btnExportSignature", "doc_signatures")):
        b.ribbon_label(bid, key)
    b.caption("lbExportSign", "lbExportSign")

    # Trang: Xoay trang (HstRotatePage.cxx turns the selected pages with their content)
    left = b.button("btnHstPageRotateLeft", ".uno:HstRotatePageLeft")
    right = b.button("btnHstPageRotateRight", ".uno:HstRotatePageRight")
    L.set_prop(left.find("object"), "icon-name", "cmd/lc_rotateleft.png")
    L.set_prop(right.find("object"), "icon-name", "cmd/lc_rotateright.png")
    b.insert_group("pmhbPage", b.new_group("gdPageHstRotate", "lbPageHstRotate", "lbPageHstRotate",
                                           [("S", [left], [right], "both-horiz")]), after="gdPageSetup")

    # Xem lại, Xem, Phần mở rộng
    review_view_extension_common(b)
    b.caption("lbViewMode", "lbViewModeDraw")
    for bid, key in (("btnViewPageMode", "normal"), ("btnViewMasterPage", "master_page"),
                     ("btnViewLeftPaneImpress", "page_pane")):
        b.ribbon_label(bid, key)
    snaps = [o.get("id") for o in L.find(b.root, "gdViewGrid").iter("object")
             if L.prop(o, "action-name") in SNAP_TOGGLES]
    if len(snaps) != len(SNAP_TOGGLES):
        raise L.RibbonUxError(f"gdViewGrid: {len(snaps)} snap toggles")
    b.take(*snaps)
    b.menu("Menu HstSnap", "MenuHstSnap-", SNAP_TOGGLES, klass="GtkCheckMenuItem")
    b.image("imgHstSnap", "cmd/32/snapborder.png")
    b.refill("gdViewGrid", [("L", b.menu_button("btnHstViewSnap", "Menu HstSnap", "snap", "imgHstSnap"))],
             "lbViewGrid")
    b.describe(skip=SLIDES_ONLY_DESCRIPTIONS)
