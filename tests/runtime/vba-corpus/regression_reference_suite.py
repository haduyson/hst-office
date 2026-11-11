# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases from the comparison with the reference office suite on a Windows test PC (tests/realwin)."""

# Each one alone made the whole module fail to compile, so no procedure of the module could run.
COMPILE_3 = """Function NextTwoCounters()
    Dim i As Long, j As Long, n As Long, a(1 To 2, 1 To 3) As Long
    For i = 1 To 2: For j = 1 To 3: a(i, j) = i * 10 + j: n = n + 1: Next j, i
    If n <> 6 Or a(2, 3) <> 23 Then NextTwoCounters = "one line " & n: Exit Function
    n = 0
    For i = 1 To 2
        For j = 1 To 2
            n = n + 1
    Next j, i
    NextTwoCounters = IIf(n = 4 And i = 3, "OK", "lines " & n & " " & i)
End Function
Function ConstantDivisionByZero()
    Dim v As Variant, got As String
    On Error Resume Next
    v = 1 / 0
    got = got & Err.Number & ",": Err.Clear
    v = 5 \\ 0
    got = got & Err.Number & ",": Err.Clear
    v = 5 Mod 0
    got = got & Err.Number
    ConstantDivisionByZero = IIf(got = "11,11,11", "OK", got)
End Function
"""

SHEET_NAMES = """Function CopiedSheetName()
    Dim ws As Worksheet
    Application.DisplayAlerts = False
    Set ws = Worksheets.Add(After:=Worksheets(Worksheets.Count))
    ws.Name = "Bao cao"
    ws.Copy After:=ws
    If Worksheets(Worksheets.Count).Name <> "Bao cao (2)" Then CopiedSheetName = "copy " & Worksheets(Worksheets.Count).Name: Exit Function
    Worksheets("Bao cao (2)").Copy After:=Worksheets(Worksheets.Count)
    If Worksheets(Worksheets.Count).Name <> "Bao cao (3)" Then CopiedSheetName = "copy of copy " & Worksheets(Worksheets.Count).Name: Exit Function
    Worksheets("Bao cao (3)").Delete
    Worksheets("Bao cao (2)").Delete
    ws.Delete
    CopiedSheetName = "OK"
End Function
Function TakenSheetName()
    Dim ws As Worksheet, number As Long
    Set ws = Worksheets.Add(After:=Worksheets(Worksheets.Count))
    ws.Name = "Rieng"
    On Error Resume Next
    ws.Name = Worksheets(1).Name
    number = Err.Number
    On Error GoTo 0
    Application.DisplayAlerts = False
    ws.Delete
    TakenSheetName = IIf(number = 1004, "OK", "error " & number)
End Function
"""

FORMAT_CODES = """Function FormatMinutesQuarterPlaceholders()
    Dim d As Date, got As String
    d = DateSerial(2024, 3, 5) + TimeSerial(9, 7, 3)
    If Format(d, "yyyy-mm-dd hh:nn:ss") <> "2024-03-05 09:07:03" Then got = got & "nn " & Format(d, "yyyy-mm-dd hh:nn:ss") & ";"
    If Format(d, "h:n") <> "9:7" Then got = got & "n " & Format(d, "h:n") & ";"
    If Format(d, "q") <> "1" Then got = got & "q " & Format(d, "q") & ";"
    If Format("ab", "@@@@") <> "  ab" Then got = got & "@ [" & Format("ab", "@@@@") & "];"
    If Format("ab", "!@@@@") <> "ab  " Then got = got & "!@ [" & Format("ab", "!@@@@") & "];"
    If Format(Null) <> "" Then got = got & "Null " & Format(Null) & ";"
    If Format(d, "hh""n""nn") <> "09n07" Then got = got & "quoted " & Format(d, "hh""n""nn") & ";"
    FormatMinutesQuarterPlaceholders = IIf(got = "", "OK", got)
End Function
"""
