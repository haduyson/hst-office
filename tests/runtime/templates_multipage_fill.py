# SPDX-License-Identifier: AGPL-3.0-only
"""UNO side of the multi-page template check: create a document from a template (or through the wizard renderer), grow
its body to N pages with realistic Vietnamese text, export PDF/ODT/DOCX/DOC and reopen the copies.

Everything here runs against a live office through the build's own pyuno; nothing is mocked.
"""
import os
import re

PARAS = [
    "Thực hiện chương trình công tác năm 2026, cơ quan đã tổ chức rà soát toàn bộ hồ sơ, tài liệu liên quan đến "
    "việc triển khai nhiệm vụ chuyển đổi số; kết quả cho thấy phần lớn các đơn vị đã hoàn thành đúng tiến độ, "
    "bảo đảm chất lượng và tuân thủ quy trình nghiệp vụ được giao.",
    "Tuy nhiên, một số đơn vị còn chậm cập nhật dữ liệu lên hệ thống quản lý văn bản và điều hành, việc lập hồ sơ "
    "điện tử chưa đầy đủ, chưa thống nhất về cách đặt tên tệp tin, số và ký hiệu văn bản; công tác lưu trữ còn "
    "phân tán, gây khó khăn cho việc tra cứu và khai thác thông tin.",
    "Để khắc phục những tồn tại nêu trên, đề nghị thủ trưởng các cơ quan, đơn vị chỉ đạo bộ phận văn thư rà soát, "
    "chuẩn hóa danh mục hồ sơ, phân công cán bộ đầu mối theo dõi, đôn đốc và báo cáo kết quả thực hiện trước ngày "
    "15 tháng 12 năm 2026.",
    "1. Rà soát, cập nhật danh mục hồ sơ năm 2026 của cơ quan, đơn vị.",
    "2. Kiểm tra việc đăng ký, quản lý văn bản đến, văn bản đi trên hệ thống.",
    "3. Tổ chức tập huấn nghiệp vụ văn thư, lưu trữ cho cán bộ, công chức.",
    "a) Thời gian: hoàn thành trong quý IV năm 2026;",
    "b) Kinh phí: từ nguồn ngân sách chi thường xuyên được giao.",
]
ONE_LINE = "Nội dung bổ sung kiểm tra ngắt trang."
FILTERS = {"pdf": "writer_pdf_Export", "odt": "writer8", "docx": "MS Word 2007 XML", "doc": "MS Word 97"}


def props(**kw):
    from com.sun.star.beans import PropertyValue
    out = []
    for key, value in kw.items():
        item = PropertyValue()
        item.Name, item.Value = key, value
        out.append(item)
    return tuple(out)


def url(path):
    import uno
    return uno.systemPathToFileUrl(os.path.abspath(path))


def role(name):
    return re.sub(r"\d+$", "", name or "")


class Document:
    """A document under test; `roles` maps paragraph text to its layout role for wizard output (direct formatting)."""

    def __init__(self, doc, roles=None):
        self.doc, self.roles = doc, roles or {}

    def elements(self):
        out, e = [], self.doc.getText().createEnumeration()
        while e.hasMoreElements():
            out.append(e.nextElement())
        return out

    def role_of(self, x):
        return self.roles.get(x.getString(), "") if self.roles else role(x.ParaStyleName)

    def pages(self):
        return self.doc.getCurrentController().PageCount

    def page_of(self, rng):
        vc = self.doc.getCurrentController().getViewCursor()
        vc.gotoRange(rng, False)
        return vc.getPage()

    def anchor(self, edit_role):
        """The last paragraph of the type's content role before the signature table (where a user types)."""
        best = None
        for x in self.elements():
            if is_table(x):
                if x.Name.startswith("Signature") and best is not None:
                    break
                continue
            if self.role_of(x) in (edit_role, "Body", "Article"):
                best = x
        return best

    def last_content_page(self):
        last = 1
        for x in self.elements():
            if is_table(x):
                last = max(last, self.page_of(x.getCellByName(x.getCellNames()[-1]).getText().getEnd()))
            elif x.getString().strip():
                last = max(last, self.page_of(x.getEnd()))
        return last

    def signature_pages(self):
        """[first, last] page of the signature table, or None."""
        for x in self.elements():
            if is_table(x) and x.Name.startswith("Signature"):
                names = x.getCellNames()
                return [self.page_of(x.getCellByName(names[0]).getText().getStart()), self.page_of(x.getCellByName(names[-1]).getText().getEnd())]
        return None

    def export(self, path, fmt):
        self.doc.storeToURL(url(path), props(FilterName=FILTERS[fmt], Overwrite=True))

    def close(self):
        self.doc.close(True)


