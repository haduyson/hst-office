# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases of the Word object model."""

WORD_ONLY = """Function FindLoopRedefined()
    Dim r As Range, n As Long
    ActiveDocument.Content.Text = "hello a hello b hello"
    Set r = ActiveDocument.Content
    With r.Find
        .Text = "hello"
        .Wrap = wdFindStop
        While .Execute
            n = n + 1
            If n > 10 Then FindLoopRedefined = "never ends": Exit Function
        Wend
    End With
    FindLoopRedefined = IIf(n = 3, "OK", "found " & n)
End Function

Function FindLoopCollapsed()
    Dim r As Range, n As Long
    ActiveDocument.Content.Text = "hello a hello b hello"
    Set r = ActiveDocument.Content
    r.Find.Text = "hello"
    Do While r.Find.Execute
        n = n + 1
        If n > 10 Then FindLoopCollapsed = "never ends": Exit Function
        r.Collapse wdCollapseEnd
    Loop
    FindLoopCollapsed = IIf(n = 3, "OK", "found " & n)
End Function

Function FindInsideRange()
    Dim r As Range
    ActiveDocument.Content.Text = "aaa needle bbb"
    Set r = ActiveDocument.Range(0, 3)
    r.Find.Text = "needle"
    FindInsideRange = IIf(r.Find.Execute, "found outside the range", "OK")
End Function

Function RangeCollapseMove()
    Dim r As Range, d As Range
    ActiveDocument.Content.Text = "mot hai ba"
    Set r = ActiveDocument.Range(4, 7)
    If r.Text <> "hai" Then RangeCollapseMove = "text " & r.Text: Exit Function
    Set d = r.Duplicate
    r.Collapse wdCollapseEnd
    If r.Start <> 7 Or r.End <> 7 Then RangeCollapseMove = "collapse end": Exit Function
    d.Collapse
    If d.End <> 4 Then RangeCollapseMove = "collapse start": Exit Function
    r.SetRange 0, 3
    If r.Text <> "mot" Then RangeCollapseMove = "SetRange": Exit Function
    If r.MoveEnd(wdCharacter, 4) <> 4 Or r.Text <> "mot hai" Then RangeCollapseMove = "MoveEnd " & r.Text: Exit Function
    If r.MoveStart(wdCharacter, 4) <> 4 Or r.Text <> "hai" Then RangeCollapseMove = "MoveStart " & r.Text: Exit Function
    RangeCollapseMove = "OK"
End Function

Function ParagraphsOfRangeAndSelection()
    Dim p As Object, n As Long
    ActiveDocument.Content.Text = "mot" & vbCr & "hai" & vbCr & "ba"
    If ActiveDocument.Range(0, 5).Paragraphs.Count <> 2 Then ParagraphsOfRangeAndSelection = "range count": Exit Function
    If Left(ActiveDocument.Range(0, 5).Paragraphs(2).Range.Text, 3) <> "hai" Then ParagraphsOfRangeAndSelection = "item": Exit Function
    If Left(ActiveDocument.Paragraphs.First.Range.Text, 3) <> "mot" Then ParagraphsOfRangeAndSelection = "First": Exit Function
    If Left(ActiveDocument.Paragraphs.Last.Range.Text, 2) <> "ba" Then ParagraphsOfRangeAndSelection = "Last": Exit Function
    ActiveDocument.Content.Select
    For Each p In Selection.Paragraphs
        n = n + 1
    Next
    ParagraphsOfRangeAndSelection = IIf(n = 3 And Selection.Paragraphs.Count = 3, "OK", "selection " & n)
End Function

Function WordsSentencesFirstLast()
    ActiveDocument.Content.Text = "Mot hai. Ba bon."
    If Left(ActiveDocument.Sentences.First.Text, 3) <> "Mot" Then WordsSentencesFirstLast = "Sentences.First": Exit Function
    If Left(ActiveDocument.Sentences.Last.Text, 2) <> "Ba" Then WordsSentencesFirstLast = "Sentences.Last": Exit Function
    WordsSentencesFirstLast = IIf(Left(ActiveDocument.Words.First.Text, 3) = "Mot", "OK", "Words.First")
End Function

Function AlignmentOfStartEnd()
    ' the document says jc start, jc end and jc center, as Word writes them
    If ActiveDocument.Paragraphs(1).Format.Alignment <> wdAlignParagraphLeft Then AlignmentOfStartEnd = "start": Exit Function
    If ActiveDocument.Paragraphs(2).Alignment <> wdAlignParagraphRight Then AlignmentOfStartEnd = "end": Exit Function
    AlignmentOfStartEnd = IIf(ActiveDocument.Paragraphs(3).Format.Alignment = wdAlignParagraphCenter, "OK", "center")
End Function

Function FontColorIsBgr()
    ActiveDocument.Content.Text = "red"
    ActiveDocument.Content.Font.Color = wdColorRed
    If ThisComponent.Text.createTextCursor().CharColor <> 16711680 Then FontColorIsBgr = "stored " & ThisComponent.Text.createTextCursor().CharColor: Exit Function
    If ActiveDocument.Content.Font.Color <> wdColorRed Then FontColorIsBgr = "read " & ActiveDocument.Content.Font.Color: Exit Function
    FontColorIsBgr = IIf(ActiveDocument.Content.Font.ColorIndex = wdRed, "OK", "index " & ActiveDocument.Content.Font.ColorIndex)
End Function

Function FontColorIndex()
    Dim i As Long
    ActiveDocument.Content.Text = "x"
    ActiveDocument.Content.Font.ColorIndex = wdBlue
    If ActiveDocument.Content.Font.Color <> wdColorBlue Then FontColorIndex = "blue " & ActiveDocument.Content.Font.Color: Exit Function
    For i = 1 To 16
        ActiveDocument.Content.Font.ColorIndex = i
        If ActiveDocument.Content.Font.ColorIndex <> i Then FontColorIndex = "index " & i: Exit Function
    Next
    ActiveDocument.Content.Font.ColorIndex = wdAuto
    FontColorIndex = IIf(ActiveDocument.Content.Font.Color = wdColorAutomatic, "OK", "auto " & ActiveDocument.Content.Font.Color)
End Function
"""
