# SPDX-License-Identifier: AGPL-3.0-only
"""VBA compatibility cases for tests/runtime/check-vba.py (Excel idioms in HST Sheets, Word idioms in HST Writer).

Each case is one VBA function body run in its own fresh document, in a module that starts with
"Option VBASupport 1" inside a VBA-mode library (what "Macro VBA" creates). The body stores
its answer in `r`; the case passes when `r` equals `want` and the optional `doc` check (Python,
reading the document over UNO) is true.

status "ok" = must pass (a failure fails the check); "limited" = known gap, reported, and a pass
is flagged so the help page and report get updated.
"""
from vba_cases_common import LOGO, WRITER_TEXT, _cell, _paragraphs, _sheet_names, _text  # noqa: F401
from vba_cases_writer import WRITER  # noqa: F401

CALC = [
    dict(id="calc-range-value", title="Range(\"A1\").Value", status="ok",
         body='Range("A1").Value = 42\nr = Range("A1").Value', want="42",
         doc=lambda d: _cell(d, "A1").Value == 42),
    dict(id="calc-cells", title="Cells(hàng, cột)", status="ok",
         body='Cells(2, 1).Value = "Xin chào"\nr = Cells(2, 1).Value', want="Xin chào",
         doc=lambda d: _cell(d, "A2").String == "Xin chào"),
    dict(id="calc-worksheets", title="Worksheets(1), Worksheets(\"tên\"), .Count", status="ok",
         body='Dim n As String\nn = Worksheets(1).Name\nWorksheets(n).Range("B1").Value = 5\n'
              'r = Worksheets.Count & "|" & Worksheets(n).Range("B1").Value', want="1|5"),
    dict(id="calc-activesheet", title="ActiveSheet", status="ok",
         body='ActiveSheet.Range("C1").Value = "x"\nr = (ActiveSheet.Name = Worksheets(1).Name) & "|" & Range("C1").Value',
         want="True|x"),
    dict(id="calc-selection", title="Range.Select, Selection", status="ok",
         body='Range("C1:C3").Select\nSelection.Value = 7\nr = Selection.Address & "|" & Range("C3").Value',
         want="$C$1:$C$3|7"),
    dict(id="calc-loops", title="For…Next, For Each cell In Range", status="ok",
         body='Dim i As Integer, c As Object, s As Double\nFor i = 1 To 5\n  Cells(i, 4).Value = i * i\nNext i\n'
              'For Each c In Range("D1:D5")\n  s = s + c.Value\nNext c\nr = s', want="55"),
    dict(id="calc-formula", title="Range.Formula, FormulaLocal", status="ok",
         body='Range("D1:D3").Value = 2\nRange("E1").Formula = "=SUM(D1:D3)"\nr = Range("E1").Value & "|" & Range("E1").Formula',
         want="6|=SUM(D1:D3)"),
    dict(id="calc-worksheetfunction", title="WorksheetFunction.Sum/Max/CountIf/VLookup", status="ok",
         body='Range("A1").Value = 1: Range("A2").Value = 5: Range("A3").Value = 9\n'
              'Range("B1").Value = "một": Range("B2").Value = "năm": Range("B3").Value = "chín"\n'
              'r = WorksheetFunction.Sum(Range("A1:A3")) & "|" & Application.WorksheetFunction.Max(Range("A1:A3")) & "|" & '
              'WorksheetFunction.CountIf(Range("A1:A3"), ">2") & "|" & WorksheetFunction.VLookup(5, Range("A1:B3"), 2, False)',
         want="15|9|2|năm"),
    dict(id="calc-msgbox", title="MsgBox (hộp thông báo)", status="ok",
         body='Dim a As Integer\na = MsgBox("Xin chào", vbInformation, "HST")\nr = "ok"', want="ok"),
    dict(id="calc-inputbox", title="InputBox, Application.InputBox", status="ok",
         body='Dim s As String\ns = InputBox("Nhập tên", "HST", "An")\nr = "ok"', want="ok"),
    dict(id="calc-font-interior", title="Font.Bold, Interior.Color, Font.Color", status="ok",
         body='Range("A1").Value = 1\nRange("A1").Font.Bold = True\nRange("A1").Interior.Color = RGB(255, 255, 0)\n'
              'Range("A1").Font.Color = RGB(255, 0, 0)\nr = Range("A1").Font.Bold',
         want="True", doc=lambda d: _cell(d, "A1").CharWeight >= 150 and _cell(d, "A1").CellBackColor == 0xFFFF00
         and _cell(d, "A1").CharColor == 0xFF0000),
    dict(id="calc-numberformat", title="NumberFormat, .Text", status="ok",
         body='Range("A1").Value = 1234567\nRange("A1").NumberFormat = "#,##0"\nr = Range("A1").Text', want="1,234,567"),
    dict(id="calc-end-usedrange", title="End(xlDown), End(xlUp), UsedRange", status="ok",
         body='Range("A1:A4").Value = 1\nr = Range("A1").End(xlDown).Row & "|" & Cells(Rows.Count, 1).End(xlUp).Row & "|" & '
              'ActiveSheet.UsedRange.Rows.Count', want="4|4|4"),
    dict(id="calc-worksheets-add", title="Worksheets.Add, .Name, .Activate", status="ok",
         body='Dim ws As Object\nSet ws = Worksheets.Add\nws.Name = "Báo cáo"\nWorksheets("Báo cáo").Activate\n'
              'r = ActiveSheet.Name & "|" & Worksheets.Count', want="Báo cáo|2",
         doc=lambda d: "Báo cáo" in _sheet_names(d)),
    dict(id="calc-copy", title="Range.Copy Destination:=", status="ok",
         body='Range("A1:A2").Value = 3\nRange("A1:A2").Copy Destination:=Range("F1")\nr = Range("F2").Value', want="3"),
    dict(id="calc-array", title="Mảng từ Range.Value (2 chiều)", status="ok",
         body='Dim v As Variant\nRange("A1:B2").Value = 4\nv = Range("A1:B2").Value\nr = UBound(v, 1) & "|" & UBound(v, 2) & "|" & v(1, 1)',
         want="2|2|4"),
    dict(id="calc-offset-resize", title="Offset, Resize, Address", status="ok",
         body='r = Range("A1").Offset(1, 1).Address & "|" & Range("A1").Resize(2, 3).Address', want="$B$2|$A$1:$C$2"),
    dict(id="calc-rows-columns", title="Columns.ColumnWidth, Rows.RowHeight, AutoFit", status="ok",
         body='Columns("A").ColumnWidth = 20\nRows(1).RowHeight = 30\nColumns("B:C").AutoFit\nr = Rows(1).RowHeight', want="30"),
    dict(id="calc-clear", title="ClearContents, Clear", status="ok",
         body='Range("A1:A3").Value = 1\nRange("A1:A2").ClearContents\nRange("A3").Clear\nr = Application.WorksheetFunction.CountA(Range("A1:A3"))',
         want="0"),
    # Error handling is tested in its own function: the case wrapper already has an On Error GoTo.
    dict(id="calc-on-error", title="On Error Resume Next, Err.Number", status="ok",
         body='r = HstLoi()', want="13",
         extra='Function HstLoi()\n  Dim x As Integer\n  On Error Resume Next\n  x = CInt("abc")\n  HstLoi = Err.Number\nEnd Function'),
    dict(id="calc-on-error-goto", title="On Error GoTo nhãn, Err.Raise", status="ok",
         body='r = HstNhan()', want="1001",
         extra='Function HstNhan()\n  On Error GoTo Loi\n  Err.Raise 1001\n  Exit Function\nLoi:\n  HstNhan = Err.Number\nEnd Function'),
    dict(id="calc-division-by-zero", title="Chia cho 0 báo lỗi 11", status="ok",
         body='r = HstChia()', want="11",
         extra='Function HstChia()\n  Dim x As Double, y As Double\n  On Error Resume Next\n  x = 1 / y\n  HstChia = Err.Number\nEnd Function'),
    dict(id="calc-strings", title="Split, Join, UCase, Format, Collection", status="ok",
         body='Dim p As Variant, c As New Collection\np = Split("a,b,c", ",")\nc.Add "x"\nc.Add "y"\n'
              'r = Join(p, "-") & "|" & UCase("hà nội") & "|" & Format(1234.5, "0.00") & "|" & c.Count',
         want="a-b-c|HÀ NỘI|1234.50|2"),
    dict(id="calc-dictionary", title="CreateObject(\"Scripting.Dictionary\"): Add, Item, Exists, Count, Remove", status="ok",
         body='Dim d As Object\nSet d = CreateObject("Scripting.Dictionary")\nd.Add "a", 1\nd.Add "b", 2\nd("c") = 3\n'
              'd.Item("a") = 10\nd.Remove "b"\nr = d.Count & "|" & d("a") & "|" & d.Item("c") & "|" & d.Exists("b") & "|" & d.Exists("c")',
         want="2|10|3|False|True"),
    dict(id="calc-dictionary-keys", title="Dictionary.Keys, .Items (mảng), For Each k In d, RemoveAll", status="ok",
         body='Dim d As Object, k As Variant, s As String, ks As Variant\nSet d = CreateObject("Scripting.Dictionary")\n'
              'd.Add "x", 1: d.Add "y", 2: d.Add "z", 3\nFor Each k In d\n  s = s & k & d(k)\nNext k\nks = d.Keys\n'
              'r = s & "|" & ks(2) & "|" & UBound(d.Items) & "|" & d.Items()(0)\nd.RemoveAll\nr = r & "|" & d.Count',
         want="x1y2z3|z|2|1|0"),
    dict(id="calc-dictionary-errors", title="Dictionary: Add trùng khóa báo lỗi 457", status="ok",
         body='r = HstTrung()', want="457",
         extra='Function HstTrung()\n  Dim d As Object\n  Set d = CreateObject("Scripting.Dictionary")\n  d.Add "k", 1\n'
               '  On Error Resume Next\n  d.Add "k", 2\n  HstTrung = Err.Number\nEnd Function'),
    dict(id="calc-dictionary-textcompare", title="Dictionary.CompareMode = vbTextCompare (\"Hà Nội\" = \"hà nội\")", status="ok",
         body='Dim d As Object, e As Object\nSet d = CreateObject("Scripting.Dictionary")\nd.CompareMode = vbTextCompare\n'
              'd("Hà Nội") = 1\nd("hà nội") = d("hà nội") + 1\nSet e = CreateObject("Scripting.Dictionary")\ne("Hà Nội") = 1\ne("hà nội") = 1\n'
              'r = d.Count & "|" & d("HÀ NỘI") & "|" & e.Count', want="1|2|2"),
    dict(id="calc-dictionary-new", title="Dim d As New Scripting.Dictionary, Set d = New Dictionary", status="ok",
         body='Dim d As New Scripting.Dictionary\nDim e As Object\nSet e = New Dictionary\nd.Add 1, "một"\ne(2) = "hai"\n'
              'r = d(1) & "|" & e(2) & "|" & d.Exists(1)', want="một|hai|True"),
    dict(id="calc-dictionary-wordcount", title="Đếm số lần xuất hiện của từ (Dictionary)", status="ok",
         body='Dim d As Object, w As Variant\nSet d = CreateObject("Scripting.Dictionary")\n'
              'For Each w In Split("an bình an vui bình an", " ")\n  d(w) = d(w) + 1\nNext w\n'
              'Range("A1").Value = d("an")\nr = d.Count & "|" & d("an") & "|" & d("bình") & "|" & d("vui")', want="3|3|2|1"),
    dict(id="calc-dictionary-dedupe", title="Lọc trùng một cột bằng Dictionary", status="ok",
         body='Dim d As Object, c As Object, i As Long, k As Variant\nSet d = CreateObject("Scripting.Dictionary")\n'
              'Range("A1").Value = "Hà Nội": Range("A2").Value = "Huế": Range("A3").Value = "Hà Nội": Range("A4").Value = "Đà Nẵng": Range("A5").Value = "Huế"\n'
              'For Each c In Range("A1:A5")\n  If Not d.Exists(c.Value) Then d.Add c.Value, True\nNext c\n'
              'i = 1\nFor Each k In d.Keys\n  Cells(i, 2).Value = k\n  i = i + 1\nNext k\nr = d.Count & "|" & Range("B3").Value',
         want="3|Đà Nẵng", doc=lambda d: _cell(d, "B1").String == "Hà Nội" and _cell(d, "B4").String == ""),
    dict(id="calc-dictionary-nested", title="Dictionary lồng nhau (Set d(k) = Dictionary)", status="ok",
         body='Dim d As Object, tp As Object\nSet d = CreateObject("Scripting.Dictionary")\n'
              'Set tp = CreateObject("Scripting.Dictionary")\ntp("dân số") = 8\nSet d("Hà Nội") = tp\n'
              'Set d("Huế") = CreateObject("Scripting.Dictionary")\nd("Huế")("dân số") = 1\n'
              'r = d("Hà Nội")("dân số") & "|" & d("Huế")("dân số") & "|" & d("Hà Nội").Count', want="8|1|1"),
    dict(id="calc-application", title="Application.ScreenUpdating, Calculate, StatusBar", status="ok",
         body='Application.ScreenUpdating = False\nApplication.Calculate\nApplication.StatusBar = "Đang chạy"\n'
              'Application.StatusBar = False\nApplication.ScreenUpdating = True\nr = Application.ScreenUpdating', want="True"),
    dict(id="calc-workbook", title="ThisWorkbook, ActiveWorkbook.Sheets", status="ok",
         body='r = ActiveWorkbook.Sheets.Count & "|" & (ThisWorkbook.Name <> "")', want="1|True"),
    dict(id="calc-sort", title="Range.Sort Key1, Order1:=xlDescending", status="ok",
         body='Range("A1").Value = 1: Range("A2").Value = 3: Range("A3").Value = 2\n'
              'Range("A1:A3").Sort Key1:=Range("A1"), Order1:=xlDescending, Header:=xlNo\nr = Range("A1").Value & Range("A3").Value',
         want="31"),
    dict(id="calc-autofilter", title="Range.AutoFilter Field, Criteria1", status="ok",
         body='Range("A1").Value = "Số": Range("A2").Value = 1: Range("A3").Value = 9\n'
              'Range("A1:A3").AutoFilter Field:=1, Criteria1:=">5"\nr = Rows(2).Hidden & "|" & Rows(3).Hidden', want="True|False"),
    dict(id="calc-names", title="Names.Add, Range(\"tên\")", status="ok",
         body='Range("A1").Value = 8\nActiveWorkbook.Names.Add Name:="DonGia", RefersTo:="=\'" & ActiveSheet.Name & "\'!$A$1"\n'
              'r = Range("DonGia").Value', want="8"),
    dict(id="calc-find-replace", title="Cells.Find, Range.Replace", status="ok",
         body='Range("B4").Value = "Xin chào"\nDim f As Object\nSet f = Cells.Find("chào")\n'
              'Range("B4").Replace "chào", "chao"\nr = f.Address & "|" & Range("B4").Value', want="$B$4|Xin chao"),
    dict(id="calc-merge-borders", title="Merge, Borders.LineStyle, HorizontalAlignment", status="ok",
         body='Range("A1:B1").Merge\nRange("A1").HorizontalAlignment = xlCenter\nRange("A2:B3").Borders.LineStyle = xlContinuous\n'
              'r = Range("A1").MergeCells', want="True"),
    dict(id="calc-comment", title="Range.AddComment", status="ok",
         body='Range("A1").AddComment "Ghi chú"\nr = Range("A1").Comment.Text', want="Ghi chú"),
    dict(id="calc-run", title="Application.Run, Call Sub", status="ok",
         body='Call HstHelper\nr = Range("Z1").Value', want="1",
         extra='Sub HstHelper()\n  Range("Z1").Value = 1\nEnd Sub'),
    dict(id="calc-udf", title="Hàm tự viết (UDF) dùng trong ô", status="ok",
         body='Range("A1").Formula = "=NHANDOI(21)"\nApplication.Calculate\nr = Range("A1").Value', want="42",
         extra='Function NhanDoi(x)\n  NhanDoi = x * 2\nEnd Function'),
    dict(id="calc-chart", title="ChartObjects.Add + Chart", status="ok",
         body='Range("A1:A3").Value = 2\nDim co As Object\nSet co = ActiveSheet.ChartObjects.Add(100, 100, 300, 200)\n'
              'co.Chart.SetSourceData Source:=Range("A1:A3")\nr = ActiveSheet.ChartObjects.Count', want="1"),
    dict(id="calc-shapes", title="Shapes.AddShape", status="ok",
         body='Dim s As Object\nSet s = ActiveSheet.Shapes.AddShape(msoShapeRectangle, 10, 10, 100, 50)\nr = ActiveSheet.Shapes.Count',
         want="1"),
]

