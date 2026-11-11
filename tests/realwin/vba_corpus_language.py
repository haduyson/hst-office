# SPDX-License-Identifier: AGPL-3.0-only
"""Host-independent VBA language cases: loops, arrays, collections, strings, dates, Format, errors, Vietnamese text.

They run in a workbook and again in a Word document, so a difference between hosts shows up too.
"""
from vba_corpus_kit import checks, vn
from vba_corpus_language_helpers import CLASS, HELPERS, LITERAL, STR_HELPERS, TYPES, VN_HELPERS  # noqa: F401

HANOI, HANOI_UP = "Hà Nội", "HÀ NỘI"

LOOPS = checks("LangLoops", [
    ("#", "Dim i As Long, s As Long, t As String, a() As Long, c As Collection, d As Object, x As Variant"),
    ("#", "s = 0: For i = 1 To 10 Step 3: s = s + i: Next i"), ("forStep", "s"),
    ("#", "t = \"\": For i = 10 To 1 Step -4: t = t & i & \",\": Next"), ("forDown", "t"),
    ("#", "s = 0: For Each x In Array(1, 2, 3, 4): If x = 3 Then Exit For\n    s = s + x: Next"), ("forEachExit", "s"),
    ("#", "i = 0: Do While i < 5: i = i + 2: Loop"), ("doWhile", "i"),
    ("#", "i = 0: Do: i = i + 1: Loop Until i >= 4"), ("loopUntil", "i"),
    ("#", "i = 0: While i < 3: i = i + 1: Wend"), ("whileWend", "i"),
    ("#", "ReDim a(1 To 3): a(1) = 5: ReDim Preserve a(1 To 5): a(5) = 9"), ("redimKeep", "a(1) + a(5)"),
    ("lbound", "LBound(a)"), ("ubound", "UBound(a)"),
    ("#", "Dim m(1 To 2, 0 To 4) As String"), ("ubound2", "UBound(m, 2)"),
    ("split", "UBound(Split(\"a,b,,c\", \",\"))"), ("splitLimit", "Split(\"a,b,c\", \",\", 2)(1)"),
    ("join", "Join(Array(\"x\", \"y\", \"z\"), \"-\")"), ("filter", "Join(Filter(Array(\"an\", \"binh\", \"lan\"), \"an\"), \"|\")"),
    ("#", "Set c = New Collection: c.Add 10, \"a\": c.Add 20, \"b\": c.Add 15, Before:=1"),
    ("collCount", "c.Count"), ("collKey", "c(\"b\")"), ("collFirst", "c(1)"),
    ("#", "c.Remove \"a\""), ("collAfterRemove", "c.Count"), ("collMissing", "c(\"zz\")"),
    ("#", "Set d = CreateObject(\"Scripting.Dictionary\"): d.Add \"k1\", 1: d(\"k2\") = 2: d.CompareMode = 1"),
    ("dictCount", "d.Count"), ("dictExists", "d.Exists(\"k1\")"), ("dictKeys", "Join(d.Keys, \",\")"),
    ("!dictDup", "d.Add \"k1\", 3"),
    ("chooseIIf", "Choose(2, \"a\", \"b\", \"c\") & IIf(5 > 3, \"Y\", \"N\") & Switch(False, 1, True, 2)"),
    ("intDiv", "17 \\ 5"), ("modOp", "-17 Mod 5"), ("power", "2 ^ 10"), ("strPlusNum", "\"1\" + 2"), ("concatNum", "\"1\" & 2"),
    ("roundBank", "Round(2.5) & \",\" & Round(3.5) & \",\" & Round(2.345, 2)"), ("cintBank", "CInt(2.5) & \",\" & CInt(3.5)"),
    ("intFix", "Int(-2.5) & \",\" & Fix(-2.5)"), ("overflow", "CInt(40000)"), ("divZero", "1 / (s - s)"), ("typeMismatch", "CLng(\"abc\")"),
    ("val", "Val(\"12.5abc\") + Val(\"&H1F\")"), ("hexOct", "Hex(255) & \",\" & Oct(8)"),
    ("isNumeric", "IsNumeric(\"1e3\") & \",\" & IsNumeric(\"\") & \",\" & IsNumeric(\"12,5\")"),
    ("like", "(\"abc\" Like \"a*\") & (\"a1\" Like \"a#\") & (\"B\" Like \"[A-C]\") & (\"b\" Like \"[!a]\")"),
    ("typeNames", "TypeName(1) & \",\" & TypeName(1.5) & \",\" & TypeName(\"s\") & \",\" & TypeName(Nothing) & \",\" & TypeName(Empty)"),
    ("cdblDot", "CDbl(\"1.5\")"), ("cstrDouble", "CStr(1.5)"), ("ccur", "CCur(1.23456)"),
    ("errRaise", "Factorial(-1)"), ("recursion", "Factorial(10)"),
    ("optional", "Opt() & \",\" & Opt(5)"), ("paramArray", "SumAll(1, 2, 3.5)"),
    ("byRef", "ByRefTest()"), ("udt", "UdtTest()"), ("errHandler", "HandlerTest()"),
])

