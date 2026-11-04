# SPDX-License-Identifier: AGPL-3.0-only
"""VBA compatibility cases for tests/runtime/check-vba.py (Excel idioms in HST Sheets, Word idioms in HST Writer).

Each case is one VBA function body run in its own fresh document, in a module that starts with
"Option VBASupport 1" inside a VBA-mode library (what "Macro VBA" creates). The body stores
its answer in `r`; the case passes when `r` equals `want` and the optional `doc` check (Python,
reading the document over UNO) is true.

status "ok" = must pass (a failure fails the check); "limited" = known gap, reported, and a pass
is flagged so the help page and report get updated.
"""

LOGO = "/home/office/assets/brand/hst-office-logo.png"  # readable by the build user
WRITER_TEXT = "Xin chào thế giới. Đây là câu thứ hai.\nĐoạn hai có từ HST và HST.\nĐoạn ba."


def _cell(doc, name):
    return doc.Sheets.getByIndex(0).getCellRangeByName(name)


def _sheet_names(doc):
    return list(doc.Sheets.ElementNames)


def _paragraphs(doc):
    enum = doc.Text.createEnumeration()
    while enum.hasMoreElements():
        yield enum.nextElement()


def _text(doc):
    return doc.Text.String.replace("\r\n", "\n").replace("\r", "\n")


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

