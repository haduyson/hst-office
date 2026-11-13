# SPDX-License-Identifier: AGPL-3.0-only
"""Cells and formulas typed by check-sheets-excel-formula-conventions.py, with the display expected.

Formulas are typed with {s} = argument separator, {d} = decimal separator and {sheet} = first sheet name of
the phase's locale; the expectation is the shown text (with {d}) or "error" for any #-error value.
The error rows follow the leading spreadsheet application: a number outside a function's domain is #NUM!
(hst-sheets-num-errors.patch), text or a value of the wrong type is #VALUE!.
"""
DATA = {"A1": "10", "A2": "20", "A3": "30", "B1": "Hà Nội", "B2": "Đà Nẵng", "B3": "Hà Nội", "F1": "1", "F2": "2", "F3": "3",
        "G1": "x", "G2": "y", "G3": "z"}
FORMULAS = [
    ("TRUE", "TRUE"), ("FALSE", "FALSE"), ("=TRUE", "TRUE"), ("=FALSE", "FALSE"), ("=1=1", "TRUE"),
    ("=AND(TRUE{s}FALSE)", "FALSE"), ("=VLOOKUP(2{s}F1:G3{s}2{s}FALSE)", "y"), ("=N(TRUE)", "1"),
    ("=IF(A1>5{s}\"Đạt\"{s}\"Không\")", "Đạt"), ("=SUMIF(B1:B3{s}\"Hà Nội\"{s}A1:A3)", "40"),
    ("=XLOOKUP(3{s}F1:F3{s}G1:G3)", "z"), ("=ROUND(2{d}345{s}2)", "2{d}35"),
    ("=CEILING(-2{d}5{s}2)", "-2"), ("=FLOOR(-2{d}5{s}2)", "-4"), ("=FLOOR(-2{d}5{s}-2)", "-2"), ("=CEILING(2{d}1{s}1)", "3"),
    ("=1/0", "#DIV/0!"), ("=NA()", "#N/A"), ("=VALUE(\"abc\")", "#VALUE!"),
    ("=NOSUCHFUNCTION(1)", "#NAME?"), ("=1+*2", "error"), ("=A1:A2 B3:B4", "#NULL!"),
    ("='{sheet}'!A1", "10"), ("=SUM('{sheet}'!A1:A3)", "60"), ("=INDIRECT(\"'{sheet}'!A2\")", "20"),
    ("=DOCSO(1234)", "Một nghìn hai trăm ba mươi bốn"), ("=BODAU(\"Hà Nội\")", "Ha Noi"), ("=TACHTEN(\"Nguyễn Văn An\")", "An"),
    # Numeric domain errors: #NUM! (built-in functions and the Analysis add-in).
    ("=SQRT(-1)", "#NUM!"), ("=LOG(0)", "#NUM!"), ("=LN(-1)", "#NUM!"), ("=ASIN(2)", "#NUM!"),
    ("=POWER(-1{s}0{d}5)", "#NUM!"), ("=FACT(-1)", "#NUM!"), ("=NORM.DIST(1{s}0{s}0{s}TRUE)", "#NUM!"),
    ("=CEILING(2{d}5{s}-2)", "#NUM!"), ("=FLOOR(2{d}5{s}0)", "#DIV/0!"), ("=BESSELJ(1{s}-1)", "#NUM!"),
    ("=PROB({1;2}{s}{0{d}5;0{d}6}{s}1)", "#NUM!"), ("=NETWORKDAYS.INTL(DATE(2026{s}1{s}1){s}DATE(2026{s}1{s}31){s}8)", "#NUM!"),
    ("=WORKDAY.INTL(DATE(2026{s}1{s}1){s}5{s}99)", "#NUM!"), ("=WRAPROWS({1;2;3}{s}0)", "#NUM!"),
    ("=CONVERT(1{s}\"m\"{s}\"xyz\")", "#N/A"), ("=CONVERT(1{s}\"m\"{s}\"kg\")", "#N/A"),
    ("=NETWORKDAYS.INTL(DATE(2026{s}1{s}1){s}DATE(2026{s}1{s}31){s}\"0000011\")", "22"),
    # Type errors stay #VALUE!.
    ("=NETWORKDAYS.INTL(DATE(2026{s}1{s}1){s}DATE(2026{s}1{s}31){s}\"00000x0\")", "#VALUE!"),
    ("=OPT_PROB_INMONEY(100{s}0{d}2{s}0{d}05{s}1{s}90{s}110{s}100{s}\"x\")", "#VALUE!"),
    ("=CHAR(0)", "#VALUE!"), ("=REPT(\"a\"{s}-1)", "#VALUE!"), ("=COMPLEX(1{s}1{s}\"k\")", "#VALUE!"),
]
# Vietnamese-locale dates: the default date format is DD/MM/YYYY like the regional short date (typed, DATE()).
DATES_VI = [("13/11/2026", "13/11/2026"), ("=DATE(2026{s}1{s}5)", "05/01/2026"), ("=DATE(2026{s}11{s}13)+1", "14/11/2026")]
# Input-line text of typed boolean constants: as typed, not TRUE()/FALSE().
FORMULA_TEXT = ["=TRUE", "=FALSE", "=AND(TRUE{s}FALSE)", "=IF(A1>5{s}TRUE{s}FALSE)"]
