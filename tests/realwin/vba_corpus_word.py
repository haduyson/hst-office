# SPDX-License-Identifier: AGPL-3.0-only
"""Word object-model cases on a document with three paragraphs: text, Find/Replace, tables, properties, events."""
from vba_corpus_kit import checks, document_module, vn

DOC = "Dim doc As Object, r As Object"
START = ("#", "Set doc = ActiveDocument")

TEXT = checks("WdText", [
    START, ("paragraphs", "doc.Paragraphs.Count"), ("p1", "doc.Paragraphs(1).Range.Text"), ("contentLen", "Len(doc.Content.Text)"),
    ("words", "doc.Words.Count"), ("characters", "doc.Characters.Count"), ("sentences", "doc.Sentences.Count"),
    ("sentence1", "doc.Sentences(1).Text"), ("rangeText", "doc.Range(0, 5).Text"), ("rangeEnd", "doc.Content.End"),
    ("firstWord", "doc.Words(1).Text"), ("lastParagraph", "doc.Paragraphs.Last.Range.Text"),
    ("!insertAfter", "doc.Content.InsertAfter \" Them\""), ("afterInsert", "doc.Paragraphs.Last.Range.Text"),
    ("!insertParagraph", "doc.Content.InsertParagraphAfter: doc.Content.InsertAfter \"Moi\""), ("paragraphsAfter", "doc.Paragraphs.Count"),
    ("!insertBefore", "doc.Paragraphs(1).Range.InsertBefore \">> \""), ("afterInsertBefore", "doc.Paragraphs(1).Range.Text"),
    ("!bold", "doc.Paragraphs(1).Range.Font.Bold = True"), ("boldRead", "doc.Paragraphs(1).Range.Font.Bold"),
    ("mixedBold", "doc.Content.Font.Bold"), ("!font", "doc.Paragraphs(2).Range.Font.Name = \"Arial\": doc.Paragraphs(2).Range.Font.Size = 14"),
    ("fontRead", "doc.Paragraphs(2).Range.Font.Name & \",\" & doc.Paragraphs(2).Range.Font.Size"),
    ("!align", "doc.Paragraphs(2).Alignment = wdAlignParagraphCenter"), ("alignRead", "doc.Paragraphs(2).Alignment"),
    ("!heading", "doc.Paragraphs(3).Style = doc.Styles(wdStyleHeading1)"), ("headingName", "doc.Paragraphs(3).Style"),
    ("!styleByName", "doc.Paragraphs(3).Style = \"Normal\""), ("styleByNameRead", "doc.Paragraphs(3).Style"),
    ("!selection", "Selection.HomeKey Unit:=wdStory: Selection.TypeText \"X\""), ("selectionStart", "Selection.Start"),
    ("afterTypeText", "Left(doc.Paragraphs(1).Range.Text, 4)"),
    ("!bookmark", "doc.Bookmarks.Add \"bm1\", doc.Range(0, 5)"), ("bookmarkExists", "doc.Bookmarks.Exists(\"bm1\")"),
    ("bookmarkText", "doc.Bookmarks(\"bm1\").Range.Text"), ("bookmarkCount", "doc.Bookmarks.Count"),
    ("#", "Set r = doc.Content: r.Collapse wdCollapseEnd"), ("!table", "doc.Tables.Add r, 2, 3"), ("tables", "doc.Tables.Count"),
    ("!cellWrite", f"doc.Tables(1).Cell(1, 1).Range.Text = {vn('Số')}"), ("cellText", "doc.Tables(1).Cell(1, 1).Range.Text"),
    ("tableShape", "doc.Tables(1).Rows.Count & \",\" & doc.Tables(1).Columns.Count"),
    ("!header", "doc.Sections(1).Headers(wdHeaderFooterPrimary).Range.Text = \"Dau trang\""),
    ("headerText", "doc.Sections(1).Headers(wdHeaderFooterPrimary).Range.Text"),
    ("!margin", "doc.PageSetup.TopMargin = CentimetersToPoints(2)"), ("marginRead", "Round(doc.PageSetup.TopMargin, 1)"),
    ("orientation", "doc.PageSetup.Orientation"), ("nameExt", "LCase(Right(doc.Name, 5))"), ("fullNameHasPath", "InStr(doc.FullName, \"\\\") > 0"),
    ("#", f"doc.Content.InsertAfter {vn('Tiếng Việt có dấu')}"), ("vnReadBack", f"InStr(doc.Content.Text, {vn('Tiếng Việt có dấu')}) > 0"),
    ("vnLastChars", "AscW(Mid(doc.Content.Text, Len(doc.Content.Text) - 1, 1))"),
], declare=DOC)

