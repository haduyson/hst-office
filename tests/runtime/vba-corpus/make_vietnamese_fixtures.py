# SPDX-License-Identifier: AGPL-3.0-only
"""Write .xlsm files whose VBA source is stored in Windows-1258 and Windows-1252. Usage: make_vietnamese_fixtures.py OUTDIR JOBS.json

Each file has assertion functions returning "OK" only when text and identifiers ran right. Vietnamese identifiers in Windows-1258
carry combining tone marks, as Office stores them. Windows-1252 has no Vietnamese, so that file covers Western accents.
"""
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vba_package  # noqa: E402

CP1258 = """Option Explicit
Public Const TIÊU_ĐỀ As String = "Báo cáo"
Public tổngTiền As Long

Function KiểmTraChuỗi()
    Dim họTên As String
    họTên = "Nguyễn Thị Hương"
    If Len("Việt") <> 4 Then KiểmTraChuỗi = "Len " & Len("Việt"): Exit Function
    If UCase("hà nội") <> "HÀ NỘI" Then KiểmTraChuỗi = "UCase " & UCase("hà nội"): Exit Function
    If Left(họTên, 6) <> "Nguyễn" Then KiểmTraChuỗi = "Left " & Left(họTên, 6): Exit Function
    If InStr(họTên, "Hương") <> 12 Then KiểmTraChuỗi = "InStr " & InStr(họTên, "Hương"): Exit Function
    If AscW(Mid("ệ", 1, 1)) <> 7879 Then KiểmTraChuỗi = "AscW " & AscW(Mid("ệ", 1, 1)): Exit Function
    KiểmTraChuỗi = "OK"
End Function

Sub TínhLương(ByVal số As Long)
    tổngTiền = số * 2
End Sub

Function KiểmTraĐịnhDanh()
    ModulTiếngViệt.TínhLương 21
    If tổngTiền <> 42 Then KiểmTraĐịnhDanh = "tổngTiền " & tổngTiền: Exit Function
    If TIÊU_ĐỀ <> "Báo cáo" Then KiểmTraĐịnhDanh = "const " & TIÊU_ĐỀ: Exit Function
    KiểmTraĐịnhDanh = "OK"
End Function

Function KiểmTraÔ()
    Worksheets("Bảng lương").Range("A1").Value = "Công ty Đà Nẵng"
    If Worksheets("Bảng lương").Range("A1").Value <> "Công ty Đà Nẵng" Then KiểmTraÔ = "ô": Exit Function
    If Worksheets(1).Name <> "Bảng lương" Then KiểmTraÔ = "tên " & Worksheets(1).Name: Exit Function
    KiểmTraÔ = "OK"
End Function

Function KiểmTraMsgBox()
    MsgBox "Xin chào Việt Nam"
    KiểmTraMsgBox = "OK"
End Function
"""
CP1252 = """Option Explicit
Public Résultat As Long

Function TestChaîne()
    Dim prénom As String
    prénom = "José Müller"
    If Len("Führer") <> 6 Then TestChaîne = "Len": Exit Function
    If UCase("déjà vu") <> "DÉJÀ VU" Then TestChaîne = "UCase " & UCase("déjà vu"): Exit Function
    If Left(prénom, 4) <> "José" Then TestChaîne = "Left": Exit Function
    If Asc("é") <> 233 Then TestChaîne = "Asc " & Asc("é"): Exit Function
    If Chr(233) <> "é" Then TestChaîne = "Chr " & AscW(Chr(233)): Exit Function
    TestChaîne = "OK"
End Function

Function TestCellule()
    Worksheets("Données").Range("A1").Value = "Évaluation à Orléans"
    If Worksheets("Données").Range("A1").Value <> "Évaluation à Orléans" Then TestCellule = "cell": Exit Function
    Résultat = 3
    If Résultat <> 3 Then TestCellule = "ident": Exit Function
    TestCellule = "OK"
End Function
"""
CP1258_FORM_CHECKS = ["KiểmTraChuỗi", "KiểmTraĐịnhDanh", "KiểmTraÔ", "KiểmTraMsgBox"]


def main():
    out, jobs_path = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    jobs = []
    files = [("vn-cp1258.xlsm", [("ModulTiếngViệt", CP1258)], 1258, "Bảng lương", CP1258_FORM_CHECKS),
             ("west-cp1252.xlsm", [("Modulé", CP1252)], 1252, "Données", ["TestChaîne", "TestCellule"])]
    for name, modules, codepage, sheet, checks in files:
        data = vba_package.xlsm(modules, codepage, sheet)
        with open(os.path.join(out, name), "wb") as handle:
            handle.write(data)
        only = [dict(library="VBAProject", module=unicodedata.normalize("NFC", modules[0][0]), proc=check, kind="Function", want="OK") for check in checks]
        jobs.append(dict(file=name, kind="calc", only=only))
    with open(jobs_path, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, ensure_ascii=False)


if __name__ == "__main__":
    main()
