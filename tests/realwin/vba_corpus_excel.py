# SPDX-License-Identifier: AGPL-3.0-only
"""Excel object-model cases: ranges, cells, formulas, sheets, names, properties, Find/Sort, formats, events."""
from vba_corpus_kit import checks, document_module, vn

WS = "Dim ws As Worksheet"
CLEAN = ("#", "Set ws = ThisWorkbook.Worksheets(1): ws.Cells.Clear")

RANGES = checks("XlRanges", [
    CLEAN, ("!write", "ws.Range(\"A1\").Value = 10: ws.Cells(2, 1).Value = 20: ws.Range(\"A3\").Value = \"ba\""),
    ("a1", "ws.Range(\"A1\").Value"), ("cells", "ws.Cells(2, 1).Value"), ("defaultMember", "ws.Range(\"A1\") + 1"),
    ("offset", "ws.Range(\"A1\").Offset(2, 0).Value"), ("resizeCount", "ws.Range(\"A1\").Resize(3, 2).Cells.Count"),
    ("address", "ws.Range(\"A1\").Resize(3, 2).Address"), ("addressRel", "ws.Range(\"B2\").Address(False, False)"),
    ("addressR1C1", "ws.Range(\"B2\").Address(ReferenceStyle:=xlR1C1)"), ("addressExternal", "ws.Range(\"B2\").Address(External:=True)"),
    ("currentRegion", "ws.Range(\"A1\").CurrentRegion.Address"), ("usedRange", "ws.UsedRange.Address"),
    ("endUp", "ws.Cells(ws.Rows.Count, 1).End(xlUp).Row"), ("endDown", "ws.Range(\"A1\").End(xlDown).Row"),
    ("endRight", "ws.Range(\"A1\").End(xlToRight).Column"), ("rowsCols", "ws.Rows.Count & \",\" & ws.Columns.Count"),
    ("#", "Dim a(1 To 2, 1 To 3) As Variant, i As Long, j As Long: For i = 1 To 2: For j = 1 To 3: a(i, j) = i * 10 + j: Next j: Next i"),
    ("!arrayWrite", "ws.Range(\"C1:E2\").Value = a"), ("arrayCell", "ws.Range(\"E2\").Value"),
    ("#", "Dim b As Variant: b = ws.Range(\"A1:A3\").Value"), ("arrayReadBounds", "LBound(b, 1) & \",\" & UBound(b, 1) & \",\" & UBound(b, 2)"),
    ("arrayReadItem", "b(3, 1)"), ("singleCellValue", "TypeName(ws.Range(\"A1:A1\").Value)"),
    ("!dateWrite", "ws.Range(\"F1\").Value = DateSerial(2024, 3, 15)"), ("dateValue", "ws.Range(\"F1\").Value"),
    ("dateValue2", "ws.Range(\"F1\").Value2"), ("dateNumberFormat", "ws.Range(\"F1\").NumberFormat"),
    ("!numberFormat", "ws.Range(\"G1\").Value = 1234.5: ws.Range(\"G1\").NumberFormat = \"#,##0.00\""),
    ("text", "ws.Range(\"G1\").Text"), ("!dateFormat", "ws.Range(\"F1\").NumberFormat = \"dd/mm/yyyy\""), ("dateText", "ws.Range(\"F1\").Text"),
    ("!merge", "ws.Range(\"H1:I1\").Merge"), ("mergeArea", "ws.Range(\"H1\").MergeArea.Address"), ("mergeCells", "ws.Range(\"I1\").MergeCells"),
    ("#", "Dim f As Range: Set f = ws.Cells.Find(What:=\"ba\", LookAt:=xlWhole)"), ("find", "f.Address"),
    ("findMissing", "ws.Cells.Find(\"khong co\") Is Nothing"),
    ("!replace", f"ws.Range(\"A1:A3\").Replace \"ba\", {vn('bốn')}"), ("afterReplace", f"ws.Range(\"A3\").Value = {vn('bốn')}"),
    ("blanks", "ws.Range(\"A1:A5\").SpecialCells(xlCellTypeBlanks).Count"),
    ("!sortData", "ws.Range(\"J1\").Value = 3: ws.Range(\"J2\").Value = 1: ws.Range(\"J3\").Value = 2"),
    ("!sort", "ws.Range(\"J1:J3\").Sort Key1:=ws.Range(\"J1\"), Order1:=xlAscending, Header:=xlNo"),
    ("sorted", "ws.Range(\"J1\").Value & ws.Range(\"J2\").Value & ws.Range(\"J3\").Value"),
    ("union", "Union(ws.Range(\"A1\"), ws.Range(\"C1:D2\")).Areas.Count & \",\" & Union(ws.Range(\"A1\"), ws.Range(\"C1:D2\")).Cells.Count"),
    ("intersect", "Intersect(ws.Range(\"A1:C3\"), ws.Range(\"B2:D4\")).Address"), ("noIntersect", "Intersect(ws.Range(\"A1\"), ws.Range(\"B2\")) Is Nothing"),
    ("!bold", "ws.Range(\"A1\").Font.Bold = True: ws.Range(\"A1\").Interior.Color = RGB(255, 0, 0)"),
    ("boldRead", "ws.Range(\"A1\").Font.Bold & \",\" & ws.Range(\"A1\").Interior.Color"),
    ("!width", "ws.Columns(\"B\").ColumnWidth = 20"), ("widthRead", "ws.Columns(\"B\").ColumnWidth"),
    ("!insertRow", "ws.Rows(1).Insert"), ("afterInsert", "ws.Range(\"A2\").Value"),
    ("!deleteRow", "ws.Rows(1).Delete"), ("afterDelete", "ws.Range(\"A1\").Value"),
    ("!clearContents", "ws.Range(\"A1\").ClearContents"), ("isEmpty", "IsEmpty(ws.Range(\"A1\").Value)"),
    ("countA", "Application.WorksheetFunction.CountA(ws.Range(\"A1:A3\"))"), ("rowCol", "ws.Range(\"C5\").Row & \",\" & ws.Range(\"C5\").Column"),
    ("forEachCells", "ForEachCells()"),
], declare=WS)

