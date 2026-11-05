# SPDX-License-Identifier: AGPL-3.0-only
"""A VBA UserForm with the common controls, as the HST editor stores it (for the runtime checks)."""
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "extensions/hst-vietnamese-tools/python"))
from hst_office import vba  # noqa: E402
from hst_office.vba_template import OPTION_LINE  # noqa: E402

NS = "{http://openoffice.org/2000/dialog}"
BODY = """
<dlg:button dlg:id="CommandButton1" dlg:tab-index="0" dlg:left="10" dlg:top="8" dlg:width="60" dlg:height="14" dlg:value="Bấm tôi"/>
<dlg:text dlg:id="Label1" dlg:tab-index="1" dlg:left="80" dlg:top="8" dlg:width="60" dlg:height="10" dlg:value="Nhãn tiếng Việt"/>
<dlg:textfield dlg:id="TextBox1" dlg:tab-index="2" dlg:left="10" dlg:top="28" dlg:width="80" dlg:height="14" dlg:value="nội dung"/>
<dlg:checkbox dlg:id="CheckBox1" dlg:tab-index="3" dlg:left="100" dlg:top="28" dlg:width="60" dlg:height="10" dlg:checked="true" dlg:value="Chọn"/>
<dlg:radiogroup>
<dlg:radio dlg:id="OptionButton1" dlg:tab-index="4" dlg:left="10" dlg:top="48" dlg:width="50" dlg:height="10" dlg:checked="true" dlg:value="Một"/>
<dlg:radio dlg:id="OptionButton2" dlg:tab-index="5" dlg:left="70" dlg:top="48" dlg:width="50" dlg:height="10" dlg:value="Hai"/>
</dlg:radiogroup>
<dlg:combobox dlg:id="ComboBox1" dlg:tab-index="6" dlg:left="10" dlg:top="64" dlg:width="80" dlg:height="14" dlg:spin="true" dlg:value="giá trị"/>
<dlg:menulist dlg:id="ListBox1" dlg:tab-index="7" dlg:left="100" dlg:top="64" dlg:width="80" dlg:height="30"/>
<dlg:titledbox dlg:id="Frame1" dlg:tab-index="8" dlg:left="10" dlg:top="100" dlg:width="170" dlg:height="50"><dlg:title dlg:value="Khung"/></dlg:titledbox>
<dlg:button dlg:id="CommandButton2" dlg:tab-index="9" dlg:left="20" dlg:top="120" dlg:width="60" dlg:height="14" dlg:value="Trong khung"/>
"""
EXTRA = '<dlg:img dlg:id="Image1" dlg:tab-index="10" dlg:left="190" dlg:top="8" dlg:width="20" dlg:height="20"/>\n'
SHOW_CODE = OPTION_LINE + '\nSub ShowForm()\n  UserForm1.Show\nEnd Sub\n'
# A literal compared with text that did not pass through the code page: the control label is UTF-16 in
# the file, the literal and the caption are Windows-1258.
COMPOSED_CODE = ('\nFunction SameText()\n  SameText = (UserForm1.Label1.Caption = "Nhãn tiếng Việt") '
                 '& "|" & (UserForm1.Caption = "Biểu mẫu HST") & "|" & (Len("Việt") = 4)\n  Unload UserForm1\nEnd Function\n')
CODE = OPTION_LINE + COMPOSED_CODE + '\nFunction DocForm()\n  DocForm = UserForm1.Caption & "|" & UserForm1.TextBox1.Text & "|" & UserForm1.Label1.Caption\n  Unload UserForm1\nEnd Function\n'
CLICK_TARGET = {"calc": 'Worksheets(1).Range("A1").Value', "writer": "ActiveDocument.Content.Text"}


def form_code(app):
    """The click handler the help page promises: it reads a control and writes to the document."""
    return ('Rem Attribute VBA_ModuleType=VBAFormModule\n' + OPTION_LINE
            + '\nPrivate Sub CommandButton1_Click()\n  ' + CLICK_TARGET[app]
            + ' = "đã bấm: " & TextBox1.Text\n  Unload Me\nEnd Sub\n')


def dialog_xml(body):
    return ('<?xml version="1.0" encoding="UTF-8"?><dlg:window xmlns:dlg="http://openoffice.org/2000/dialog" '
            'xmlns:script="http://openoffice.org/2000/script" dlg:id="UserForm1" dlg:left="60" dlg:top="60" dlg:width="230" '
            'dlg:height="170" dlg:closeable="true" dlg:moveable="true" dlg:title="Biểu mẫu HST"><dlg:bulletinboard>'
            + body + '</dlg:bulletinboard></dlg:window>').encode("utf-8")


def add_form(ctx, doc, app, body):
    """The form as the editor stores it: a dialog plus a FORM module of the same name."""
    import uno
    import unohelper
    from com.sun.star.io import XInputStreamProvider
    library_name = vba.prepare_document(doc, app)[0]
    data = dialog_xml(body)

    class Provider(unohelper.Base, XInputStreamProvider):
        def createInputStream(self):
            stream = ctx.ServiceManager.createInstanceWithContext("com.sun.star.io.SequenceInputStream", ctx)
            stream.initialize((uno.ByteSequence(data),))
            return stream
    dialogs = doc.DialogLibraries
    if not dialogs.hasByName(library_name):
        dialogs.createLibrary(library_name)
    dialogs.loadLibrary(library_name)
    # the container checks the Any's exact type, which a plain Python object does not carry
    uno.invoke(dialogs.getByName(library_name), "insertByName",
               ("UserForm1", uno.Any("com.sun.star.io.XInputStreamProvider", Provider())))
    library = doc.BasicLibraries.getByName(library_name)
    info = uno.createUnoStruct("com.sun.star.script.ModuleInfo")
    info.ModuleType, info.ModuleObject = 3, doc
    library.insertModuleInfo("UserForm1", info)
    library.insertByName("UserForm1", form_code(app))
    vba.add_module(library, "HstForms", CODE + SHOW_CODE.split("\n", 1)[1])


def read_dialog(doc, project):
    dialogs = doc.DialogLibraries
    if not dialogs.hasByName(project):
        return None
    dialogs.loadLibrary(project)
    if not dialogs.getByName(project).hasByName("UserForm1"):
        return None
    stream = dialogs.getByName(project).getByName("UserForm1").createInputStream()
    data = b""
    while True:
        count, chunk = stream.readBytes(None, 65536)
        data += bytes(chunk)
        if count < 65536:
            return data


def controls_of(xml):
    """{name: properties} with absolute positions, and the form caption. The importer turns a group box
    into a frame that contains its controls at positions relative to it: both count as "frame"."""
    out = {}

    def walk(element, base_x, base_y):
        for child in element:
            name = child.get(NS + "id")
            tag = child.tag.replace(NS, "")
            if not name or name.startswith("DummyGroupSep"):
                walk(child, base_x, base_y)  # bulletinboard, radiogroup
                continue
            title = child.find(NS + "title")
            box = [int(child.get(NS + k, "0")) for k in ("left", "top", "width", "height")]
            box[0] += base_x
            box[1] += base_y
            out[name] = dict(tag="frame" if tag == "titledbox" else tag, checked=child.get(NS + "checked"), box=tuple(box),
                             value=child.get(NS + "value") if title is None else title.get(NS + "value"))
            nested = tag == "frame"
            walk(child, box[0] if nested else base_x, box[1] if nested else base_y)
    root = ET.fromstring(xml)
    walk(root, 0, 0)
    return out, root.get(NS + "title")
