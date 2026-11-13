# SPDX-License-Identifier: AGPL-3.0-only
"""More C++ edits of the Writer ribbon UX rework, in the form of ribbon_ux_writer_cxx.EDITS:
- .uno:HstDifferentFirstPage and .uno:HstDifferentOddEven: toggles of the current page style's shared first page
  and shared left/right header and footer (Đầu trang và chân trang ▸ Tùy chọn), one undo step each (ChgPageDesc);
- Dán ▾ in every application: the clipboard formats, then Chỉ dán văn bản and Dán đặc biệt;
- a double-click on a picture, shape, frame or object opens its contextual tab (hst-ribbon-ux-engine.patch)."""

DIFFERENT_FIRST = ("HstDifferentFirstPage", "FN_HST_DIFFERENT_FIRST_PAGE", "Different First Page", "Trang đầu khác")
DIFFERENT_ODD_EVEN = ("HstDifferentOddEven", "FN_HST_DIFFERENT_ODD_EVEN", "Different Odd and Even Pages",
                      "Trang chẵn lẻ khác")
UI_PO = "translations/source/vi/officecfg/registry/data/org/openoffice/Office/UI.po"
UI_PO_ANCHOR = 'msgstr "Loại bỏ định dạng đoạn văn"\n\n'
XCU_ANCHOR = '      <node oor:name=".uno:ResetAttributes" oor:op="replace">\n'
IDS = """#define FN_HST_RESET_PARAGRAPH      (FN_FORMAT + 16)
"""
SDI_ANCHOR = "SfxVoidItem HstResetParagraph FN_HST_RESET_PARAGRAPH\n"
EXECUTE_ANCHOR = "        case FN_UPDATE_ALL:\n            {\n                comphelper::EmbeddedObjectContainer&"
STATE_ANCHOR = "            case SID_GALLERY_ENABLE_ADDCOPY:\n"
DOUBLE_CLICK = ("                        /* This is no good: on the one hand GetSelectionType is used as flag field\n")
CLIP_RESULT = "        SfxUInt32Item aItem(SID_CLIPBOARD_FORMAT_ITEMS, sResult.toUInt32());\n"
CLIP_POPUP = "        ToolBox& rBox = GetToolBox();\n        ToolBoxItemId nId = GetId();\n        rBox.SetItemDown( nId, true );\n"


def slot(name, ident):
    return (f"SfxBoolItem {name} {ident}\n()\n[\n    AutoUpdate = TRUE,\n    FastCall = FALSE,\n"
            "    ReadOnlyDoc = FALSE,\n    Toggle = FALSE,\n    Container = FALSE,\n    RecordAbsolute = FALSE,\n"
            "    RecordPerSet;\n\n    AccelConfig = TRUE,\n    MenuConfig = TRUE,\n    ToolBoxConfig = TRUE,\n"
            "    GroupId = SfxGroupId::Format;\n]\n\n")


def node(name, label):
    return (f'      <node oor:name=".uno:{name}" oor:op="replace">\n'
            f'        <prop oor:name="Label" oor:type="xs:string">\n          <value xml:lang="en-US">{label}</value>\n'
            '        </prop>\n        <prop oor:name="Properties" oor:type="xs:int">\n          <value>1</value>\n'
            "        </prop>\n      </node>\n")


def po(name, label, vi):
    return (f'#. hstHF\n#: WriterCommands.xcu\nmsgctxt ""\n"WriterCommands.xcu\\n"\n'
            f'"..WriterCommands.UserInterface.Commands..uno:{name}\\n"\n"Label\\n"\n"value.text"\n'
            f'msgid "{label}"\nmsgstr "{vi}"\n\n')