FORMULAS = checks("XlFormulas", [
    CLEAN, ("!fill", "Dim i As Long: For i = 1 To 5: ws.Cells(i, 1).Value = i * 2: ws.Cells(i, 2).Value = \"k\" & i: Next"),
    ("!formulas", "ws.Range(\"C1\").Formula = \"=SUM(A1:A5)\": ws.Range(\"C2\").Formula = \"=AVERAGE(A1:A5)\": "
     "ws.Range(\"C3\").Formula = \"=IF(A1>5,\"\"lon\"\",\"\"nho\"\")\": ws.Range(\"C4\").Formula = \"=VLOOKUP(\"\"k3\"\",B1:C5,1,FALSE)\""),
    ("sum", "ws.Range(\"C1\").Value"), ("average", "ws.Range(\"C2\").Value"), ("if", "ws.Range(\"C3\").Value"), ("vlookup", "ws.Range(\"C4\").Value"),
    ("formulaText", "ws.Range(\"C1\").Formula"), ("formulaR1C1", "ws.Range(\"C1\").FormulaR1C1"), ("hasFormula", "ws.Range(\"C1\").HasFormula"),
    ("!more", "ws.Range(\"D1\").Formula = \"=COUNTIF(A1:A5,\"\">4\"\")\": ws.Range(\"D2\").Formula = \"=SUMIF(A1:A5,\"\">4\"\")\": "
     "ws.Range(\"D3\").Formula = \"=INDEX(B1:B5,MATCH(6,A1:A5,0))\": ws.Range(\"D4\").Formula = \"=ROUND(2.345,2)\""),
    ("countif", "ws.Range(\"D1\").Value"), ("sumif", "ws.Range(\"D2\").Value"), ("indexMatch", "ws.Range(\"D3\").Value"), ("round", "ws.Range(\"D4\").Value"),
    ("!textFns", "ws.Range(\"E1\").Formula = \"=TEXT(A1,\"\"0.00\"\")\": ws.Range(\"E2\").Formula = \"=CONCATENATE(B1,\"\"-\"\",A1)\": "
     "ws.Range(\"E3\").Formula = \"=DATE(2024,1,31)+1\": ws.Range(\"E4\").Formula = \"=IFERROR(1/0,\"\"loi\"\")\""),
    ("textFn", "ws.Range(\"E1\").Value"), ("concat", "ws.Range(\"E2\").Value"), ("dateFn", "ws.Range(\"E3\").Value"), ("iferror", "ws.Range(\"E4\").Value"),
    ("!errorCell", "ws.Range(\"F1\").Formula = \"=1/0\""), ("errorValue", "ws.Range(\"F1\").Value"), ("isError", "IsError(ws.Range(\"F1\").Value)"),
    ("errorText", "ws.Range(\"F1\").Text"),
    ("wfSum", "WorksheetFunction.Sum(ws.Range(\"A1:A5\"))"), ("wfMax", "Application.WorksheetFunction.Max(ws.Range(\"A1:A5\"))"),
    ("wfVlookup", "WorksheetFunction.VLookup(\"k2\", ws.Range(\"B1:C5\"), 1, False)"),
    ("wfVlookupMissing", "WorksheetFunction.VLookup(\"zz\", ws.Range(\"B1:C5\"), 1, False)"),
    ("appVlookupMissing", "IsError(Application.VLookup(\"zz\", ws.Range(\"B1:C5\"), 1, False))"),
    ("wfMatch", "WorksheetFunction.Match(8, ws.Range(\"A1:A5\"), 0)"), ("wfCountIf", "WorksheetFunction.CountIf(ws.Range(\"A1:A5\"), \">=6\")"),
    ("wfRoundDown", "WorksheetFunction.RoundDown(2.567, 2)"), ("wfText", "WorksheetFunction.Text(0.5, \"0%\")"),
    ("evaluate", "Application.Evaluate(\"SUM(1,2,3)\")"), ("evaluateRef", "Evaluate(\"A1*2\")"), ("bracket", "[A2+1]"),
    ("!r1c1Write", "ws.Range(\"G1\").FormulaR1C1 = \"=RC[-6]*3\""), ("r1c1Value", "ws.Range(\"G1\").Value"), ("r1c1AsA1", "ws.Range(\"G1\").Formula"),
    ("!fillDown", "ws.Range(\"G1:G5\").FillDown"), ("filledFormula", "ws.Range(\"G5\").Formula"),
    ("!arrayFormula", "ws.Range(\"H1\").FormulaArray = \"=SUM(A1:A5*2)\""), ("arrayFormulaValue", "ws.Range(\"H1\").Value"),
    ("!recalc", "ws.Range(\"A1\").Value = 100: Application.Calculate"), ("afterRecalc", "ws.Range(\"C1\").Value"),
    ("calcMode", "Application.Calculation"),
], declare=WS)

