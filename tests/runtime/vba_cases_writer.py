# SPDX-License-Identifier: AGPL-3.0-only
"""Word idioms of the VBA compatibility matrix (tests/runtime/check-vba.py), run in HST Writer on WRITER_TEXT.

Same rules as vba_cases.py. As in Word, a paragraph's Range ends after its mark: Range.Text ends with vbCr, Words
counts punctuation and the mark as words of their own, and paragraph-wide members change that paragraph only.
"""
from vba_cases_common import LOGO, _paragraphs, _text  # noqa: F401

WRITER = [
    dict(id="writer-activedocument", title="ActiveDocument.Content.Text", status="ok",
         body='r = Left(ActiveDocument.Content.Text, 9)', want="Xin chào "),
    dict(id="writer-range-insert", title="Range.InsertAfter, InsertBefore", status="ok",
         body='ActiveDocument.Content.InsertAfter " Hết."\nActiveDocument.Content.InsertBefore "Đầu. "\nr = "ok"', want="ok",
         doc=lambda d: _text(d).startswith("Đầu. Xin chào") and _text(d).rstrip().endswith("Hết.")),
    dict(id="writer-document-range", title="ActiveDocument.Range(start, end).Text", status="ok",
         body='r = ActiveDocument.Range(0, 3).Text', want="Xin"),
    dict(id="writer-selection-typetext", title="Selection.TypeText, TypeParagraph", status="ok",
         body='Selection.HomeKey Unit:=wdStory\nSelection.TypeText Text:="Mới "\nSelection.TypeParagraph\nr = "ok"', want="ok",
         doc=lambda d: _text(d).startswith("Mới \nXin chào")),
    dict(id="writer-selection-font", title="Selection.Font.Bold, Range.Font.Size", status="ok",
         body='ActiveDocument.Range(0, 3).Select\nSelection.Font.Bold = True\nActiveDocument.Range(0, 3).Font.Size = 20\n'
              'r = ActiveDocument.Range(0, 3).Font.Bold', want="-1",
         doc=lambda d: d.Text.createEnumeration().nextElement().createEnumeration().nextElement().CharWeight >= 150),
    dict(id="writer-paragraphs", title="Paragraphs.Count, Paragraphs(n).Range.Text", status="ok",
         body='r = ActiveDocument.Paragraphs.Count & "|" & Left(ActiveDocument.Paragraphs(3).Range.Text, 7)', want="3|Đoạn ba"),
    dict(id="writer-paragraph-format", title="Paragraphs(1).Alignment, Range.ParagraphFormat.Alignment", status="ok",
         body='ActiveDocument.Paragraphs(1).Alignment = wdAlignParagraphCenter\n'
              'ActiveDocument.Paragraphs(2).Range.ParagraphFormat.Alignment = wdAlignParagraphRight\n'
              'r = ActiveDocument.Paragraphs(1).Alignment & "|" & ActiveDocument.Paragraphs(2).Format.Alignment',
         want="1|2", doc=lambda d: d.Text.createEnumeration().nextElement().ParaAdjust == 3),
    dict(id="writer-find-replace", title="Find.Execute Replace:=wdReplaceAll", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Content\nrg.Find.Execute FindText:="HST", ReplaceWith:="HASON", Replace:=wdReplaceAll\n'
              'r = "ok"', want="ok", doc=lambda d: "HST" not in _text(d) and _text(d).count("HASON") == 2),
    dict(id="writer-find", title="Find.Execute không thay thế (tìm, chọn chữ tìm thấy)", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Content\nr = rg.Find.Execute(FindText:="thế giới") & "|" & rg.Text', want="True|thế giới"),
    dict(id="writer-tables-add", title="Tables.Add, Rows.Count, Columns.Count", status="ok",
         body='Dim tb As Object\nSet tb = ActiveDocument.Tables.Add(ActiveDocument.Paragraphs(3).Range, 2, 3)\n'
              'r = ActiveDocument.Tables.Count & "|" & tb.Rows.Count & "|" & tb.Columns.Count',
         want="1|2|3", doc=lambda d: d.TextTables.Count == 1),
    dict(id="writer-table-cell", title="Table.Cell(h, c).Range.Text", status="ok",
         body='Dim tb As Object\nSet tb = ActiveDocument.Tables.Add(ActiveDocument.Paragraphs(3).Range, 2, 3)\n'
              'tb.Cell(1, 1).Range.Text = "Ô 1"\ntb.Cell(2, 3).Range.Text = "Ô 6"\nr = tb.Cell(2, 3).Range.Text', want="Ô 6",
         doc=lambda d: d.TextTables.getByIndex(0).getCellByName("A1").String == "Ô 1"),
    dict(id="writer-words-sentences", title="Words.Count, Sentences(1)", status="ok",
         body='r = (ActiveDocument.Words.Count > 10) & "|" & Left(ActiveDocument.Sentences(1).Text, 8)', want="True|Xin chào"),
    dict(id="writer-bookmarks", title="Bookmarks.Add, Bookmarks(\"tên\").Range", status="ok",
         body='ActiveDocument.Bookmarks.Add "DauVanBan", ActiveDocument.Range(0, 3)\n'
              'r = ActiveDocument.Bookmarks.Count & "|" & ActiveDocument.Bookmarks("DauVanBan").Range.Text', want="1|Xin"),
    dict(id="writer-styles", title="Paragraphs(1).Style = \"Heading 1\"", status="ok",
         body='ActiveDocument.Paragraphs(1).Style = ActiveDocument.Styles(wdStyleHeading1)\nr = "ok"', want="ok",
         doc=lambda d: d.Text.createEnumeration().nextElement().ParaStyleName in ("Heading 1", "Heading1")),
    dict(id="writer-header-footer", title="Sections(1).Headers(wdHeaderFooterPrimary)", status="ok",
         body='ActiveDocument.Sections(1).Headers(wdHeaderFooterPrimary).Range.Text = "Đầu trang"\nr = "ok"', want="ok"),
    dict(id="writer-insert-break", title="Selection.InsertBreak wdPageBreak", status="ok",
         body='Selection.EndKey Unit:=wdStory\nSelection.InsertBreak Type:=wdPageBreak\nr = "ok"', want="ok"),
    dict(id="writer-msgbox", title="MsgBox", status="ok",
         body='Dim a As Integer\na = MsgBox("Xin chào", vbOKOnly)\nr = "ok"', want="ok"),
    dict(id="writer-loop-paragraphs", title="For Each p In ActiveDocument.Paragraphs", status="ok",
         body='Dim p As Object, n As Integer\nFor Each p In ActiveDocument.Paragraphs\n  n = n + 1\nNext p\nr = n', want="3"),
    dict(id="writer-inlineshapes", title="InlineShapes.Count, Shapes.Count", status="ok",
         body='r = ActiveDocument.InlineShapes.Count & "|" & ActiveDocument.Shapes.Count', want="0|0"),
    dict(id="writer-inlineshapes-add", title="InlineShapes.AddPicture, Width/Height, LockAspectRatio", status="ok",
         body='Dim ish As Object, h As Single\nSet ish = ActiveDocument.InlineShapes.AddPicture(FileName:="' + LOGO + '", '
              'LinkToFile:=False, SaveWithDocument:=True, Range:=ActiveDocument.Paragraphs(3).Range)\n'
              'h = ish.Height / ish.Width\nish.LockAspectRatio = msoTrue\nish.Width = 72\n'
              'r = ActiveDocument.InlineShapes.Count & "|" & Round(ish.Width) & "|" & (Abs(ish.Height / ish.Width - h) < 0.02) & "|" & ish.Type',
         want="1|72|True|3", doc=lambda d: d.GraphicObjects.Count == 1),
    dict(id="writer-fields", title="Fields.Add (DATE, PAGE, NUMPAGES), Fields.Update", status="ok",
         body='ActiveDocument.Fields.Add Range:=ActiveDocument.Range(0, 0), Type:=wdFieldDate\n'
              'ActiveDocument.Fields.Add ActiveDocument.Paragraphs(3).Range, wdFieldPage\n'
              'ActiveDocument.Fields.Add ActiveDocument.Range(0, 0), wdFieldEmpty, "NUMPAGES"\n'
              'r = ActiveDocument.Fields.Count & "|" & ActiveDocument.Fields.Update', want="3|0"),
    dict(id="writer-comments", title="Comments.Add, Comments(1).Range.Text, .Scope, .Author", status="ok",
         body='Dim cm As Object\nSet cm = ActiveDocument.Comments.Add(ActiveDocument.Range(0, 3), "Ghi chú")\n'
              'cm.Author = "HST"\nr = ActiveDocument.Comments.Count & "|" & ActiveDocument.Comments(1).Range.Text & "|" & cm.Scope.Text & "|" & cm.Author',
         want="1|Ghi chú|Xin|HST"),
    dict(id="writer-lists", title="Range.ListFormat.ApplyBulletDefault", status="ok",
         body='ActiveDocument.Paragraphs(2).Range.ListFormat.ApplyBulletDefault\nr = "ok"', want="ok",
         doc=lambda d: [p.NumberingStyleName for p in _paragraphs(d)][:3] == ["", "List 1", ""]),
    dict(id="writer-document-properties", title="BuiltInDocumentProperties(\"Title\")", status="ok",
         body='ActiveDocument.BuiltInDocumentProperties("Title") = "Báo cáo"\nr = ActiveDocument.BuiltInDocumentProperties("Title")',
         want="Báo cáo"),
    dict(id="writer-dictionary-wordcount", title="Đếm từ trong văn bản bằng Scripting.Dictionary", status="ok",
         body='Dim d As Object, w As Variant\nSet d = CreateObject("Scripting.Dictionary")\nd.CompareMode = vbTextCompare\n'
              # as in Word, a paragraph's Range.Text ends with its mark (vbCr): a word-count macro strips it
              'For Each w In Split(Replace(Replace(ActiveDocument.Paragraphs(2).Range.Text, vbCr, ""), ".", ""), " ")\n  If Len(Trim(w)) > 0 Then d(Trim(w)) = d(Trim(w)) + 1\nNext w\n'
              'r = d("hst") & "|" & d.Exists("ĐOẠN") & "|" & d.Count', want="2|True|6"),
    dict(id="writer-dictionary-nested", title="Dictionary lồng nhau, khóa tiếng Việt (TextCompare)", status="ok",
         body='Dim d As Object\nSet d = CreateObject("Scripting.Dictionary")\nd.CompareMode = vbTextCompare\n'
              'Set d("Hà Nội") = CreateObject("Scripting.Dictionary")\nd("hà nội")("số đoạn") = ActiveDocument.Paragraphs.Count\n'
              'r = d("HÀ NỘI")("số đoạn") & "|" & d.Count', want="3|1"),
    dict(id="writer-range-words", title="Range.Words.Count, Range.Sentences(1), Range.Bold/Italic", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Paragraphs(1).Range\nrg.Words(1).Bold = True\nrg.Sentences(2).Italic = True\n'
              'r = rg.Words.Count & "|" & Left(rg.Sentences(2).Text, 6) & "|" & rg.Words(1).Bold & "|" & rg.Words(2).Bold & "|" & rg.Sentences(2).Italic',
         # Word: punctuation and the paragraph mark are words of their own (9 words, 2 full stops, the mark)
         want="12|Đây là|-1|0|-1"),
    dict(id="writer-paragraph-scope", title="Paragraphs(2).Range.Style, .ListFormat, .Paragraphs only touch paragraph 2", status="ok",
         body='Dim rg As Object\nSet rg = ActiveDocument.Paragraphs(2).Range\nrg.Style = ActiveDocument.Styles(wdStyleHeading1)\n'
              'rg.ParagraphFormat.Alignment = wdAlignParagraphCenter\nr = rg.Paragraphs.Count & "|" & ActiveDocument.Paragraphs(3).Alignment',
         want="1|0", doc=lambda d: [p.ParaStyleName for p in _paragraphs(d)][:3] == ["Standard", "Heading 1", "Standard"]),
    dict(id="writer-selection-words", title="Selection.Words, Selection.Sentences, Selection.ClearFormatting", status="ok",
         body='ActiveDocument.Paragraphs(1).Range.Select\nSelection.Words(1).Italic = True\n'
              'r = Selection.Words(1).Italic & "|" & Selection.Sentences.Count\nSelection.ClearFormatting\nr = r & "|" & Selection.Words(1).Italic',
         want="-1|2|0"),
]
