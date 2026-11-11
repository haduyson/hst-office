# SPDX-License-Identifier: AGPL-3.0-only
"""VBA helper procedures and the class module the language cases call (plain VBA source text)."""

TYPES = '''Type Diem
    Ten As String
    Gia As Double
End Type

'''

HELPERS = '''Public Function Factorial(ByVal n As Long) As Double
    If n < 0 Then Err.Raise vbObjectError + 513, "Factorial", "am"
    If n <= 1 Then Factorial = 1 Else Factorial = n * Factorial(n - 1)
End Function

Public Function Opt(Optional ByVal x As Variant) As String
    If IsMissing(x) Then Opt = "missing" Else Opt = "x" & x
End Function

Public Function SumAll(ParamArray xs() As Variant) As Double
    Dim x As Variant
    For Each x In xs
        SumAll = SumAll + x
    Next
End Function

Private Sub Bump(ByRef a As Long, ByVal b As Long)
    a = a + 1
    b = b + 1
End Sub

Public Function ByRefTest() As String
    Dim a As Long, b As Long
    Bump a, b
    ByRefTest = a & "," & b
End Function

Public Function UdtTest() As String
    Dim d As Diem
    d.Ten = "But": d.Gia = 2.5
    UdtTest = d.Ten & d.Gia * 2
End Function

Public Function HandlerTest() As String
    Dim s As String
    On Error GoTo h
    s = "a"
    Err.Raise 1001, "src", "custom"
    s = s & "b"
    HandlerTest = s
    Exit Function
h:
    s = s & "[" & Err.Number & ":" & Err.Description & "]"
    Resume Next
End Function

Public Function ClassUse() As String
    Dim k As New CDiem
    k.Ten = "Ban"
    k.Gia = 4
    ClassUse = k.Ten & "=" & k.Total(3)
End Function
'''


CLASS = '''Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Private mTen As String
Public Gia As Double

Public Property Get Ten() As String
    Ten = mTen
End Property

Public Property Let Ten(ByVal value As String)
    mTen = UCase(value)
End Property

Public Function Total(ByVal n As Long) As Double
    Total = Gia * n
End Function
'''


STR_HELPERS = '''Public Function MidStmt() As String
    Dim s As String
    s = "abcdef"
    Mid(s, 2, 3) = "XYZ"
    MidStmt = s
End Function

Public Function LSetTest() As String
    Dim a As String * 5, b As String * 5
    LSet a = "ab"
    RSet b = "ab"
    LSetTest = "[" & a & "][" & b & "]"
End Function
'''


VN_HELPERS = '''Public Function DictVn() As String
    Dim d As Object
    Set d = CreateObject("Scripting.Dictionary")
    d.CompareMode = vbTextCompare
    d.Add U("H{e0} N{1ed9}i"), 1
    DictVn = d.Exists(U("h{e0} n{1ed9}i")) & "," & d.Exists(U("HA NOI"))
End Function

Public Function FileRoundTrip() As String
    Dim f As Integer, path As String, ln As String, s As String
    s = U("Ti{1ebf}ng Vi{1ec7}t caf{e9}")
    path = "C:\\hst-test\\vba-tmp-ansi.txt"
    f = FreeFile
    Open path For Output As #f
    Print #f, s
    Close #f
    f = FreeFile
    Open path For Input As #f
    Line Input #f, ln
    Close #f
    Kill path
    FileRoundTrip = (ln = s) & "|" & Len(ln) & "|" & Right(ln, 4)
End Function

Public Function Utf8Stream() As String
    Dim st As Object, path As String, back As String
    path = "C:\\hst-test\\vba-tmp-utf8.txt"
    Set st = CreateObject("ADODB.Stream")
    st.Type = 2: st.Charset = "utf-8": st.Open
    st.WriteText U("Ti{1ebf}ng Vi{1ec7}t")
    st.SaveToFile path, 2
    st.Close
    st.Open: st.LoadFromFile path
    back = st.ReadText
    st.Close
    Kill path
    Utf8Stream = (back = U("Ti{1ebf}ng Vi{1ec7}t")) & "|" & Len(back)
End Function
'''


# The literal file: Vietnamese typed into the VBA source with a Vietnamese code page (1258), as a VBE on a
# Vietnamese-locale Windows stores it. A reference suite on a Western code page decodes these bytes differently.
LITERAL = '''Public Function LiteralVn() As String
    Dim s As String
    s = "Hà Nội"
    LiteralVn = Len(s) & "|" & AscW(Mid(s, 2, 1)) & "|" & AscW(Mid(s, 6, 1))
End Function
'''
