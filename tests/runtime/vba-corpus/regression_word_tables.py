# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases for Word tables and Document members real macros use, checking their effect."""

WORD_TABLES = """Private Function NewTable(rows As Long, cols As Long) As Object
    ActiveDocument.Content.Text = "x" & vbCr & "y"
    Set NewTable = ActiveDocument.Tables.Add(ActiveDocument.Paragraphs(1).Range, rows, cols)
End Function
Function RowsAndColumnsChange()
    Dim t As Object
    Set t = NewTable(2, 2)
    t.Rows.Add
    If t.Rows.Count <> 3 Then RowsAndColumnsChange = "Rows.Add": Exit Function
    t.Columns.Add
    If t.Columns.Count <> 3 Then RowsAndColumnsChange = "Columns.Add": Exit Function
    t.Rows(1).Cells(2).Range.Text = "hai"
    If Left(t.Cell(1, 2).Range.Text, 3) <> "hai" Then RowsAndColumnsChange = "Rows(i).Cells": Exit Function
    t.Rows.Last.Cells(1).Range.Text = "cuoi"
    If Left(t.Cell(3, 1).Range.Text, 4) <> "cuoi" Then RowsAndColumnsChange = "Rows.Last": Exit Function
    t.Rows(2).Delete
    If t.Rows.Count <> 2 Then RowsAndColumnsChange = "Row.Delete": Exit Function
    t.Columns(1).Delete
    If t.Columns.Count <> 2 Then RowsAndColumnsChange = "Column.Delete": Exit Function
    RowsAndColumnsChange = "OK"
End Function
Function WholeTableRange()
    Dim t As Object
    Set t = NewTable(2, 2)
    t.Cell(1, 1).Range.Text = "a"
    t.Cell(2, 2).Range.Text = "d"
    If InStr(t.Range.Text, "a") = 0 Or InStr(t.Range.Text, "d") = 0 Then WholeTableRange = "Text [" & t.Range.Text & "]": Exit Function
    t.Range.Font.Bold = True
    If Not t.Cell(2, 2).Range.Font.Bold Then WholeTableRange = "Font": Exit Function
    If t.Range.Cells.Count <> 4 Then WholeTableRange = "Cells": Exit Function
    If t.Range.Rows.Count <> 2 Then WholeTableRange = "Rows": Exit Function
    t.Rows(1).Range.Font.Italic = True
    If Not t.Cell(1, 1).Range.Font.Italic Or t.Cell(2, 1).Range.Font.Italic Then WholeTableRange = "Row range": Exit Function
    t.Range.Delete
    If t.Rows.Count <> 2 Or Len(t.Cell(1, 1).Range.Text) > 2 Then WholeTableRange = "Delete": Exit Function
    WholeTableRange = "OK"
End Function
Function CellMembers()
    Dim t As Object
    Set t = NewTable(2, 2)
    t.Cell(1, 1).Shading.BackgroundPatternColor = RGB(255, 0, 0)
    If t.Cell(1, 1).Shading.BackgroundPatternColor <> RGB(255, 0, 0) Then CellMembers = "Shading": Exit Function
    t.Cell(1, 2).VerticalAlignment = wdCellAlignVerticalCenter
    If t.Cell(1, 2).VerticalAlignment <> wdCellAlignVerticalCenter Then CellMembers = "VerticalAlignment": Exit Function
    If t.Cell(2, 1).RowIndex <> 2 Or t.Cell(2, 1).ColumnIndex <> 1 Then CellMembers = "indexes": Exit Function
    t.Cell(1, 1).Merge t.Cell(1, 2)
    If t.Rows(1).Cells.Count <> 1 And t.Range.Cells.Count <> 3 Then CellMembers = "Merge": Exit Function
    CellMembers = "OK"
End Function
Function TableLook()
    Dim t As Object
    Set t = NewTable(2, 2)
    t.Borders.Enable = True
    If Not t.Borders.Enable Then TableLook = "Borders on": Exit Function
    t.Borders.Enable = False
    If t.Borders.Enable Then TableLook = "Borders off": Exit Function
    t.Style = "Table Grid"
    If t.Style <> "Table Grid" Then TableLook = "Style": Exit Function
    If Not t.Borders.Enable Then TableLook = "Grid has no lines": Exit Function
    t.Rows(1).HeadingFormat = True
    If Not t.Rows(1).HeadingFormat Then TableLook = "HeadingFormat": Exit Function
    t.AutoFitBehavior wdAutoFitWindow
    t.PreferredWidthType = wdPreferredWidthPoints
    t.PreferredWidth = 200
    TableLook = IIf(Abs(t.PreferredWidth - 200) < 1, "OK", "PreferredWidth " & t.PreferredWidth)
End Function
Function NotesAndLinks()
    Dim d As Object, r As Object
    Set d = ActiveDocument
    d.Content.Text = "mot hai ba"
    Set r = d.Range(0, 3)
    d.Footnotes.Add r, , "chu thich"
    If d.Footnotes.Count <> 1 Then NotesAndLinks = "Footnotes": Exit Function
    If d.Footnotes(1).Range.Text <> "chu thich" Then NotesAndLinks = "Footnote text": Exit Function
    d.Endnotes.Add d.Range(4, 7), , "cuoi"
    If d.Endnotes.Count <> 1 Then NotesAndLinks = "Endnotes": Exit Function
    d.Hyperlinks.Add d.Range(0, 3), "http://x.y/", , , "mot"
    If d.Hyperlinks.Count <> 1 Then NotesAndLinks = "Hyperlinks " & d.Hyperlinks.Count: Exit Function
    If d.Hyperlinks(1).Address <> "http://x.y/" Then NotesAndLinks = "Address": Exit Function
    NotesAndLinks = "OK"
End Function
Function DocumentMembers()
    Dim d As Object, f As String
    Set d = ActiveDocument
    d.Content.Text = "mot hai" & vbCr & "ba"
    If d.Characters.Count < 9 Then DocumentMembers = "Characters": Exit Function
    d.TrackRevisions = True
    If Not d.TrackRevisions Then DocumentMembers = "TrackRevisions": Exit Function
    d.TrackRevisions = False
    If d.ComputeStatistics(wdStatisticWords) <> 3 Then DocumentMembers = "words": Exit Function
    If d.ComputeStatistics(wdStatisticPages) < 1 Then DocumentMembers = "pages": Exit Function
    d.Repaginate
    f = Environ("TMPDIR") & "/w.pdf"
    d.ExportAsFixedFormat OutputFileName:=f, ExportFormat:=wdExportFormatPDF
    If Len(Dir(f)) = 0 Then DocumentMembers = "PDF": Exit Function
    d.Variables("k").Value = "v"
    If d.Variables("k").Value <> "v" Then DocumentMembers = "Variables": Exit Function
    If d.Paragraphs(1).Next.Range.Text <> "ba" & vbCr And Left(d.Paragraphs(1).Next.Range.Text, 2) <> "ba" Then DocumentMembers = "Next": Exit Function
    If Not d.Paragraphs(1).Previous Is Nothing Then DocumentMembers = "Previous": Exit Function
    d.PageSetup.PaperSize = wdPaperA4
    If Abs(d.PageSetup.PageWidth - 595) > 2 Then DocumentMembers = "PageWidth": Exit Function
    If Application.DisplayAlerts = 0 Then DocumentMembers = "DisplayAlerts": Exit Function
    If Len(Application.Path) = 0 Then DocumentMembers = "Path": Exit Function
    Selection.Font.AllCaps = True
    If Not Selection.Font.AllCaps Then DocumentMembers = "AllCaps": Exit Function
    Selection.Font.AllCaps = False
    d.Styles.Add "TenRieng", wdStyleTypeParagraph
    DocumentMembers = IIf(d.Styles("TenRieng").NameLocal = "TenRieng", "OK", "Styles.Add")
End Function
"""