SHEETS = checks("XlSheets", [
    ("#", "Dim ws2 As Worksheet, n As Long, sh As Object, nm As String: Application.DisplayAlerts = False"),
    ("count", "ThisWorkbook.Worksheets.Count"), ("firstName", "Worksheets(1).Name"),
    ("#", "Set ws2 = Worksheets.Add(After:=Worksheets(Worksheets.Count))"), ("addedCount", "Worksheets.Count"),
    ("activeAfterAdd", "ActiveSheet.Name = ws2.Name"), ("!rename", "ws2.Name = \"Bao cao\""), ("index", "Worksheets(\"Bao cao\").Index"),
    ("!renameVn", f"ws2.Name = {vn('Báo cáo')}"), ("vnName", f"Worksheets({vn('Báo cáo')}).Name = {vn('Báo cáo')}"),
    ("!renameDup", "ws2.Name = \"Sheet1\""), ("nameAfterDup", f"ws2.Name = {vn('Báo cáo')}"), ("!renameBack", "ws2.Name = \"Bao cao\""),
    ("!copy", "ws2.Copy After:=ws2"), ("copyName", "Worksheets(Worksheets.Count).Name"), ("countAfterCopy", "Worksheets.Count"),
    ("!deleteCopy", "Worksheets(\"Bao cao (2)\").Delete"), ("countAfterDelete", "Worksheets.Count"),
    ("!hide", "ws2.Visible = xlSheetHidden"), ("visible", "ws2.Visible"), ("!unhide", "ws2.Visible = xlSheetVisible"),
    ("!move", "ws2.Move Before:=Worksheets(1)"), ("firstAfterMove", "Worksheets(1).Name"),
    ("!moveBack", "Worksheets(\"Bao cao\").Move After:=Worksheets(Worksheets.Count)"),
    ("missing", "Worksheets(\"Khong co\").Name"), ("sheetsVsWorksheets", "Sheets.Count = Worksheets.Count"),
    ("#", "For Each sh In ThisWorkbook.Worksheets: nm = nm & sh.Name & \";\": Next"), ("forEachNames", "nm"),
    ("!crossSheet", "Worksheets(\"Bao cao\").Range(\"A1\").Value = 5: Worksheets(1).Range(\"A1\").Formula = \"='Bao cao'!A1*2\""),
    ("crossSheetValue", "Worksheets(1).Range(\"A1\").Value"), ("codeName", "Worksheets(1).CodeName"),
    ("workbookName", "ThisWorkbook.Name"), ("pathSet", "Len(ThisWorkbook.Path) > 0"), ("activeIsThis", "ActiveWorkbook Is ThisWorkbook"),
    ("!deleteAdded", "Worksheets(\"Bao cao\").Delete: Worksheets(1).Cells.Clear"), ("finalCount", "Worksheets.Count"),
    ("#", "Application.DisplayAlerts = True"),
], declare="")

