# SPDX-License-Identifier: AGPL-3.0-only
"""Regression cases: class modules (Implements, events) and Excel tables."""

CLASS_ATTRS = 'Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"\nAttribute VB_GlobalNameSpace = False\nAttribute VB_Creatable = False\nAttribute VB_PredeclaredId = False\nAttribute VB_Exposed = False\n'
CLASS_SHAPE = CLASS_ATTRS + """Public Function Area() As Double
End Function
"""
CLASS_SQUARE = CLASS_ATTRS + """Implements IShape
Private m As Double
Public Event Changed(x As Double)
Private Sub Class_Initialize()
    m = 2
End Sub
Public Property Get Side() As Double
    Side = m
End Property
Public Property Let Side(v As Double)
    m = v
    RaiseEvent Changed(v)
End Property
Private Function IShape_Area() As Double
    IShape_Area = m * m
End Function
Friend Function Twice() As Double
    Twice = m * 2
End Function
"""
CLASS_WATCH = CLASS_ATTRS + """Public WithEvents Target As Square
Public Seen As Double
Private Sub Target_Changed(x As Double)
    Seen = x
End Sub
"""
CLASS_USE = """Function NewClassObjects()
    Dim s As New Square
    If s.Side <> 2 Then NewClassObjects = "Initialize": Exit Function
    s.Side = 3
    If s.Twice <> 6 Then NewClassObjects = "Friend": Exit Function
    Dim t As Square
    Set t = New Square
    If t.Side <> 2 Then NewClassObjects = "second object": Exit Function
    Dim c As New Collection
    c.Add t
    If c(1).Side <> 2 Then NewClassObjects = "in Collection": Exit Function
    NewClassObjects = IIf(TypeName(t) = "Square", "OK", "TypeName " & TypeName(t))
End Function

Function ClassImplements()
    Dim i As IShape, s As New Square
    Set i = s
    s.Side = 3
    ClassImplements = IIf(i.Area() = 9, "OK", "Area " & i.Area())
End Function

Function ClassEvents()
    Dim w As New Watch, s As New Square
    Set w.Target = s
    s.Side = 7
    ClassEvents = IIf(w.Seen = 7, "OK", "Seen " & w.Seen)
End Function
"""
TABLES = """Function ListObjectsBasics()
    Dim ws As Worksheet, lo As Object, c As Object, n As Long
    Set ws = Worksheets(1)
    ws.Range("A1").Value = "Ten"
    ws.Range("B1").Value = "Tuoi"
    ws.Range("A2").Value = "An"
    ws.Range("B2").Value = 30
    ws.Range("A3").Value = "Binh"
    ws.Range("B3").Value = 40
    If ws.ListObjects.Count <> 0 Then ListObjectsBasics = "count before": Exit Function
    Set lo = ws.ListObjects.Add(xlSrcRange, ws.Range("A1:B3"), , xlYes)
    lo.Name = "BangNhanSu"
    If ws.ListObjects.Count <> 1 Then ListObjectsBasics = "count": Exit Function
    If ws.ListObjects("BangNhanSu").Range.Address <> "$A$1:$B$3" Then ListObjectsBasics = "Range " & lo.Range.Address: Exit Function
    If lo.DataBodyRange.Address <> "$A$2:$B$3" Then ListObjectsBasics = "Body": Exit Function
    If lo.HeaderRowRange.Cells(1, 2).Value <> "Tuoi" Then ListObjectsBasics = "Header": Exit Function
    If Not lo.TotalsRowRange Is Nothing Then ListObjectsBasics = "Totals": Exit Function
    If lo.ListColumns.Count <> 2 Or lo.ListRows.Count <> 2 Then ListObjectsBasics = "sizes": Exit Function
    If lo.ListColumns("Tuoi").Index <> 2 Then ListObjectsBasics = "column by name": Exit Function
    If WorksheetFunction.Sum(lo.ListColumns("Tuoi").DataBodyRange) <> 70 Then ListObjectsBasics = "sum": Exit Function
    For Each c In lo.ListColumns
        n = n + 1
    Next
    If n <> 2 Then ListObjectsBasics = "For Each": Exit Function
    lo.ListRows.Add
    If lo.ListRows.Count <> 3 Or lo.Range.Address <> "$A$1:$B$4" Then ListObjectsBasics = "add " & lo.Range.Address: Exit Function
    lo.ListRows(3).Range.Cells(1, 1).Value = "Chi"
    If ws.Range("A4").Value <> "Chi" Then ListObjectsBasics = "new row": Exit Function
    lo.Unlist
    ListObjectsBasics = IIf(ws.ListObjects.Count = 0, "OK", "Unlist")
End Function

Function CommandBarsWork()
    If Application.CommandBars.Count < 0 Then CommandBarsWork = "count": Exit Function
    Dim b As Object
    Set b = Application.CommandBars.Add("HstBar", , , True)
    If b.Name <> "HstBar" Then CommandBarsWork = "name": Exit Function
    b.Delete
    CommandBarsWork = "OK"
End Function
"""
COMPILE = """Option Explicit
Private Output As Long
Private Binary As Long

Private Function ArrayOfLong() As Long()
    Dim a(1 To 2) As Long
    a(2) = 7
    ArrayOfLong = a
End Function

Property Get ArrayProperty() As String()
    Dim a(0) As String
    a(0) = "x"
    ArrayProperty = a
End Property

Function ArrayReturnTypes()
    Dim v As Variant, w() As Long
    v = ArrayOfLong()
    If v(2) <> 7 Then ArrayReturnTypes = "v(2)": Exit Function
    w = ArrayOfLong()
    If UBound(w) <> 2 Or w(2) <> 7 Then ArrayReturnTypes = "w(2)": Exit Function
    ArrayReturnTypes = IIf(ArrayProperty()(0) = "x", "OK", "property")
End Function

Function KeywordsAsNames()
    Dim Random As Long, Access As Long, Read As Long, Base As Long, Compare As Long
    Output = 1: Binary = 2: Random = 3: Access = 4: Read = 5: Base = 6: Compare = 7
    If Output + Binary + Random + Access + Read + Base + Compare <> 28 Then KeywordsAsNames = "sum": Exit Function
    Dim Items() As Long
    ReDim Items(1 To 2)
    Items(1) = Output
    Dim f As Integer
    f = FreeFile
    Open Environ("TMPDIR") & "/kw.txt" For Output As #f
    Print #f, "line"
    Close #f
    Open Environ("TMPDIR") & "/kw.txt" For Binary Access Read As #f
    Close #f
    KeywordsAsNames = "OK"
End Function
"""
