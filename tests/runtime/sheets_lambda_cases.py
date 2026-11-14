# SPDX-License-Identifier: AGPL-3.0-only
"""LAMBDA-family and GROUPBY/PIVOTBY cases of check-sheets-excel-functions.py (same format as
sheets_excel_functions_cases.CASES; data in H1:J6). Array results are checked through SUM/INDEX because typed
formulas do not spill in this release (see hst-sheets-lambda-functions.patch).
"""
LAMBDA_NEW = ["LAMBDA", "ISOMITTED", "MAP", "REDUCE", "SCAN", "BYROW", "BYCOL", "MAKEARRAY", "GROUPBY", "PIVOTBY"]

LAMBDA_CASES = [
    ('=LAMBDA(x;x*2)(21)', "42", "_xlfn.LAMBDA(_xlpm.x,_xlpm.x*2)(21)"),
    ('=SUM(MAP(J2:J4;LAMBDA(v;v+1)))', "9", "_xlfn.MAP("),
    ('=REDUCE(0;J2:J6;LAMBDA(a;v;a+v))', "15", "_xlfn.REDUCE("),
    ('=SUM(SCAN(0;J2:J4;LAMBDA(a;v;a+v)))', "10", "_xlfn.SCAN("),
    ('=SUM(BYROW(J2:J6;LAMBDA(r;r*2)))', "30", "_xlfn.BYROW("),
    ('=SUM(BYCOL(J2:J6;SUM))', "15", "_xlfn.BYCOL(J2:J6,_xleta.SUM)"),
    ('=SUM(MAKEARRAY(2;3;LAMBDA(r;c;r*c)))', "18", "_xlfn.MAKEARRAY("),
    ('=LAMBDA(a;[b];IF(ISOMITTED(b);a;a+b))(5)', "5", "_xlfn.ISOMITTED("),
    ('=INDEX(GROUPBY(H2:H6;J2:J6;SUM);3;2)', "15", "_xlfn.GROUPBY(H2:H6,J2:J6,_xleta.SUM)"),
    ('=INDEX(GROUPBY(H2:H6;J2:J6;PERCENTOF;0;0);1;2)', "0{dec}6", "_xleta.PERCENTOF"),
    ('=INDEX(PIVOTBY(H2:H6;I2:I6;J2:J6;SUM);2;2)', "6", "_xlfn.PIVOTBY(H2:H6,I2:I6,J2:J6,_xleta.SUM)"),    ('=LET(f;LAMBDA(x;x+1);f(2))', "3", "_xlfn.LET(_xlpm.f,_xlfn.LAMBDA(_xlpm.x,_xlpm.x+1),_xlpm.f(2))"),
]
