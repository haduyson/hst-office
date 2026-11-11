# SPDX-License-Identifier: AGPL-3.0-only
"""Shared pieces of the VBA comparison corpus: the Kit module, the check DSL and the .xlsm/.docm packages.

Every case is a public Function in module `Cases` that runs a list of checks under `On Error Resume Next` and
returns one `key=value` line per check (value normalized by Kit.Fmt, or `ERR<number>`). The same file is run in
the reference suite (COM, Application.Run) and in HST Office (UNO script provider); the drivers compare lines.
Non-ASCII text is written as `U("H{e0} N{1ed9}i")` so the VBA source stays in code page 1252, as a file saved
by the reference suite on a Western Windows would be.
"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime", "vba-corpus"))
from vba_package import DOCX, XLSX  # noqa: E402
from vba_project_writer import vba_project  # noqa: E402

KIT = '''Public HstOut As String

Public Sub P(ByVal k As String, v As Variant, ByVal e As Long)
    If e <> 0 Then
        HstOut = HstOut & k & "=ERR" & e & vbLf
    Else
        HstOut = HstOut & k & "=" & Fmt(v) & vbLf
    End If
End Sub

Public Function Take() As String
    Take = HstOut
    HstOut = ""
End Function

Public Function Fmt(v As Variant) As String
    On Error GoTo bad
    If IsObject(v) Then Fmt = "<Object " & TypeName(v) & ">": Exit Function
    If IsArray(v) Then Fmt = "<Array " & LBound(v) & ".." & UBound(v) & ">": Exit Function
    Select Case VarType(v)
    Case vbEmpty: Fmt = "<Empty>"
    Case vbNull: Fmt = "<Null>"
    Case vbError: Fmt = "<" & CStr(v) & ">"
    Case vbDate
        Fmt = "Date:" & Year(v) & "-" & Month(v) & "-" & Day(v) & " " & Hour(v) & ":" & Minute(v) & ":" & Second(v)
    Case vbBoolean
        If v Then Fmt = "True" Else Fmt = "False"
    Case vbString
        Fmt = Replace(Replace(Replace(Replace(v, vbCr, "\\r"), vbLf, "\\n"), Chr(7), "\\a"), vbTab, "\\t")
    Case vbByte, vbInteger, vbLong, vbSingle, vbDouble, vbCurrency, vbDecimal
        Fmt = TypeName(v) & ":" & Trim(Str(v))
    Case Else
        Fmt = "<" & TypeName(v) & ">"
    End Select
    Exit Function
bad:
    Fmt = "<FmtErr" & Err.Number & ">"
End Function

Public Function U(ByVal s As String) As String
    Dim i As Long, j As Long, r As String
    i = 1
    Do While i <= Len(s)
        If Mid$(s, i, 1) = "{" Then
            j = InStr(i, s, "}")
            r = r & ChrW(CLng("&H" & Mid$(s, i + 1, j - i - 1)))
            i = j + 1
        Else
            r = r & Mid$(s, i, 1)
            i = i + 1
        End If
    Loop
    U = r
End Function
'''

DOC_BASE = {
    "ThisWorkbook": "0{00020819-0000-0000-C000-000000000046}",
    "Sheet1": "0{00020820-0000-0000-C000-000000000046}",
    "ThisDocument": "1Normal.ThisDocument",
}
DOC_ATTRS = ('Attribute VB_GlobalNameSpace = False\nAttribute VB_Creatable = False\nAttribute VB_PredeclaredId = True\n'
             'Attribute VB_Exposed = True\nAttribute VB_TemplateDerived = False\nAttribute VB_Customizable = True\n')


def vn(text):
    """VBA expression text for a Unicode string: `U("...")` with {hex} escapes, or a plain literal when ASCII."""
    if all(ord(c) < 128 for c in text):
        return '"' + text.replace('"', '""') + '"'
    return 'U("' + "".join(c if ord(c) < 128 and c not in '{}"' else "{%x}" % ord(c) for c in text) + '")'


def checks(name, entries, declare=""):
    """entries: ("key", "expr") records expr; ("!key", "stmt") records ok/ERR; ("#", "line") runs a setup line."""
    lines = [f"Public Function {name}() As String", "    Dim v As Variant", f"    {declare}" if declare else "",
             "    On Error Resume Next", "    HstOut = \"\""]
    for key, code in entries:
        if key == "#":
            lines.append("    " + code)
        elif key.startswith("!"):
            lines.append(f'    Err.Clear: {code}: P "{key[1:]}", "ok", Err.Number')
        else:
            lines.append(f'    Err.Clear: v = Empty: v = {code}: P "{key}", v, Err.Number')
    lines += [f"    {name} = Take()", "End Function", ""]
    return "\n".join(line for line in lines if line != "")


def function_names(source):
    return [line.split()[2].split("(")[0] for line in source.splitlines() if line.startswith("Public Function ")]


def document_module(name, code):
    return f'Attribute VB_Base = "{DOC_BASE[name]}"\n' + DOC_ATTRS + code


def with_documents(modules, names):
    """Real projects always hold the host's document modules; Word refuses a project without ThisDocument (5981)."""
    present = {name for name, _source in modules}
    return list(modules) + [(name, document_module(name, "")) for name in names if name not in present]


def xlsm(modules, codepage=1252):
    """Workbook with codeName attributes, so ThisWorkbook/Sheet1 document modules bind to the workbook and sheet."""
    modules = with_documents(modules, ("ThisWorkbook", "Sheet1"))
    names = {name for name, _source in modules}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        for part, text in XLSX.items():
            text = text.replace("{sheet}", "Sheet1")
            if part == "xl/workbook.xml" and "ThisWorkbook" in names:
                text = text.replace("<sheets>", '<workbookPr codeName="ThisWorkbook"/><sheets>')
            if part == "xl/worksheets/sheet1.xml" and "Sheet1" in names:
                text = text.replace("<sheetData/>", '<sheetPr codeName="Sheet1"/><sheetData/>')
            package.writestr(part, text)
        package.writestr("xl/vbaProject.bin", vba_project(modules, codepage))
    return buffer.getvalue()


PARAGRAPHS = ("Hello world. Second sentence.", "Next paragraph with world again.", "Last line")


def docm(modules, codepage=1252, paragraphs=PARAGRAPHS):
    modules = with_documents(modules, ("ThisDocument",))
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>' for text in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        for part, text in DOCX.items():
            package.writestr(part, text)
        package.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.'
                         'org/wordprocessingml/2006/main"><w:body>' + body + "</w:body></w:document>")
        package.writestr("word/vbaProject.bin", vba_project(modules, codepage, "Project"))
    return buffer.getvalue()