def is_table(x):
    return x.supportsService("com.sun.star.text.TextTable")


def create(desktop, path_kind, ident, template_path):
    if path_kind == "template":
        return Document(desktop.loadComponentFromURL(url(template_path), "_blank", 0, props(Hidden=True, AsTemplate=True)))
    from hst_office.nd30_layout import build_layout
    from hst_office.nd30_writer import insert_layout
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, props(Hidden=True))
    layout = build_layout(ident)
    result = insert_layout(doc, doc.getCurrentController().getViewCursor(), layout, apply_page=True, page_numbers=True)
    if result.get("blockers"):
        raise RuntimeError("wizard refused: %s" % result["blockers"])
    names = [b.get("name", "Grid") for b in layout["blocks"] if b["type"] == "grid"]
    tables = [x for x in Document(doc).elements() if is_table(x)]
    for index, (table, name) in enumerate(zip(tables, names)):
        table.setName("%s%d" % (name, index))
    roles = {}
    for b in layout["blocks"]:
        if b["type"] == "paragraph" and b.get("role"):
            roles.setdefault("".join(r["text"] for r in b["runs"]), b["role"])
    return Document(doc, roles)


class Filler:
    """Appends paragraphs after the anchor (they keep its paragraph style), or data rows to a ruled form table."""

    def __init__(self, document, anchor=None, table=None):
        self.document, self.table, self.count = document, table, 0
        if anchor is not None:
            self.text = document.doc.getText()
            self.cursor = self.text.createTextCursorByRange(anchor.getEnd())

    def add(self, text=None):
        if self.table is not None:
            rows = self.table.getRows()
            n = rows.getCount()
            rows.insertByIndex(n, 1)
            for c in range(self.table.getColumns().getCount()):
                try:
                    self.table.getCellByPosition(c, n).setString(str(self.count + 1) if c == 0 else "Hồ sơ số %d về công tác văn thư năm 2026" % (self.count + 1))
                except Exception:
                    pass
        else:
            self.text.insertControlCharacter(self.cursor, 0, False)  # PARAGRAPH_BREAK
            self.text.insertString(self.cursor, text or PARAS[self.count % len(PARAS)], False)
        self.count += 1

    def remove_last(self):
        if self.table is not None:
            rows = self.table.getRows()
            rows.removeByIndex(rows.getCount() - 1, 1)
        else:
            self.cursor.gotoStartOfParagraph(True)
            self.cursor.setString("")
            self.cursor.goLeft(1, True)
            self.cursor.setString("")
        self.count -= 1


def filler_for(document, edit_role, ruled_form):
    if ruled_form:
        for x in document.elements():
            if is_table(x) and x.Name.startswith("Form") and x.getRows().getCount() >= 2:
                return Filler(document, table=x)
    anchor = document.anchor(edit_role)
    return Filler(document, anchor=anchor) if anchor is not None else None


def grow(document, filler, pages, limit=400):
    """Fill to `pages`: for 1 the page is filled to the brim; otherwise text is added until text reaches page `pages`
    (the empty closing paragraph alone does not count: the sweep checks that one)."""
    if filler is None:
        return document.pages()
    for _ in range(limit):
        if pages > 1 and document.last_content_page() >= pages:
            if filler.table is None:  # two more lines: off the knife edge where only the 1 pt end paragraph moves
                filler.add(ONE_LINE)
                filler.add(ONE_LINE)
            break
        filler.add()
        if pages == 1 and document.pages() > 1:
            filler.remove_last()
            break
    return document.pages()


def sweep(document, filler, steps=45):
    """Grow a full first page line by line across the page break; report a split signature or a blank last page."""
    grow(document, filler, 1)
    problems = []
    for step in range(steps):
        filler.add(ONE_LINE)
        sig = document.signature_pages()
        if sig and sig[0] != sig[1]:
            problems.append("step %d: signature block split over pages %s" % (step + 1, sig))
        last = document.last_content_page()
        if last < document.pages():
            problems.append("step %d: blank last page (content ends on p%d of %d)" % (step + 1, last, document.pages()))
        if sig and sig[0] >= 2 and step > 5:
            break
    return problems
