# SPDX-License-Identifier: AGPL-3.0-only
"""Count Excel and Word object-model use across the scanned macros, as data: nothing runs.

Usage: census.py OUT.json TREE SCAN.jsonl... TREE is the LibreOffice source, for what its VBA API (oovbaapi) declares.
"""
import collections
import glob
import json
import os
import re
import sys

STRING = re.compile(r'"(?:[^"\n]|"")*"')
COMMENT = re.compile(r"(?m)^[ \t]*(?:'|Rem\b).*$|'[^\n]*$", re.I)
MEMBER = re.compile(r"\.\s*([A-Za-z_]\w*)")
DECL = re.compile(r"\b(?:Sub|Function|Property\s+(?:Get|Let|Set)|Dim|Public|Private|Const|Type|Enum|Global)\s+(?:WithEvents\s+)?([A-Za-z_]\w*)", re.I)
TYPE_FIELD = re.compile(r"(?m)^\s*([A-Za-z_]\w*)\s+As\s+")
FAMILIES = {
    "excel": ["Range", "Cells", "Worksheets", "Sheets", "Selection", "ActiveSheet", "ActiveCell", "ActiveWorkbook", "ThisWorkbook", "Workbooks",
              "Rows", "Columns", "UsedRange", "CurrentRegion", "Offset", "Resize", "End", "Find", "AutoFilter", "Sort", "PasteSpecial", "Copy",
              "PivotTables", "PivotCaches", "Charts", "ChartObjects", "Shapes", "Names", "Validation", "FormatConditions", "Hyperlinks", "Comments",
              "ListObjects", "QueryTables", "PageSetup", "Windows", "Interior", "Font", "Borders", "NumberFormat", "Formula", "FormulaR1C1", "Value", "Value2"],
    "word": ["ActiveDocument", "ThisDocument", "Documents", "Selection", "Bookmarks", "Tables", "Find", "Paragraphs", "Sections", "Fields", "InlineShapes",
             "Shapes", "Styles", "ContentControls", "FormFields", "MailMerge", "TablesOfContents", "Headers", "Footers", "Revisions", "Comments",
             "Words", "Sentences", "Characters", "PageSetup", "ListFormat", "ParagraphFormat", "HomeKey", "EndKey", "MoveRight", "MoveLeft", "TypeText",
             "InsertBreak", "InsertFile", "CustomProperties", "BuiltInDocumentProperties", "Variables", "Hyperlinks", "Range"],
}
PATTERNS = {
    "Scripting.Dictionary": r"Scripting\.Dictionary", "FileSystemObject": r"FileSystemObject", "RegExp": r"VBScript\.RegExp|\bRegExp\b",
    "ADODB": r"ADODB\.", "WScript": r"WScript\.", "XMLHTTP": r"XMLHTTP|WinHttp", "Declare API": r"(?m)^\s*(Public\s+|Private\s+)?Declare\b",
    "Collection": r"\bNew Collection\b", "MsgBox": r"\bMsgBox\b", "InputBox": r"\bInputBox\b", "UserForm .Show": r"\.Show\b", "Class module": r"\bNew [A-Z]\w+",
    "On Error Resume Next": r"On Error Resume Next", "Application.Run": r"Application\.Run\b", "GetOpenFilename": r"GetOpenFilename", "Dir()": r"\bDir\(",
    "File I/O": r"(?m)^\s*Open .* For ", "Workbooks.Open": r"Workbooks\.Open", "Documents.Open": r"Documents\.Open", "Excel.Application": r"Excel\.Application",
    "Word.Application": r"Word\.Application", "ThisWorkbook.Path": r"ThisWorkbook\.Path", "Application.OnTime": r"Application\.OnTime", "Evaluate": r"\bEvaluate\b",
}
EVENT = re.compile(r"(?m)^\s*(?:Private\s+|Public\s+)?Sub\s+((?:Workbook|Worksheet|Document|UserForm|Auto|App|Chart)_?\w+|\w+_(?:Click|Change|Initialize|Activate|Terminate|DblClick|KeyPress|Exit|AfterUpdate))\b", re.I)


def idl_members(tree):
    members = collections.defaultdict(set)
    for path in glob.glob(os.path.join(tree, "oovbaapi/ooo/vba/**/*.idl"), recursive=True):
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = re.sub(r"/\*.*?\*/|//[^\n]*", "", handle.read(), flags=re.S)
        interface = os.path.basename(path)[:-4]
        for match in re.finditer(r"(?:\[attribute[^\]]*\]\s*[\w:<>]+(?:\s+\w+)?\s+|[\w:<>]+\s+)(\w+)\s*(?:\(|;|\{)", text):
            members[match.group(1).lower()].add(interface)
    return members


def clean(code):
    return COMMENT.sub("", STRING.sub('""', code))


def main():
    out_path, tree = sys.argv[1], sys.argv[2]
    idl = idl_members(tree)
    member_files, member_count, family, pattern, events = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    kinds = collections.Counter()
    for scan_path in sys.argv[3:]:
        with open(scan_path, encoding="utf-8") as handle:
            for line in handle:
                scan = json.loads(line)
                if not scan.get("has_macros"):
                    continue
                ext = os.path.splitext(scan["name"])[1].lower()
                app = "word" if ext.startswith((".do")) else "excel"
                kinds[app] += 1
                code = "\n".join(m["code"] or "" for m in scan.get("modules", []))
                raw_patterns = {name for name, rx in PATTERNS.items() if re.search(rx, code, re.I)}
                for name in raw_patterns:
                    pattern[(app, name)] += 1
                stripped = clean(code)
                declared = {d.lower() for d in DECL.findall(stripped)} | {f.lower() for f in TYPE_FIELD.findall(stripped)}
                members = collections.Counter(m for m in MEMBER.findall(stripped))
                seen = set()
                for member, count in members.items():
                    key = member.lower()
                    member_count[(app, key)] += count
                    if key not in seen and key not in declared:
                        member_files[(app, key)] += 1
                        seen.add(key)
                for name in FAMILIES[app]:
                    if re.search(rf"\b{name}\b", stripped):
                        family[(app, name)] += 1
                for event in {e.lower() for e in EVENT.findall(code)}:
                    events[(app, event)] += 1
    rows = [dict(app=a, member=m, files=n, uses=member_count[(a, m)], in_idl=m in idl, interfaces=sorted(idl.get(m, ()))[:4]) for (a, m), n in member_files.most_common()]
    result = dict(files=kinds, members=rows, families=[dict(app=a, name=n, files=c) for (a, n), c in family.most_common()],
                  patterns=[dict(app=a, name=n, files=c) for (a, n), c in pattern.most_common()],
                  events=[dict(app=a, name=n, files=c) for (a, n), c in events.most_common(60)])
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=0, ensure_ascii=False)
    print(dict(kinds), len(rows))


if __name__ == "__main__":
    main()
