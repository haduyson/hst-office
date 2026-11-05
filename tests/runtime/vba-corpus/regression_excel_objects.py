# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases for the Excel object members real macros use most, each checking the effect and not only that no error came."""

SHEET_DATA = """Private Sub FillData(s As Object)
    s.Cells.Clear
    s.Range("A1").Value = "Ten": s.Range("B1").Value = "So"
    s.Range("A2").Value = "Cam": s.Range("B2").Value = 3
    s.Range("A3").Value = "An": s.Range("B3").Value = 1
    s.Range("A4").Value = "Binh": s.Range("B4").Value = 2
    s.Range("A5").Value = "An": s.Range("B5").Value = 1
End Sub
"""

EXCEL_OBJECTS = SHEET_DATA + """Function EvaluateFormula()
    Dim s As Object
    Set s = ActiveSheet
    FillData s
    If Evaluate("SUM(1,2)") <> 3 Then EvaluateFormula = "plain": Exit Function
    If Application.Evaluate("SUM(B2:B5)") <> 7 Then EvaluateFormula = "range sum": Exit Function
    If s.Evaluate("COUNTA(A1:A5)") <> 5 Then EvaluateFormula = "sheet": Exit Function
    If Evaluate("B2").Value <> 3 Then EvaluateFormula = "range": Exit Function
    If [B3] <> 1 Then EvaluateFormula = "brackets": Exit Function
    EvaluateFormula = "OK"
End Function
Function WorksheetSort()
    Dim s As Object
    Set s = ActiveSheet
    FillData s
    s.Sort.SortFields.Clear
    s.Sort.SortFields.Add Key:=s.Range("B2:B5"), Order:=xlDescending
    If s.Sort.SortFields.Count <> 1 Then WorksheetSort = "count": Exit Function
    s.Sort.SetRange s.Range("A1:B5")
    s.Sort.Header = xlYes
    s.Sort.Apply
    If s.Range("A1").Value <> "Ten" Then WorksheetSort = "header moved": Exit Function
    If s.Range("A2").Value <> "Cam" Or s.Range("B5").Value <> 1 Or s.Range("B3").Value <> 2 Then WorksheetSort = "order": Exit Function
    WorksheetSort = "OK"
End Function
Function FindNextLoop()
    Dim s As Object, c As Object, first As String, n As Long
    Set s = ActiveSheet
    FillData s
    Set c = s.Range("A1:A5").Find(What:="An", LookIn:=xlValues, LookAt:=xlWhole)
    If c Is Nothing Then FindNextLoop = "first": Exit Function
    first = c.Address
    Do
        n = n + 1
        Set c = s.Range("A1:A5").FindNext(c)
    Loop While Not c Is Nothing And c.Address <> first And n < 9
    FindNextLoop = IIf(n = 2, "OK", "found " & n)
End Function
Function FormatConditionsAdd()
    Dim s As Object, r As Object, fc As Object
    Set s = ActiveSheet
    FillData s
    Set r = s.Range("B2:B5")
    r.FormatConditions.Delete
    Set fc = r.FormatConditions.Add(Type:=xlCellValue, Operator:=xlGreater, Formula1:="=1")
    If r.FormatConditions.Count <> 1 Then FormatConditionsAdd = "count": Exit Function
    If fc Is Nothing Then FormatConditionsAdd = "object": Exit Function
    fc.Interior.ColorIndex = 3
    r.FormatConditions.Delete
    FormatConditionsAdd = IIf(r.FormatConditions.Count = 0, "OK", "not deleted")
End Function
Function RemoveDuplicatesKeepsFirst()
    Dim s As Object
    Set s = ActiveSheet
    FillData s
    s.Range("A1:B5").RemoveDuplicates Columns:=1, Header:=xlYes
    If s.Range("A4").Value <> "Binh" Then RemoveDuplicatesKeepsFirst = "row 4": Exit Function
    RemoveDuplicatesKeepsFirst = IIf(IsEmpty(s.Range("A5").Value), "OK", "row 5 stayed")
End Function
Function TextToColumnsSplits()
    Dim s As Object
    Set s = ActiveSheet
    s.Cells.Clear
    s.Range("A1").Value = "x,y,z"
    s.Range("A1").TextToColumns Destination:=s.Range("A1"), DataType:=xlDelimited, Comma:=True
    TextToColumnsSplits = IIf(s.Range("C1").Value = "z" And s.Range("A1").Value = "x", "OK", s.Range("A1").Value & "|" & s.Range("C1").Value)
End Function
Function RangeMembers()
    Dim s As Object, r As Object
    Set s = ActiveSheet
    FillData s
    Set r = s.Range("A1:B5")
    If r.CountLarge <> 10 Then RangeMembers = "CountLarge": Exit Function
    If r.HasArray Then RangeMembers = "HasArray": Exit Function
    If Not s.Range("A1").ListObject Is Nothing Then RangeMembers = "ListObject": Exit Function
    If s.Range("A1").AddressLocal <> "$A$1" Then RangeMembers = "AddressLocal": Exit Function
    s.Range("A1").AddComment "ghi chu"
    s.Range("A1").ClearNotes
    If Not s.Range("A1").Comment Is Nothing Then RangeMembers = "ClearNotes": Exit Function
    RangeMembers = "OK"
End Function
Function SheetMembers()
    Dim s As Object
    Set s = ActiveSheet
    s.Tab.Color = RGB(255, 0, 0)
    If s.Tab.Color <> RGB(255, 0, 0) Then SheetMembers = "Tab.Color " & s.Tab.Color: Exit Function
    If s.Type <> xlWorksheet Then SheetMembers = "Type": Exit Function
    FillData s
    If s.FilterMode Then SheetMembers = "FilterMode before": Exit Function
    s.Range("A1:B5").AutoFilter Field:=1, Criteria1:="An"
    If Not s.FilterMode Then SheetMembers = "FilterMode after": Exit Function
    If Not s.Rows(2).Hidden Then SheetMembers = "row not filtered": Exit Function
    s.ShowAllData
    If s.Rows(2).Hidden Then SheetMembers = "ShowAllData": Exit Function
    s.Range("A1:B5").AutoFilter
    s.HPageBreaks.Add s.Range("A3")
    s.ResetAllPageBreaks
    SheetMembers = IIf(s.HPageBreaks.Count = 0, "OK", "page breaks")
End Function
Function ApplicationSettings()
    Application.Calculation = xlCalculationManual
    Application.Calculate
    Application.CalculateFull
    Application.Calculation = xlCalculationAutomatic
    Application.DisplayAlerts = False
    Application.DisplayAlerts = True
    Application.UserName = "Nguoi dung"
    If Application.UserName <> "Nguoi dung" Then ApplicationSettings = "UserName": Exit Function
    Application.MoveAfterReturn = True
    Application.MacroOptions Macro:="ApplicationSettings", Description:="x"
    If Len(Application.Path) = 0 Then ApplicationSettings = "Path": Exit Function
    If Len(Application.Build) = 0 Then ApplicationSettings = "Build": Exit Function
    ApplicationSettings = "OK"
End Function
Function FileDialogFilters()
    Dim d As Object
    Set d = Application.FileDialog(msoFileDialogFilePicker)
    d.Filters.Clear
    d.Filters.Add "So lieu", "*.xlsx;*.xlsm"
    d.Filters.Add "Tat ca", "*.*"
    If d.Filters.Count <> 2 Then FileDialogFilters = "count": Exit Function
    If d.Filters(1).Description <> "So lieu" Then FileDialogFilters = "description": Exit Function
    If d.Filters(2).Extensions <> "*.*" Then FileDialogFilters = "extensions": Exit Function
    d.FilterIndex = 2
    FileDialogFilters = IIf(d.FilterIndex = 2, "OK", "index")
End Function
"""