COMMANDS = (DIFFERENT_FIRST, DIFFERENT_ODD_EVEN)
EXECUTE = """        case FN_HST_DIFFERENT_FIRST_PAGE:
        case FN_HST_DIFFERENT_ODD_EVEN:
        {
            // HST: "Trang đầu khác" / "Trang chẵn lẻ khác" of the header and footer tab: the current page
            // style gets its own first page, or its own left and right header and footer (one undo step)
            const size_t nDesc = rSh.GetCurPageDesc();
            SwPageDesc aDesc(rSh.GetPageDesc(nDesc));
            if (nSlot == FN_HST_DIFFERENT_FIRST_PAGE)
                aDesc.ChgFirstShare(!aDesc.IsFirstShared());
            else
            {
                const bool bShare = !aDesc.IsHeaderShared();
                aDesc.ChgHeaderShare(bShare);
                aDesc.ChgFooterShare(bShare);
            }
            rSh.ChgPageDesc(nDesc, aDesc);
            rReq.Done();
        }
        break;
"""
STATE = """            case FN_HST_DIFFERENT_FIRST_PAGE:
            case FN_HST_DIFFERENT_ODD_EVEN:
            {
                const SwPageDesc& rDesc = rSh.GetPageDesc(rSh.GetCurPageDesc());
                rSet.Put(SfxBoolItem(nWhich, nWhich == FN_HST_DIFFERENT_FIRST_PAGE ? !rDesc.IsFirstShared()
                                                                                   : !rDesc.IsHeaderShared()));
            }
            break;
"""
CLIP_ENTRIES = """        // HST: after the clipboard formats, plain text and Paste Special, as Office's Paste Options
        const OUString aUnformatted(u".uno:PasteUnformatted"_ustr), aSpecial(u".uno:PasteSpecial"_ustr);
        const auto lcl_Label = [this](const OUString& rCommand) {
            return vcl::CommandInfoProvider::GetLabelForCommand(
                vcl::CommandInfoProvider::GetCommandProperties(rCommand, m_sModuleName)).replaceAll("~", "");
        };
        xPopup->append_separator(u"hstseparator"_ustr);
        xPopup->append(aUnformatted, lcl_Label(aUnformatted));
        xPopup->append(aSpecial, lcl_Label(aSpecial));

"""
CLIP_DISPATCH = """        if (sResult == aUnformatted || sResult == aSpecial)
        {
            Dispatch(sResult, Sequence<PropertyValue>());
            GetToolBox().EndSelection();
            return;
        }
"""

EDITS = [
    ("sw/inc/cmdid.h", [(IDS, IDS + "// HST: the header and footer tab's Trang đầu khác and Trang chẵn lẻ khác\n"
                         "#define FN_HST_DIFFERENT_FIRST_PAGE (FN_FORMAT + 17)\n"
                         "#define FN_HST_DIFFERENT_ODD_EVEN   (FN_FORMAT + 18)\n")]),
    ("sw/sdi/swriter.sdi", [(SDI_ANCHOR, "".join(slot(n, i) for n, i, _l, _v in COMMANDS) + SDI_ANCHOR)]),
    ("sw/sdi/_basesh.sdi", [("    FN_UPDATE_ALL // status(final|play)\n",
                             "".join(f"    {i}\n    [\n        ExecMethod = Execute ;\n        StateMethod = GetState ;\n"
                                     '        DisableFlags="SfxDisableFlags::SwOnProtectedCursor";\n    ]\n\n'
                                     for _n, i, _l, _v in COMMANDS) + "    FN_UPDATE_ALL // status(final|play)\n")]),
    ("sw/source/uibase/shells/basesh.cxx", [(EXECUTE_ANCHOR, EXECUTE + "\n" + EXECUTE_ANCHOR),
                                            (STATE_ANCHOR, STATE + STATE_ANCHOR)]),
    ("officecfg/registry/data/org/openoffice/Office/UI/WriterCommands.xcu",
     [(XCU_ANCHOR, "".join(node(n, label) for n, _i, label, _v in COMMANDS) + XCU_ANCHOR)]),
    (UI_PO, [(UI_PO_ANCHOR, UI_PO_ANCHOR + "".join(po(n, label, vi) for n, _i, label, vi in COMMANDS))]),
    ("svx/source/mnuctrls/clipboardctl.cxx", [
        ("#include <vcl/svapp.hxx>\n", "#include <vcl/commandinfoprovider.hxx>\n#include <vcl/svapp.hxx>\n"),
        (CLIP_POPUP, CLIP_ENTRIES + CLIP_POPUP), (CLIP_RESULT, CLIP_DISPATCH + "\n" + CLIP_RESULT)]),
    ("sw/source/uibase/docvw/edtwin.cxx", [
        ("#include <vcl/dialoghelper.hxx>\n", "#include <vcl/HstRibbonContext.hxx>\n#include <vcl/dialoghelper.hxx>\n"),
        (DOUBLE_CLICK, "                            // HST: the double-click opens the object's contextual tab\n"
                       "                            hst::ribbon::OpenContextualTab(*this);\n" + DOUBLE_CLICK)]),
]