STRINGS = checks("LangStrings", [
    ("#", "Dim s As String: s = \"  Xin chao Viet Nam  \""),
    ("trim", "\"[\" & Trim(s) & \"][\" & LTrim(s) & \"][\" & RTrim(s) & \"]\""), ("len", "Len(s)"),
    ("leftRightMid", "Left(Trim(s), 3) & \"|\" & Right(Trim(s), 3) & \"|\" & Mid(Trim(s), 5, 4)"), ("midNoLen", "Mid(\"abcdef\", 3)"),
    ("instr", "InStr(s, \"Viet\") & \",\" & InStr(1, s, \"viet\", vbTextCompare) & \",\" & InStr(1, s, \"viet\")"),
    ("instrRev", "InStrRev(\"a.b.c\", \".\")"), ("replace", "Replace(\"a-b-c-d\", \"-\", \"+\", 1, 2)"),
    ("replaceStart", "Replace(\"a-b-c-d\", \"-\", \"+\", 3)"), ("replaceText", "Replace(\"AbAB\", \"ab\", \"x\", , , vbTextCompare)"),
    ("case", "UCase(\"abc\") & LCase(\"DEF\")"), ("proper", "StrConv(\"xin CHAO ban\", vbProperCase)"),
    ("reverse", "StrReverse(\"abc\")"), ("space", "\"[\" & Space(3) & String(3, \"x\") & String(2, 65) & \"]\""),
    ("asc", "Asc(\"A\") & \",\" & Chr(66) & \",\" & AscW(\"z\") & \",\" & ChrW(8364)"),
    ("strComp", "StrComp(\"a\", \"B\") & \",\" & StrComp(\"a\", \"B\", vbTextCompare) & \",\" & StrComp(\"abc\", \"ABC\", 1)"),
    ("compareOp", "(\"a\" < \"B\") & \",\" & (\"a\" = \"A\")"), ("crlf", "Len(vbCrLf) & Len(vbNewLine) & Len(vbTab)"),
    ("midStmt", "MidStmt()"), ("lset", "LSetTest()"), ("strDollar", "Left$(\"hello\", 2) & UCase$(\"x\")"),
    ("formatDollar", "Format$(3.14159, \"0.00\")"), ("str", "Str(42) & \"|\" & Str(-1.5)"),
    ("splitJoinLoop", "Join(Split(\"1 2 3\"), \"+\")"), ("chrNull", "Len(Chr(0))"),
])