NAMES = checks("XlNames", [
    CLEAN, ("!data", "ws.Range(\"A1\").Value = 1: ws.Range(\"A2\").Value = 2: ws.Range(\"A3\").Value = 3"),
    ("!add", "ThisWorkbook.Names.Add Name:=\"DonGia\", RefersTo:=\"=Sheet1!$A$1:$A$3\""),
    ("cells", "ws.Range(\"DonGia\").Cells.Count"), ("appRange", "Range(\"DonGia\").Address"), ("wfSum", "WorksheetFunction.Sum(Range(\"DonGia\"))"),
    ("refersTo", "ThisWorkbook.Names(\"DonGia\").RefersTo"), ("refersToRange", "ThisWorkbook.Names(\"DonGia\").RefersToRange.Address"),
    ("!formula", "ws.Range(\"B1\").Formula = \"=SUM(DonGia)*2\""), ("formulaValue", "ws.Range(\"B1\").Value"),
    ("!constant", "ThisWorkbook.Names.Add \"TyLe\", \"=0.1\""), ("evaluateConst", "Evaluate(\"TyLe\")"),
    ("!rangeName", "ws.Range(\"C1:C2\").Name = \"Vung1\""), ("rangeNameRef", "ThisWorkbook.Names(\"Vung1\").RefersTo"),
    ("!local", "ws.Names.Add Name:=\"Rieng\", RefersTo:=\"=Sheet1!$A$1\""), ("localName", "ws.Names(\"Rieng\").Name"),
    ("count", "ThisWorkbook.Names.Count"), ("missing", "ThisWorkbook.Names(\"KhongCo\").Name"),
    ("!delete", "ThisWorkbook.Names(\"DonGia\").Delete: ThisWorkbook.Names(\"TyLe\").Delete: ThisWorkbook.Names(\"Vung1\").Delete"),
    ("countAfter", "ThisWorkbook.Names.Count"),
], declare=WS)