FIND = checks("WdFind", [
    START, ("#", "Set r = doc.Content"),
    ("replaceAll", "r.Find.Execute(FindText:=\"world\", ReplaceWith:=\"Viet Nam\", Replace:=wdReplaceAll)"),
    ("afterReplace", "InStr(doc.Content.Text, \"world\") & \",\" & (Len(doc.Content.Text) - Len(Replace(doc.Content.Text, \"Viet Nam\", \"\"))) / 8"),
    ("#", "Set r = doc.Content"), ("matchCaseMiss", "r.Find.Execute(FindText:=\"hello\", MatchCase:=True)"),
    ("#", "Set r = doc.Content"), ("matchCaseHit", "r.Find.Execute(FindText:=\"hello\", MatchCase:=False)"), ("foundRange", "r.Text & \"@\" & r.Start"),
    ("#", "Set r = doc.Content"), ("wildcard", "r.Find.Execute(FindText:=\"S[a-z]{5}\", MatchWildcards:=True)"), ("wildcardText", "r.Text"),
    ("#", "Set r = doc.Content"), ("wholeWord", "r.Find.Execute(FindText:=\"line\", MatchWholeWord:=True)"),
    ("#", "Set r = doc.Content"),
    ("replaceVn", f"r.Find.Execute(FindText:=\"Next\", ReplaceWith:={vn('Tiếp')}, Replace:=wdReplaceAll)"),
    ("vnInText", f"InStr(doc.Content.Text, {vn('Tiếp paragraph')}) > 0"),
    ("#", "Set r = doc.Content"), ("findVn", f"r.Find.Execute(FindText:={vn('tiếp')}, MatchCase:=False)"),
    ("countE", "CountOccurrences(\"e\")"),
    ("#", "Set r = doc.Content"), ("replaceParagraph", "r.Find.Execute(FindText:=\"sentence.\", ReplaceWith:=\"sentence.^pChen\", Replace:=wdReplaceAll)"),
    ("paragraphsAfter", "doc.Paragraphs.Count"),
    ("#", "Set r = doc.Content: r.Find.ClearFormatting: r.Find.Text = \"Chen\": r.Find.Forward = True: r.Find.Wrap = wdFindStop"),
    ("propertyStyle", "r.Find.Execute"), ("found", "r.Find.Found"),
    ("#", "Set r = doc.Content: r.Find.Replacement.ClearFormatting: r.Find.Replacement.Font.Bold = True"),
    ("formatReplace", "r.Find.Execute(FindText:=\"Chen\", ReplaceWith:=\"\", Format:=True, Replace:=wdReplaceAll)"),
    ("#", "Set r = doc.Content: r.Find.Execute FindText:=\"Chen\""), ("formattedBold", "r.Font.Bold"),
    ("#", "Set r = doc.Content"), ("notFound", "r.Find.Execute(FindText:=\"khongtimthay\")"), ("rangeUnchangedOnMiss", "r.End = doc.Content.End"),
    ("selectionFind", "SelectionFind()"),
], declare=DOC)

PROPS = checks("WdProps", [
    START, ("!title", "doc.BuiltInDocumentProperties(\"Title\") = \"Cong van\""), ("titleRead", "doc.BuiltInDocumentProperties(\"Title\").Value"),
    ("!author", f"doc.BuiltInDocumentProperties(\"Author\").Value = {vn('Trần Bình')}"),
    ("authorRead", f"doc.BuiltInDocumentProperties(\"Author\").Value = {vn('Trần Bình')}"),
    ("!custom", "doc.CustomDocumentProperties.Add Name:=\"SoHieu\", LinkToContent:=False, Type:=4, Value:=\"45/CV\""),
    ("customRead", "doc.CustomDocumentProperties(\"SoHieu\").Value"), ("customCount", "doc.CustomDocumentProperties.Count"),
    ("!variable", f"doc.Variables.Add \"bien1\", {vn('giá trị')}"), ("variableRead", f"doc.Variables(\"bien1\").Value = {vn('giá trị')}"),
    ("variableCount", "doc.Variables.Count"), ("variableMissing", "doc.Variables(\"khongco\").Value"),
    ("!variableSet", "doc.Variables(\"bien2\").Value = \"x\""), ("variableSetRead", "doc.Variables(\"bien2\").Value"),
    ("saved", "TypeName(doc.Saved)"),
], declare=DOC)

EVENTS = checks("WdEvents", [
    START, ("documentOpen", "doc.Variables(\"evt_open\").Value"), ("autoOpen", "doc.Variables(\"evt_auto\").Value"),
    ("order", "EventOrder"),
], declare=DOC)

EVENT_MODULES = [("ThisDocument", document_module("ThisDocument", "Private Sub Document_Open()\n"
                  "    ActiveDocument.Variables(\"evt_open\").Value = \"doc-open\"\n    EventOrder = EventOrder & \"D\"\nEnd Sub\n"))]
AUTO_OPEN = ("Public EventOrder As String\n\nPublic Sub AutoOpen()\n    ActiveDocument.Variables(\"evt_auto\").Value = \"auto-open\"\n"
             "    EventOrder = EventOrder & \"A\"\nEnd Sub\n")

HELPERS = '''Public Function CountOccurrences(ByVal what As String) As Long
    Dim r As Object, n As Long
    Set r = ActiveDocument.Content
    With r.Find
        .Text = what
        .MatchCase = True
        .Forward = True
        .Wrap = 0
        Do While .Execute
            n = n + 1
            If n > 500 Then Exit Do
            r.Collapse 0
        Loop
    End With
    CountOccurrences = n
End Function

Public Function SelectionFind() As String
    Selection.HomeKey Unit:=6
    With Selection.Find
        .ClearFormatting
        .Text = "paragraph"
        .Forward = True
        .Wrap = 1
    End With
    If Selection.Find.Execute Then SelectionFind = Selection.Text & "@" & Selection.Start Else SelectionFind = "miss"
End Function
'''