DATES = checks("LangDates", [
    ("#", "Dim d As Date: d = DateSerial(2024, 3, 15) + TimeSerial(14, 30, 5)"),
    ("dateSerialOverflow", "DateSerial(2024, 2, 30)"), ("dateSerialNeg", "DateSerial(2024, 1, 0)"),
    ("dateAddMonth", "DateAdd(\"m\", 1, #1/31/2024#)"), ("dateAddDay", "DateAdd(\"d\", -20, d)"), ("dateAddQ", "DateAdd(\"q\", 1, d)"),
    ("dateAddHour", "DateAdd(\"h\", 12, d)"), ("dateDiffD", "DateDiff(\"d\", #1/1/2024#, d)"), ("dateDiffM", "DateDiff(\"m\", #12/31/2023#, #1/1/2024#)"),
    ("dateDiffWw", "DateDiff(\"ww\", #1/1/2024#, d)"), ("dateDiffYyyy", "DateDiff(\"yyyy\", #12/31/2023#, #1/1/2024#)"),
    ("datePart", "DatePart(\"q\", d) & \",\" & DatePart(\"y\", d) & \",\" & DatePart(\"ww\", d) & \",\" & DatePart(\"w\", d)"),
    ("weekday", "Weekday(d) & \",\" & Weekday(d, vbMonday)"), ("ymdhms", "Year(d) & Month(d) & Day(d) & Hour(d) & Minute(d) & Second(d)"),
    ("monthName", "MonthName(3) & \",\" & MonthName(3, True)"), ("weekdayName", "WeekdayName(1) & \",\" & WeekdayName(6, True)"),
    ("timeSerial", "TimeSerial(25, 0, 0)"), ("dateValueIso", "DateValue(\"2024-03-15\")"), ("timeValue", "TimeValue(\"14:30\")"),
    ("cdateIso", "CDate(\"2024-03-15 08:00\")"), ("cdateDmy", "CDate(\"15/03/2024\")"), ("cdateMdy", "CDate(\"3/15/2024\")"),
    ("isDate", "IsDate(\"2024-02-30\") & \",\" & IsDate(\"2024-02-29\") & \",\" & IsDate(\"abc\")"),
    ("dateLiteral", "#3/15/2024#"), ("dateToLong", "CLng(#1/1/2024#)"), ("dateToDouble", "CDbl(d)"),
    ("dateArith", "d + 1.5"), ("dateCompare", "(d > #3/15/2024#) & (Int(d) = #3/15/2024#)"),
    ("dateSerialType", "TypeName(DateSerial(2024, 1, 1))"), ("nowYear", "Year(Now) = Year(Date)"), ("timerType", "TypeName(Timer)"),
    ("dateAddLeap", "DateAdd(\"yyyy\", 1, #2/29/2024#)"), ("cdateNumber", "CDate(45366.5)"),
])

FORMAT = checks("LangFormat", [
    ("#", "Dim d As Date: d = DateSerial(2024, 3, 5) + TimeSerial(9, 7, 3)"),
    ("thousands", "Format(1234567.891, \"#,##0.00\")"), ("percent", "Format(0.256, \"0.0%\")"), ("zeros", "Format(5, \"000\")"),
    ("sections", "Format(-3, \"0;(0)\") & \"|\" & Format(0, \"0;-0;\"\"zero\"\"\")"), ("roundHalf", "Format(2.5, \"0\") & Format(3.5, \"0\")"),
    ("twoDp", "Format(12.345, \"0.00\") & \"|\" & Format(12.355, \"0.00\")"), ("sci", "Format(12345, \"0.00E+00\")"),
    ("named", "Format(1234.5, \"Fixed\") & \"|\" & Format(1234.5, \"Standard\") & \"|\" & Format(0.5, \"Percent\")"),
    ("currency", "Format(1234.5, \"Currency\")"), ("yesNo", "Format(True, \"Yes/No\") & Format(0, \"True/False\")"),
    ("generalNumber", "Format(1234.5)"), ("textUpper", "Format(\"abc\", \">\") & Format(\"ABC\", \"<\")"), ("at", "Format(\"ab\", \"@@@@\")"),
    ("dmy", "Format(d, \"dd/mm/yyyy\")"), ("iso", "Format(d, \"yyyy-mm-dd hh:nn:ss\")"), ("dmShort", "Format(d, \"d/m/yy\")"),
    ("ampm", "Format(d, \"h:mm AM/PM\")"), ("dddd", "Format(d, \"dddd\") & \"|\" & Format(d, \"ddd\")"),
    ("mmmm", "Format(d, \"mmmm\") & \"|\" & Format(d, \"mmm\")"), ("longDate", "Format(d, \"Long Date\")"),
    ("shortDate", "Format(d, \"Short Date\")"), ("formatNumber", "FormatNumber(1234.5, 2)"), ("formatPercent", "FormatPercent(0.1234, 1)"),
    ("formatCurrency", "FormatCurrency(1234.5)"), ("formatDateTime", "FormatDateTime(d, vbShortDate) & \"|\" & FormatDateTime(d, vbLongTime)"),
    ("quarter", "Format(d, \"q\")"), ("escaped", "Format(5, \"\\#0\")"), ("literal", "Format(7, \"\"\"No. \"\"0\")"),
    ("nullFormat", "Format(Null)"), ("emptyFormat", "\"[\" & Format(\"\", \"0\") & \"]\""), ("negZero", "Format(-0.001, \"0.00\")"),
])

