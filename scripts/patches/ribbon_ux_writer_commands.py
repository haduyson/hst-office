# SPDX-License-Identifier: AGPL-3.0-only
"""The split buttons of the Writer ribbon UX rework (generate-ribbon-ux-writer.py), as the Sheets "Định dạng ngày
tháng" button of hst-ribbon-extensions-tab.patch: a Writer-only Controller.xcu node gives the command a
GenericPopupToolbarController whose arrow opens a popup menu file of sw/uiconfig/swriter/popupmenu. A click on the
button still runs its own command. Labels of the popup entries are Vietnamese in every UI language, as in the
HST menu and the other HST popup menus."""
import ribbon_ux_lib as lib

CONTROLLER = "officecfg/registry/data/org/openoffice/Office/UI/Controller.xcu"
MAKEFILE = "sw/UIConfig_swriter.mk"
POPUP_DIR = "sw/uiconfig/swriter/popupmenu/"
CONTROLLER_ANCHOR = '    </node>\n    <node oor:name="StatusBar">\n'
MAKEFILE_ANCHOR = "\tsw/uiconfig/swriter/popupmenu/insertfield \\\n"

# node name, command, popup file, comment, entries (command, label)
SPLIT_BUTTONS = [
    ("HstWriterPasteSplitButton", ".uno:Paste", "hstpaste",
     '"Dán" of the Writer ribbon: the arrow offers plain text and Paste Special instead of the clipboard formats.',
     [(".uno:PasteUnformatted", "Chỉ dán văn bản"), (".uno:PasteSpecial", "Dán đặc biệt")]),
    ("HstWriterCitationInsertSplitButton", "org.hst.office.vi:CitationInsert", "hstcitationinsert",
     '"Chèn trích dẫn" of the Writer ribbon (Tham khảo ▸ Trích dẫn): the arrow adds or imports a source in the\n'
     '           source manager, or inserts the last citation again.',
     [("org.hst.office.vi:CitationLibrary", "Thêm nguồn mới"),
      ("org.hst.office.vi:CitationLibrary", "Nhập từ tệp"),
      ("org.hst.office.vi:CitationReinsert", "Chèn lại trích dẫn")]),
]

POPUP_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!--
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
-->
"""


def xml_escape(text):
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def node(name, command, popup, comment):
    return (f"      <!-- HST Office: {comment} -->\n"
            f'      <node oor:name="{name}" oor:op="replace">\n'
            f'        <prop oor:name="Command">\n          <value>{xml_escape(command)}</value>\n        </prop>\n'
            '        <prop oor:name="Module">\n          <value>com.sun.star.text.TextDocument</value>\n        </prop>\n'
            '        <prop oor:name="Controller">\n'
            '          <value>com.sun.star.comp.framework.GenericPopupToolbarController</value>\n        </prop>\n'
            f'        <prop oor:name="Value">\n          <value>private:resource/popupmenu/{popup}</value>\n'
            '        </prop>\n      </node>\n')


def popup_file(comment, entries):
    lines = [POPUP_HEAD, f"<!-- HST Office: {comment} -->\n",
             '<menu:menupopup xmlns:menu="http://openoffice.org/2001/menu">\n']
    lines += [f'  <menu:menuitem menu:id="{xml_escape(c)}" menu:label="{xml_escape(label)}"/>\n'
              for c, label in entries]
    lines.append("</menu:menupopup>\n")
    return "".join(lines)


def insert_once(text, anchor, addition, path):
    if text.count(anchor) != 1:
        raise lib.RibbonUxError(f"{path}: anchor found {text.count(anchor)} times")
    at = text.index(anchor)
    return text[:at] + addition + text[at:]


def diffs(tree):
    """The hunks of the split buttons: Controller.xcu, the makefile and the new popup menu files."""
    controller = lib.read(tree, CONTROLLER)
    nodes = "".join(node(name, command, popup, comment) for name, command, popup, comment, _e in SPLIT_BUTTONS)
    out = [lib.file_diff(CONTROLLER, controller, insert_once(controller, CONTROLLER_ANCHOR, nodes, CONTROLLER))]
    makefile = lib.read(tree, MAKEFILE)
    lines = "".join(sorted(f"\t{POPUP_DIR}{popup} \\\n" for _n, _c, popup, _m, _e in SPLIT_BUTTONS))
    out.append(lib.file_diff(MAKEFILE, makefile, insert_once(makefile, MAKEFILE_ANCHOR, lines, MAKEFILE)))
    for _name, _command, popup, comment, entries in SPLIT_BUTTONS:
        path = f"{POPUP_DIR}{popup}.xml"
        out.append(lib.file_diff(path, "", popup_file(comment.replace("\n           ", " "), entries)))
    return out
