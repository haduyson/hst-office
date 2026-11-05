# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases for Excel shapes, hyperlinks from a range and chart series, checking their effect."""

EXCEL_SHAPES = """Function ShapeAction()
    Dim s As Object, h As Object
    Set s = ActiveSheet
    Set h = s.Shapes.AddShape(1, 100, 100, 50, 50)
    h.OnAction = "Macro1"
    If InStr(h.OnAction, "Macro1") = 0 Then ShapeAction = "OnAction [" & h.OnAction & "]": Exit Function
    h.OnAction = ""
    ShapeAction = IIf(h.OnAction = "", "OK", "cleared")
End Function
Function ShapeCells()
    Dim s As Object, h As Object
    Set s = ActiveSheet
    Set h = s.Shapes.AddShape(1, s.Cells(3, 2).Left + 2, s.Cells(3, 2).Top + 2, 2, 2)
    If h.TopLeftCell.Address <> "$B$3" Then ShapeCells = "TopLeftCell " & h.TopLeftCell.Address: Exit Function
    ShapeCells = IIf(h.BottomRightCell.Row = 3, "OK", "BottomRightCell " & h.BottomRightCell.Address)
End Function
Function TextboxInSheet()
    Dim h As Object
    Set h = ActiveSheet.Shapes.AddTextbox(msoTextOrientationHorizontal, 10, 10, 90, 30)
    h.TextFrame.Characters.Text = "chu"
    TextboxInSheet = IIf(h.TextFrame.Characters.Text = "chu", "OK", "text")
End Function
Function PictureMissing()
    On Error Resume Next
    ActiveSheet.Shapes.AddPicture "/no/such.png", False, True, 1, 1, 9, 9
    PictureMissing = IIf(Err.Number <> 0, "OK", "no error")
End Function
Function RangeHyperlinks()
    Dim r As Object
    Set r = Range("D1")
    r.Hyperlinks.Add Anchor:=r, Address:="http://x.y/", TextToDisplay:="trang"
    If r.Hyperlinks.Count <> 1 Then RangeHyperlinks = "Count " & r.Hyperlinks.Count: Exit Function
    RangeHyperlinks = IIf(r.Value = "trang", "OK", "text")
End Function
Function ChartSeries()
    Dim s As Object, c As Object, x As Object
    Set s = ActiveSheet
    s.Range("A1").Value = "Ten": s.Range("B1").Value = "So"
    s.Range("A2").Value = "a": s.Range("B2").Value = 3
    s.Range("A3").Value = "b": s.Range("B3").Value = 5
    Set c = s.ChartObjects.Add(50, 50, 300, 200).Chart
    Do While c.SeriesCollection.Count > 0
        c.SeriesCollection(1).Delete
    Loop
    Set x = c.SeriesCollection.NewSeries
    If c.SeriesCollection.Count <> 1 Then ChartSeries = "NewSeries": Exit Function
    x.Values = s.Range("B2:B3")
    x.XValues = s.Range("A2:A3")
    x.Name = "=" & s.Name & "!$B$1"
    If x.Name <> "So" Then ChartSeries = "Name [" & x.Name & "]": Exit Function
    Dim v
    v = x.Values
    If UBound(v) - LBound(v) <> 1 Or v(UBound(v)) <> 5 Then ChartSeries = "Values": Exit Function
    x.Name = "Doanh thu"
    If x.Name <> "Doanh thu" Then ChartSeries = "literal name [" & x.Name & "]": Exit Function
    x.Delete
    ChartSeries = IIf(c.SeriesCollection.Count = 0, "OK", "Delete")
End Function
"""

EXCEL_WORKBOOK = """Function WorkbookMembers()
    Dim b As Object
    Set b = ActiveWorkbook
    If b.ReadOnly Then WorkbookMembers = "ReadOnly": Exit Function
    b.BuiltinDocumentProperties("Title").Value = "Bao cao"
    If b.BuiltinDocumentProperties("Title") <> "Bao cao" Then WorkbookMembers = "Title": Exit Function
    b.CustomDocumentProperties.Add Name:="Dot", LinkToContent:=False, Type:=4, Value:="1"
    If b.CustomDocumentProperties("Dot").Value <> "1" Then WorkbookMembers = "custom": Exit Function
    b.CustomDocumentProperties("Dot").Delete
    b.RefreshAll
    b.Protect Password:="x", Structure:=True, Windows:=False
    If Not b.ProtectStructure Then WorkbookMembers = "Protect": Exit Function
    b.Unprotect "x"
    If b.Styles("Normal").Font.Size <= 0 Then WorkbookMembers = "Styles Normal": Exit Function
    If Not b.Sheets(b.Sheets.Count).Next Is Nothing Then WorkbookMembers = "Next": Exit Function
    If Not b.Sheets(1).Previous Is Nothing Then WorkbookMembers = "Previous": Exit Function
    WorkbookMembers = "OK"
End Function
Function FunctionNames()
    If Abs(WorksheetFunction.Norm_S_Dist(0, True) - 0.5) > 0.0001 Then FunctionNames = "Norm_S_Dist": Exit Function
    FunctionNames = IIf(WorksheetFunction.Sum(1, 2) = 3, "OK", "Sum")
End Function
"""