WRITER = [
    dict(id="writer-activedocument", title="ActiveDocument.Content.Text", status="ok",
         body='r = Left(ActiveDocument.Content.Text, 9)', want="Xin chào "),
    dict(id="writer-range-insert", title="Range.InsertAfter, InsertBefore", status="ok",
         body='ActiveDocument.Content.InsertAfter " Hết."\nActiveDocument.Content.InsertBefore "Đầu. "\nr = "ok"', want="ok",
         doc=lambda d: _text(d).startswith("Đầu. Xin chào") and _text(d).rstrip().endswith("Hết.")),
    dict(id="writer-document-range", title="ActiveDocument.Range(start, end).Text", status="ok",
         body='r = ActiveDocument.Range(0, 3).Text', want="Xin"),
    dict(id="writer-selection-typetext", title="Selection.TypeText, TypeParagraph", status="ok",
         body='Selection.HomeKey Unit:=wdStory\nSelection.TypeText Text:="Mới "\nSelection.TypeParagraph\nr = "ok"', want="ok",
         doc=lambda d: _text(d).startswith("Mới \nXin chào")),
    dict(id="writer-selection-font", title="Selection.Font.Bold, Range.Font.Size", status="ok",
         body='ActiveDocument.Range(0, 3).Select\nSelection.Font.Bold = True\nActiveDocument.Range(0, 3).Font.Size = 20\n'
              'r = ActiveDocument.Range(0, 3).Font.Bold', want="-1",
         doc=lambda d: d.Text.createEnumeration().nextElement().createEnumeration().nextElement().CharWeight >= 150),
    dict(id="writer-paragraphs", title="Paragraphs.Count, Paragraphs(n).Range.Text", status="ok",
         body='r = ActiveDocument.Paragraphs.Count & "|" & Left(ActiveDocument.Paragraphs(3).Range.Text, 7)', want="3|Đoạn ba"),
    dict(id="writer-paragraph-format", title="Paragraphs(1).Alignment, Range.ParagraphFormat.Alignment", status="ok",
         body='ActiveDocument.Paragraphs(1).Alignment = wdAlignParagraphCenter\n'
              'ActiveDocument.Paragraphs(2).Range.ParagraphFormat.Alignment = wdAlignParagraphRight\n'
              'r = ActiveDocument.Paragraphs(1).Alignment & "|" & ActiveDocument.Paragraphs(2).Format.Alignment',
         want="1|2", doc=lambda d: d.Text.createEnumeration().nextElement().ParaAdjust == 3),
    dict(id="writer-find-replace", title="Find.Execute Replace:=wdReplaceAll", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Content\nrg.Find.Execute FindText:="HST", ReplaceWith:="HASON", Replace:=wdReplaceAll\n'
              'r = "ok"', want="ok", doc=lambda d: "HST" not in _text(d) and _text(d).count("HASON") == 2),
    dict(id="writer-find", title="Find.Execute không thay thế (tìm, chọn chữ tìm thấy)", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Content\nr = rg.Find.Execute(FindText:="thế giới") & "|" & rg.Text', want="True|thế giới"),
    dict(id="writer-tables-add", title="Tables.Add, Rows.Count, Columns.Count", status="ok",
         body='Dim tb As Object\nSet tb = ActiveDocument.Tables.Add(ActiveDocument.Paragraphs(3).Range, 2, 3)\n'
              'r = ActiveDocument.Tables.Count & "|" & tb.Rows.Count & "|" & tb.Columns.Count',
         want="1|2|3", doc=lambda d: d.TextTables.Count == 1),
    dict(id="writer-table-cell", title="Table.Cell(h, c).Range.Text", status="ok",
         body='Dim tb As Object\nSet tb = ActiveDocument.Tables.Add(ActiveDocument.Paragraphs(3).Range, 2, 3)\n'
              'tb.Cell(1, 1).Range.Text = "Ô 1"\ntb.Cell(2, 3).Range.Text = "Ô 6"\nr = tb.Cell(2, 3).Range.Text', want="Ô 6",
         doc=lambda d: d.TextTables.getByIndex(0).getCellByName("A1").String == "Ô 1"),
    dict(id="writer-words-sentences", title="Words.Count, Sentences(1)", status="ok",
         body='r = (ActiveDocument.Words.Count > 10) & "|" & Left(ActiveDocument.Sentences(1).Text, 8)', want="True|Xin chào"),
    dict(id="writer-bookmarks", title="Bookmarks.Add, Bookmarks(\"tên\").Range", status="ok",
         body='ActiveDocument.Bookmarks.Add "DauVanBan", ActiveDocument.Range(0, 3)\n'
              'r = ActiveDocument.Bookmarks.Count & "|" & ActiveDocument.Bookmarks("DauVanBan").Range.Text', want="1|Xin"),
    dict(id="writer-styles", title="Paragraphs(1).Style = \"Heading 1\"", status="ok",
         body='ActiveDocument.Paragraphs(1).Style = ActiveDocument.Styles(wdStyleHeading1)\nr = "ok"', want="ok",
         doc=lambda d: d.Text.createEnumeration().nextElement().ParaStyleName in ("Heading 1", "Heading1")),
    dict(id="writer-header-footer", title="Sections(1).Headers(wdHeaderFooterPrimary)", status="ok",
         body='ActiveDocument.Sections(1).Headers(wdHeaderFooterPrimary).Range.Text = "Đầu trang"\nr = "ok"', want="ok"),
    dict(id="writer-insert-break", title="Selection.InsertBreak wdPageBreak", status="ok",
         body='Selection.EndKey Unit:=wdStory\nSelection.InsertBreak Type:=wdPageBreak\nr = "ok"', want="ok"),
    dict(id="writer-msgbox", title="MsgBox", status="ok",
         body='Dim a As Integer\na = MsgBox("Xin chào", vbOKOnly)\nr = "ok"', want="ok"),
    dict(id="writer-loop-paragraphs", title="For Each p In ActiveDocument.Paragraphs", status="ok",
         body='Dim p As Object, n As Integer\nFor Each p In ActiveDocument.Paragraphs\n  n = n + 1\nNext p\nr = n', want="3"),
    dict(id="writer-inlineshapes", title="InlineShapes.Count, Shapes.Count", status="ok",
         body='r = ActiveDocument.InlineShapes.Count & "|" & ActiveDocument.Shapes.Count', want="0|0"),
    dict(id="writer-inlineshapes-add", title="InlineShapes.AddPicture, Width/Height, LockAspectRatio", status="ok",
         body='Dim ish As Object, h As Single\nSet ish = ActiveDocument.InlineShapes.AddPicture(FileName:="' + LOGO + '", '
              'LinkToFile:=False, SaveWithDocument:=True, Range:=ActiveDocument.Paragraphs(3).Range)\n'
              'h = ish.Height / ish.Width\nish.LockAspectRatio = msoTrue\nish.Width = 72\n'
              'r = ActiveDocument.InlineShapes.Count & "|" & Round(ish.Width) & "|" & (Abs(ish.Height / ish.Width - h) < 0.02) & "|" & ish.Type',
         want="1|72|True|3", doc=lambda d: d.GraphicObjects.Count == 1),
    dict(id="writer-fields", title="Fields.Add (DATE, PAGE, NUMPAGES), Fields.Update", status="ok",
         body='ActiveDocument.Fields.Add Range:=ActiveDocument.Range(0, 0), Type:=wdFieldDate\n'
              'ActiveDocument.Fields.Add ActiveDocument.Paragraphs(3).Range, wdFieldPage\n'
              'ActiveDocument.Fields.Add ActiveDocument.Range(0, 0), wdFieldEmpty, "NUMPAGES"\n'
              'r = ActiveDocument.Fields.Count & "|" & ActiveDocument.Fields.Update', want="3|0"),
    dict(id="writer-comments", title="Comments.Add, Comments(1).Range.Text, .Scope, .Author", status="ok",
         body='Dim cm As Object\nSet cm = ActiveDocument.Comments.Add(ActiveDocument.Range(0, 3), "Ghi chú")\n'
              'cm.Author = "HST"\nr = ActiveDocument.Comments.Count & "|" & ActiveDocument.Comments(1).Range.Text & "|" & cm.Scope.Text & "|" & cm.Author',
         want="1|Ghi chú|Xin|HST"),
    dict(id="writer-lists", title="Range.ListFormat.ApplyBulletDefault", status="ok",
         body='ActiveDocument.Paragraphs(2).Range.ListFormat.ApplyBulletDefault\nr = "ok"', want="ok",
         doc=lambda d: [p.NumberingStyleName for p in _paragraphs(d)][:3] == ["", "List 1", ""]),
    dict(id="writer-document-properties", title="BuiltInDocumentProperties(\"Title\")", status="ok",
         body='ActiveDocument.BuiltInDocumentProperties("Title") = "Báo cáo"\nr = ActiveDocument.BuiltInDocumentProperties("Title")',
         want="Báo cáo"),
    dict(id="writer-dictionary-wordcount", title="Đếm từ trong văn bản bằng Scripting.Dictionary", status="ok",
         body='Dim d As Object, w As Variant\nSet d = CreateObject("Scripting.Dictionary")\nd.CompareMode = vbTextCompare\n'
              'For Each w In Split(Replace(ActiveDocument.Paragraphs(2).Range.Text, ".", ""), " ")\n  If Len(Trim(w)) > 0 Then d(Trim(w)) = d(Trim(w)) + 1\nNext w\n'
              'r = d("hst") & "|" & d.Exists("ĐOẠN") & "|" & d.Count', want="2|True|6"),
    dict(id="writer-dictionary-nested", title="Dictionary lồng nhau, khóa tiếng Việt (TextCompare)", status="ok",
         body='Dim d As Object\nSet d = CreateObject("Scripting.Dictionary")\nd.CompareMode = vbTextCompare\n'
              'Set d("Hà Nội") = CreateObject("Scripting.Dictionary")\nd("hà nội")("số đoạn") = ActiveDocument.Paragraphs.Count\n'
              'r = d("HÀ NỘI")("số đoạn") & "|" & d.Count', want="3|1"),
    dict(id="writer-range-words", title="Range.Words.Count, Range.Sentences(1), Range.Bold/Italic", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Paragraphs(1).Range\nrg.Words(1).Bold = True\nrg.Sentences(2).Italic = True\n'
              'r = rg.Words.Count & "|" & Left(rg.Sentences(2).Text, 6) & "|" & rg.Words(1).Bold & "|" & rg.Words(2).Bold & "|" & rg.Sentences(2).Italic',
         want="9|Đây là|-1|0|-1"),
    dict(id="writer-selection-words", title="Selection.Words, Selection.Sentences, Selection.ClearFormatting", status="ok",
         body='ActiveDocument.Paragraphs(1).Range.Select\nSelection.Words(1).Italic = True\n'
              'r = Selection.Words(1).Italic & "|" & Selection.Sentences.Count\nSelection.ClearFormatting\nr = r & "|" & Selection.Words(1).Italic',
         want="-1|2|0"),
]
