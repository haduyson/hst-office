# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases for the Word Range and Selection members real macros use most, checking their effect."""

WORD_MEMBERS = """Private Function Fresh() As Object
    ActiveDocument.Content.Text = "Hello big world. Second one." & vbCr & "Next para" & vbCr & "Last"
    Set Fresh = ActiveDocument.Range(0, 0)
End Function
Function RangeMoves()
    Dim r As Object, n As Long
    Set r = Fresh()
    n = r.Move(wdWord, 1)
    If r.Start <> 6 Or r.End <> 6 Then RangeMoves = "Move " & r.Start: Exit Function
    r.Expand wdWord
    If r.Text <> "big " Then RangeMoves = "Expand word [" & r.Text & "]": Exit Function
    r.Collapse wdCollapseStart
    r.Expand wdParagraph
    If Left(r.Text, 5) <> "Hello" Or Right(r.Text, 1) <> vbCr Then RangeMoves = "Expand para [" & r.Text & "]": Exit Function
    r.SetRange 7, 7
    r.EndOf wdWord, wdExtend
    If r.Start <> 7 Or r.End <> 10 Then RangeMoves = "EndOf " & r.Start & "," & r.End: Exit Function
    r.SetRange 7, 7
    r.StartOf wdWord
    If r.Start <> 6 Then RangeMoves = "StartOf " & r.Start: Exit Function
    RangeMoves = "OK"
End Function
Function NextAndPrevious()
    Dim r As Object
    Set r = Fresh()
    r.SetRange 0, 6
    If r.Next(wdWord, 1).Text <> "big " Then NextAndPrevious = "Next [" & r.Next(wdWord, 1).Text & "]": Exit Function
    r.SetRange 6, 9
    If r.Previous(wdWord, 1).Text <> "Hello " Then NextAndPrevious = "Previous": Exit Function
    NextAndPrevious = "OK"
End Function
Function RangeDeleteAndCharacters()
    Dim r As Object
    Set r = Fresh()
    If ActiveDocument.Range(0, 5).Characters.Count <> 5 Then RangeDeleteAndCharacters = "Count": Exit Function
    If ActiveDocument.Range(0, 5).Characters(2).Text <> "e" Then RangeDeleteAndCharacters = "Item": Exit Function
    r.SetRange 0, 6
    If r.Delete() <> 6 Then RangeDeleteAndCharacters = "returned": Exit Function
    If Left(ActiveDocument.Content.Text, 3) <> "big" Then RangeDeleteAndCharacters = "not deleted": Exit Function
    ActiveDocument.Paragraphs(1).Range.Delete
    RangeDeleteAndCharacters = IIf(Left(ActiveDocument.Content.Text, 4) = "Next", "OK", "paragraph")
End Function
Function SelectionAsRange()
    Fresh
    Selection.SetRange 0, 5
    If Selection.Text <> "Hello" Then SelectionAsRange = "SetRange": Exit Function
    If Selection.Type <> wdSelectionNormal Then SelectionAsRange = "Type": Exit Function
    Selection.InsertAfter "X"
    If Selection.Text <> "HelloX" Then SelectionAsRange = "InsertAfter": Exit Function
    Selection.InsertBefore "Y"
    If Selection.Text <> "YHelloX" Then SelectionAsRange = "InsertBefore": Exit Function
    Selection.Collapse wdCollapseStart
    If Selection.Type <> wdSelectionIP Then SelectionAsRange = "Type IP": Exit Function
    Selection.Expand wdWord
    If Left(Selection.Text, 7) <> "YHelloX" Then SelectionAsRange = "Expand": Exit Function
    Selection.MoveEnd wdCharacter, -1
    Selection.Collapse wdCollapseEnd
    Selection.Move wdCharacter, 1
    Selection.StartOf wdParagraph
    SelectionAsRange = IIf(Selection.Start = 0 And Selection.StoryType = wdMainTextStory, "OK", "StartOf " & Selection.Start)
End Function
Function ClipboardKeepsSelection()
    Fresh
    Selection.SetRange 0, 1
    ActiveDocument.Range(6, 9).Copy
    If Selection.Start <> 0 Or Selection.End <> 1 Then ClipboardKeepsSelection = "selection moved": Exit Function
    Dim r As Object
    Set r = ActiveDocument.Range(0, 0)
    r.Paste
    ClipboardKeepsSelection = IIf(Left(ActiveDocument.Content.Text, 3) = "big", "OK", "[" & Left(ActiveDocument.Content.Text, 8) & "]")
End Function
Function InsideRange()
    Dim r As Object, t As Object
    Set r = Fresh()
    Set t = ActiveDocument.Tables.Add(ActiveDocument.Paragraphs(2).Range, 2, 3)
    If ActiveDocument.Content.Tables.Count <> 1 Then InsideRange = "Tables": Exit Function
    If ActiveDocument.Range(0, 3).Tables.Count <> 0 Then InsideRange = "Tables outside": Exit Function
    If t.Cell(2, 2).Range.Rows.Count <> 1 Then InsideRange = "Rows": Exit Function
    If t.Cell(2, 2).Range.Cells.Count <> 1 Then InsideRange = "Cells": Exit Function
    If t.Cell(2, 2).Range.Information(wdWithInTable) <> True Then InsideRange = "Information": Exit Function
    If ActiveDocument.Range(0, 3).Information(wdWithInTable) <> False Then InsideRange = "Information outside": Exit Function
    t.Cell(2, 2).Select
    If Selection.Information(wdStartOfRangeRowNumber) <> 2 Then InsideRange = "row number": Exit Function
    If Selection.Information(wdMaximumNumberOfColumns) <> 3 Then InsideRange = "columns": Exit Function
    t.Delete
    ActiveDocument.Bookmarks.Add "b1", ActiveDocument.Range(0, 3)
    If ActiveDocument.Range(0, 5).Bookmarks.Count <> 1 Then InsideRange = "Bookmarks in": Exit Function
    If ActiveDocument.Range(10, 12).Bookmarks.Count <> 0 Then InsideRange = "Bookmarks out": Exit Function
    InsideRange = "OK"
End Function
Function TextFormatting()
    Dim r As Object
    Set r = Fresh()
    r.SetRange 0, 5
    r.Underline = wdUnderlineSingle
    If r.Font.Underline <> wdUnderlineSingle Then TextFormatting = "Underline": Exit Function
    r.HighlightColorIndex = wdYellow
    If r.HighlightColorIndex <> wdYellow Then TextFormatting = "Highlight " & r.HighlightColorIndex: Exit Function
    r.HighlightColorIndex = wdNoHighlight
    If r.HighlightColorIndex <> wdNoHighlight Then TextFormatting = "No highlight": Exit Function
    If ActiveDocument.Range(0, 11).ComputeStatistics(wdStatisticWords) <> 2 Then TextFormatting = "words": Exit Function
    If r.StoryType <> wdMainTextStory Then TextFormatting = "story": Exit Function
    If r.StoryLength < 40 Then TextFormatting = "story length": Exit Function
    TextFormatting = "OK"
End Function
Function StyleByName()
    Dim r As Object
    Set r = Fresh()
    ActiveDocument.Paragraphs(1).Style = "Heading 1"
    If ActiveDocument.Paragraphs(1).Style <> "Heading 1" Then StyleByName = "by name": Exit Function
    ActiveDocument.Paragraphs(1).Style = wdStyleNormal
    If ActiveDocument.Styles("Normal").NameLocal = "" Then StyleByName = "Styles(Normal)": Exit Function
    ActiveDocument.Styles("Normal").Font.Size = 13
    If ActiveDocument.Styles("Normal").Font.Size <> 13 Then StyleByName = "Normal font": Exit Function
    Selection.Style = "Normal"
    StyleByName = "OK"
End Function
"""

WORD_DIALOGS = """Function FileDialogAndFind()
    Dim d As Object
    Set d = Application.FileDialog(msoFileDialogFilePicker)
    d.Filters.Clear
    d.Filters.Add "Word", "*.docx"
    If d.Filters.Count <> 1 Then FileDialogAndFind = "Filters": Exit Function
    ActiveDocument.Content.Text = "mot hai"
    With Selection.Find
        .Text = "hai"
        .Execute
        If Not .Found Then FileDialogAndFind = "Found": Exit Function
        .Text = "khong"
        .Execute
        If .Found Then FileDialogAndFind = "not Found": Exit Function
    End With
    FileDialogAndFind = "OK"
End Function
"""