PROPS = checks("XlProps", [
    ("!title", "ThisWorkbook.BuiltinDocumentProperties(\"Title\") = \"Bao cao thang\""),
    ("titleRead", "ThisWorkbook.BuiltinDocumentProperties(\"Title\").Value"),
    ("!author", f"ThisWorkbook.BuiltinDocumentProperties(\"Author\").Value = {vn('Nguyễn An')}"),
    ("authorRead", f"ThisWorkbook.BuiltinDocumentProperties(\"Author\").Value = {vn('Nguyễn An')}"),
    ("!subject", "ThisWorkbook.BuiltinDocumentProperties(\"Subject\") = \"Chu de\""), ("subjectRead", "ThisWorkbook.BuiltinDocumentProperties(\"Subject\")"),
    ("!customText", "ThisWorkbook.CustomDocumentProperties.Add Name:=\"SoHieu\", LinkToContent:=False, Type:=4, Value:=\"123/QD\""),
    ("customText", "ThisWorkbook.CustomDocumentProperties(\"SoHieu\").Value"),
    ("!customNumber", "ThisWorkbook.CustomDocumentProperties.Add Name:=\"SoTrang\", LinkToContent:=False, Type:=1, Value:=12"),
    ("customNumber", "ThisWorkbook.CustomDocumentProperties(\"SoTrang\").Value + 1"),
    ("customCount", "ThisWorkbook.CustomDocumentProperties.Count"), ("customType", "ThisWorkbook.CustomDocumentProperties(\"SoHieu\").Type"),
    ("!customDelete", "ThisWorkbook.CustomDocumentProperties(\"SoHieu\").Delete"), ("customCountAfter", "ThisWorkbook.CustomDocumentProperties.Count"),
    ("missing", "ThisWorkbook.CustomDocumentProperties(\"KhongCo\").Value"),
], declare="")

EVENTS = checks("XlEvents", [
    ("#", "Set ws = ThisWorkbook.Worksheets(1)"),
    ("workbookOpen", "ws.Range(\"Z1\").Value"), ("autoOpen", "ws.Range(\"Z2\").Value"),
    ("!change", "ws.Range(\"A10\").Value = 7"), ("worksheetChange", "ws.Range(\"Z3\").Value"),
    ("!disabled", "Application.EnableEvents = False: ws.Range(\"A10\").Value = 8: Application.EnableEvents = True"),
    ("afterDisabled", "ws.Range(\"Z3\").Value"), ("!otherCell", "ws.Range(\"B10\").Value = 1"), ("afterOtherCell", "ws.Range(\"Z3\").Value"),
], declare=WS)

EVENT_MODULES = [
    ("ThisWorkbook", document_module("ThisWorkbook", "Private Sub Workbook_Open()\n    Worksheets(1).Range(\"Z1\").Value = \"wb-open\"\nEnd Sub\n")),
    ("Sheet1", document_module("Sheet1", "Private Sub Worksheet_Change(ByVal Target As Range)\n"
                               "    If Target.Address = \"$A$10\" Then Me.Range(\"Z3\").Value = \"changed:\" & Target.Value\nEnd Sub\n")),
]
AUTO_OPEN = "Public Sub Auto_Open()\n    ThisWorkbook.Worksheets(1).Range(\"Z2\").Value = \"auto-open\"\nEnd Sub\n"

RANGE_HELPERS = '''Public Function ForEachCells() As String
    Dim c As Range, s As String
    For Each c In ThisWorkbook.Worksheets(1).Range("C1:D2").Cells
        s = s & c.Address(False, False) & "=" & c.Value & ";"
    Next
    ForEachCells = s
End Function
'''
