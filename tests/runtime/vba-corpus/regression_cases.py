# SPDX-License-Identifier: AGPL-3.0-only
"""One regression case per fix found through the corpus. Each case is a VBA function that returns "OK" or what went wrong.

make_regression_fixtures.py stores them in real VBA projects (.xlsm, .docm) and check-vba-corpus-regression.py runs them in the sandbox.
"""

from regression_excel import CLASS_SHAPE, CLASS_SQUARE, CLASS_USE, CLASS_WATCH, COMPILE, TABLES
from regression_word import WORD_ONLY

CHECK = 'If {cond} Then {name} = "{what}": Exit Function\n'


def fails(name, *checks):
    """A function that returns OK unless one of (condition that means failure, label) holds."""
    body = "".join("    " + CHECK.format(cond=cond, name=name, what=what) for cond, what in checks)
    return f'Function {name}()\n{body}    {name} = "OK"\nEnd Function\n'


CALC_ONLY = "\n".join([
    fails("LibQualifiedCalls",
          ('VBA.Len("abc") <> 3', "VBA.Len"), ('VBA.Left$("abc", 1) <> "a"', "VBA.Left$"), ('VBA.Strings.Trim(" a ") <> "a"', "VBA.Strings.Trim"),
          ('Strings.UCase("a") <> "A"', "Strings.UCase"), ('Conversion.CLng("12") <> 12', "Conversion.CLng"), ('Information.IsEmpty(1)', "Information.IsEmpty"),
          ('Math.Abs(-2) <> 2', "Math.Abs"), ('DateTime.Year(DateSerial(2024, 1, 2)) <> 2024', "DateTime.Year")),
    fails("ChrAnsi",
          ('AscW(Chr(233)) <> 233', "Chr 233"), ('AscW(Chr(160)) <> 160', "Chr 160"), ('AscW(Chr(65)) <> 65', "Chr 65"), ('Chr(10) <> vbLf', "Chr 10")),
    'Function NewVbaCollection()\n    Dim c As New VBA.Collection\n    c.Add 5\n    NewVbaCollection = IIf(c.Count = 1, "OK", "count")\nEnd Function\n',
    # RegExp through CreateObject, as most files do, and with early binding
    '''Function RegExpBasics()
    Dim re As Object, ms As Object, m As Object, n As Long, joined As String
    Set re = CreateObject("VBScript.RegExp")
    re.Pattern = "(\\w+)@(\\w+)\\.vn"
    re.Global = True
    re.IgnoreCase = True
    If Not re.Test("Lien he: AN@HASON.VN") Then RegExpBasics = "Test": Exit Function
    Set ms = re.Execute("a@b.vn, c@d.vn")
    If ms.Count <> 2 Then RegExpBasics = "Count " & ms.Count: Exit Function
    If ms(1).Value <> "c@d.vn" Then RegExpBasics = "Item value": Exit Function
    If ms(0).FirstIndex <> 0 Or ms(1).FirstIndex <> 8 Or ms(0).Length <> 6 Then RegExpBasics = "index": Exit Function
    If ms(1).SubMatches(1) <> "d" Then RegExpBasics = "SubMatches": Exit Function
    For Each m In ms
        joined = joined & m.Value & ";"
    Next
    If joined <> "a@b.vn;c@d.vn;" Then RegExpBasics = "For Each " & joined: Exit Function
    If re.Replace("a@b.vn", "$2:$1") <> "b:a" Then RegExpBasics = "Replace " & re.Replace("a@b.vn", "$2:$1"): Exit Function
    re.Global = False
    If re.Replace("a@b.vn a@b.vn", "x") <> "x a@b.vn" Then RegExpBasics = "not global": Exit Function
    RegExpBasics = "OK"
End Function
''',
    '''Function RegExpEarlyBound()
    Dim re As New RegExp
    re.Pattern = "^\\d{3}$"
    RegExpEarlyBound = IIf(re.Test("123") And Not re.Test("12a"), "OK", "Test")
End Function
''',
    '''Function RegExpBadPattern()
    Dim re As Object
    Set re = CreateObject("VBScript.RegExp")
    re.Pattern = "("
    On Error Resume Next
    Dim b As Boolean
    b = re.Test("x")
    RegExpBadPattern = IIf(Err.Number = 5017, "OK", "Err " & Err.Number)
End Function
''',
    # FileSystemObject: the sandbox's private temporary folder
    '''Function FsoTextFile()
    Dim fso As Object, t As Object, p As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    p = fso.BuildPath(Environ("TMPDIR"), "hst fso.txt")
    Set t = fso.CreateTextFile(p, True)
    t.WriteLine "dong mot"
    t.Write "two"
    t.Close
    If Not fso.FileExists(p) Then FsoTextFile = "not created": Exit Function
    Set t = fso.OpenTextFile(p, 1)
    If t.ReadLine <> "dong mot" Then FsoTextFile = "ReadLine": Exit Function
    If t.AtEndOfStream Then FsoTextFile = "AtEnd early": Exit Function
    If t.ReadAll <> "two" Then FsoTextFile = "ReadAll": Exit Function
    If Not t.AtEndOfStream Then FsoTextFile = "AtEnd": Exit Function
    t.Close
    Set t = fso.OpenTextFile(p, 8)
    t.WriteLine "!"
    t.Close
    If fso.GetFile(p).Size <> 16 Then FsoTextFile = "Size " & fso.GetFile(p).Size: Exit Function
    fso.DeleteFile p
    FsoTextFile = IIf(fso.FileExists(p), "not deleted", "OK")
End Function
''',
    fails("FsoNames",
          ('CreateObject("Scripting.FileSystemObject").GetFileName("C:\\a\\b.xlsx") <> "b.xlsx"', "GetFileName"),
          ('CreateObject("Scripting.FileSystemObject").GetBaseName("/a/b.c.xlsx") <> "b.c"', "GetBaseName"),
          ('CreateObject("Scripting.FileSystemObject").GetExtensionName("b.XLSX") <> "XLSX"', "GetExtensionName"),
          ('CreateObject("Scripting.FileSystemObject").GetParentFolderName("C:\\a\\b.xlsx") <> "C:\\a"', "GetParentFolderName")),
    '''Function FsoFolders()
    Dim fso As New Scripting.FileSystemObject, d As String, f As Object, names As String, n As Long
    d = fso.BuildPath(Environ("TMPDIR"), "hstdir")
    If fso.FolderExists(d) Then fso.DeleteFolder d
    fso.CreateFolder d
    fso.CreateFolder d & "/sub"
    fso.CreateTextFile(d & "\\a.txt").Close
    fso.CopyFile d & "/a.txt", d & "/b.txt"
    fso.MoveFile d & "/b.txt", d & "/sub/c.txt"
    For Each f In fso.GetFolder(d).Files
        names = names & f.Name & ";"
    Next
    If names <> "a.txt;" Then FsoFolders = "Files " & names: Exit Function
    For Each f In fso.GetFolder(d).SubFolders
        n = n + f.Files.Count
    Next
    If n <> 1 Then FsoFolders = "SubFolders " & n: Exit Function
    fso.DeleteFolder d
    If fso.FolderExists(d) Then FsoFolders = "not deleted": Exit Function
    On Error Resume Next
    Dim x As Object
    Set x = fso.GetFile(d & "/none.txt")
    FsoFolders = IIf(Err.Number = 53, "OK", "Err " & Err.Number)
End Function
''',
])
SYNTAX_ERROR = 'Sub Broken()\n    If Then\nEnd Sub\n'
SYNTAX_OK = 'Function StillThere()\n    StillThere = "OK"\nEnd Function\n'
PARAGRAPHS = tuple(f'<w:p><w:pPr><w:jc w:val="{jc}"/></w:pPr><w:r><w:t>Hello world. Second sentence.</w:t></w:r></w:p>' for jc in ("start", "end", "center"))
FILES = [
    # name, kind, modules, expected results (module, function, want). A want of None only needs the office to survive.
    ("rtl-objects.xlsm", "calc", [("Cases", CALC_ONLY)], None),
    ("compile.xlsm", "calc", [("Cases", COMPILE)], None),
    ("classes.xlsm", "calc", [("IShape", CLASS_SHAPE), ("Square", CLASS_SQUARE), ("Watch", CLASS_WATCH), ("Cases", CLASS_USE)], [("Cases", f, "OK") for f in ("NewClassObjects", "ClassImplements", "ClassEvents")]),
    ("tables.xlsm", "calc", [("Cases", TABLES)], None),
    ("rtl-objects.docm", "writer", [("Cases", CALC_ONLY)], None),
    ("word-objects.docm", "writer", [("Cases", WORD_ONLY)], None),
    ("syntax-error.xlsm", "calc", [("Bad", SYNTAX_ERROR), ("Good", SYNTAX_OK)], [("Good", "StillThere", "OK")]),
    ("syntax-error.docm", "writer", [("Bad", SYNTAX_ERROR), ("Good", SYNTAX_OK)], [("Good", "StillThere", "OK")]),
]