VIETNAMESE = checks("LangVietnamese", [
    ("#", f"Dim s As String, t As String: s = {vn(HANOI)}: t = {vn('đường phố')}"),
    ("len", "Len(s)"), ("ucase", f"UCase(s) = {vn(HANOI_UP)}"), ("ucaseText", "UCase(t)"), ("lcase", f"LCase({vn('ĐÀ NẴNG')})"),
    ("ascw", "AscW(Mid(s, 6, 1)) & \",\" & AscW(Left(t, 1))"), ("instr", f"InStr(s, {vn('Nội')})"),
    ("instrText", f"InStr(1, s, {vn('NỘI')}, vbTextCompare)"), ("strCompText", f"StrComp(s, {vn(HANOI_UP)}, vbTextCompare)"),
    ("replace", f"Replace(t, {vn('phố')}, {vn('làng')})"), ("proper", f"StrConv({vn('nguyễn văn an')}, vbProperCase)"),
    ("compareOrder", f"({vn('Đức')} > {vn('Dũng')}) & \",\" & ({vn('Ánh')} > \"An\")"),
    ("like", f"(s Like \"H*\") & (s Like {vn('*Nội')})"), ("reverse", "StrReverse(s)"), ("mid", "Mid(t, 2, 4)"),
    ("nfdLen", "Len(U(\"Ha{300}\"))"), ("ansiChr", "Chr(208) & \",\" & Asc(" + vn("Đ") + ")"),
    ("dictKey", "DictVn()"), ("fileRoundTrip", "FileRoundTrip()"), ("utf8Stream", "Utf8Stream()"),
])

SOURCE = "\n".join([TYPES, LOOPS, HELPERS, STRINGS, STR_HELPERS, DATES, FORMAT, VIETNAMESE, VN_HELPERS,
                    checks("LangClass", [("classUse", "ClassUse()")], declare="")])
MODULES = [("Cases", SOURCE), ("CDiem", CLASS)]
FUNCTIONS = ["LangLoops", "LangStrings", "LangDates", "LangFormat", "LangVietnamese", "LangClass"]

# Constructs that stop a whole module from compiling where Basic differs; kept apart so the other cases run.
COMPILE = """Public Function CompileNextTwo() As String
    Dim i As Long, j As Long, n As Long
    For i = 1 To 2: For j = 1 To 3: n = n + 1: Next j, i
    CompileNextTwo = "n=" & n & "|i=" & i
End Function

Public Function CompileDivZero() As String
    Dim v As Variant, got As String
    On Error Resume Next
    v = 1 / 0
    got = Err.Number & ",": Err.Clear
    v = 5 \\ 0
    got = got & Err.Number & ",": Err.Clear
    v = 5 Mod 0
    CompileDivZero = got & Err.Number
End Function
"""
