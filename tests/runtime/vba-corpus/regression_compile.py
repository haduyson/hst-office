# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases: code real files have and the Basic compiler refused, each also checking what it does."""

COMPILE_2 = """Function ElseAfterCall()
    Dim r As Long
    If 1 = 2 Then Bump r, 1 Else Bump r, 2
    If r <> 2 Then ElseAfterCall = "Then or Else": Exit Function
    If 1 = 1 Then Bump r, 5 Else Bump r, 100
    If r <> 7 Then ElseAfterCall = "second": Exit Function
    If 1 = 2 Then Bump r, 1 Else If 1 = 3 Then Bump r, 2 Else Bump r, 3
    ElseAfterCall = IIf(r = 10, "OK", "Else If " & r)
End Function
Private Sub Bump(ByRef x As Long, ByVal y As Long)
    x = x + y
End Sub
Function StepAsName()
    Dim step As Long, i As Long, n As Long
    step = 2
    For i = 1 To 5 Step step
        n = n + 1
    Next
    If n <> 3 Then StepAsName = "Step var " & n: Exit Function
    n = 0
    For i = 1 To step Step 1
        n = n + 1
    Next
    StepAsName = IIf(n = 2, "OK", "To var " & n)
End Function
Public Property Get Property(ByVal Name As String) As Variant
    Property = Name & "!"
End Property
Function PropertyAsName()
    Dim property As String
    property = "a"
    PropertyAsName = IIf(property & Me_Property() = "aa!", "OK", property)
End Function
Private Function Me_Property()
    Me_Property = Property("a")
End Function
Function NumberedLines()
    Dim n As Long
10  n = 1
20  GoTo 40
30  n = 100
40  n = n + 1
    On Error GoTo 900
50  Err.Raise 5
60  n = 100
900 NumberedLines = IIf(n = 2, "OK", "n " & n)
End Function
Function WithNewAndBang()
    With New Collection
        .Add 7
        If .Count <> 1 Then WithNewAndBang = "With New": Exit Function
    End With
    Dim d As Object
    Set d = ActiveSheet.Range("A1")
    With ActiveSheet
        !Name = .Name
    End With
    WithNewAndBang = "OK"
End Function
Function DatesWithBlanks()
    If Hour(#5:07:49 PM#) <> 17 Then DatesWithBlanks = "PM": Exit Function
    If Minute(#1/2/2020 5:07 AM#) <> 7 Then DatesWithBlanks = "date and time": Exit Function
    If Hour(#17:07#) <> 17 Then DatesWithBlanks = "24 h": Exit Function
    Dim f As Integer
    f = FreeFile
    Open Environ("TMPDIR") & "/d.txt" For Output As #f
    Print #f, "a": Close #f
    DatesWithBlanks = IIf(Year(#1/2/2020#) = 2020, "OK", "date")
End Function
Enum KindOf
    KindFirst = 4
End Enum
Function EnumDefault(Optional p As KindOf = KindOf.KindFirst)
    EnumDefault = p
End Function
Function EnumDefaultValue()
    EnumDefaultValue = IIf(EnumDefault() = 4, "OK", "value " & EnumDefault())
End Function
Function OrdinalInName()
    Dim Numero\u00ba As Long
    Numero\u00ba = 3
    OrdinalInName = IIf(Numero\u00ba = 3, "OK", "value")
End Function
Private Function CountOf(c As Object) As Long
    CountOf = c.Count
End Function
Function NewAsArgument()
    Dim n As Long
    n = CountOf(New Collection)
    TakeNew New Collection
    NewAsArgument = IIf(n = 0, "OK", "count")
End Function
Private Sub TakeNew(c As Object)
    c.Add 1
End Sub
Private Function DefaultNull(Optional x As Variant = Null)
    DefaultNull = IsNull(x)
End Function
Private Function DefaultOffice(Optional o As XlSortOrder = xlDescending)
    DefaultOffice = o
End Function
Function DefaultsOfOptional()
    If Not DefaultNull() Then DefaultsOfOptional = "Null": Exit Function
    If DefaultNull(1) Then DefaultsOfOptional = "given": Exit Function
    DefaultsOfOptional = IIf(DefaultOffice() = xlDescending, "OK", "Office " & DefaultOffice())
End Function
Type Buffer
    Items() As Long
    Count As Long
End Type
Function ReDimOfMember()
    Dim b As Buffer
    ReDim b.Items(1 To 3)
    b.Items(3) = 7
    If UBound(b.Items) <> 3 Then ReDimOfMember = "bound": Exit Function
    ReDim Preserve b.Items(1 To 5)
    If b.Items(3) <> 7 Or UBound(b.Items) <> 5 Then ReDimOfMember = "preserve": Exit Function
    With b
        ReDim .Items(2)
        If UBound(.Items) <> 2 Or b.Items(1) <> 0 Then ReDimOfMember = "With": Exit Function
    End With
    ReDimOfMember = "OK"
End Function
"""
