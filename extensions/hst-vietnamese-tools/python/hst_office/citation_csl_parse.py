# SPDX-License-Identifier: AGPL-3.0-only
"""Read a CSL 1.0 style file the user chose (.csl, XML). HST bundles no CSL file; an imported file stays the
user's own and is only read. A DOCTYPE/ENTITY declaration is refused, the file is limited to 1 MB, and elements
outside the supported subset are listed as warnings (they print nothing). Pure Python (no uno)."""
import xml.etree.ElementTree as ElementTree

NS = "{http://purl.org/net/xbiblio/csl}"
MAX_BYTES = 1024 * 1024
SUPPORTED = {"style", "info", "title", "title-short", "id", "link", "author", "contributor", "name", "email", "uri",
             "category", "issn", "eissn", "summary", "updated", "rights", "published", "locale", "terms", "term",
             "single", "multiple", "date", "date-part", "style-options", "macro", "citation", "bibliography",
             "sort", "key", "layout", "text", "number", "label", "names", "et-al", "substitute", "group", "choose",
             "if", "else-if", "else", "name-part", "institution", "institution-part"}


class CslError(ValueError):
    pass


class Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag, attrs, children, text):
        self.tag, self.attrs, self.children, self.text = tag, attrs, children, text

    def get(self, name, default=None):
        return self.attrs.get(name, default)

    def child(self, tag):
        return next((c for c in self.children if c.tag == tag), None)

    def all(self, tag):
        return [c for c in self.children if c.tag == tag]


def _convert(element, warnings):
    tag = element.tag.replace(NS, "")
    if tag not in SUPPORTED and tag not in warnings:
        warnings.append(tag)
    children = [_convert(child, warnings) for child in element]
    return Node(tag, dict(element.attrib), children, (element.text or "").strip())


class CslStyle:
    """Parsed parts of a CSL style."""

    def __init__(self, root, warnings):
        self.root, self.warnings = root, warnings
        self.cls = root.get("class", "in-text")
        self.default_locale = root.get("default-locale", "en-US")
        info = root.child("info")
        title = info.child("title") if info else None
        self.title = title.text if title is not None else "Kiểu CSL"
        self.macros = {m.get("name"): m for m in root.all("macro")}
        self.citation, self.bibliography = root.child("citation"), root.child("bibliography")
        self.terms = {}
        for locale in root.all("locale"):
            terms = locale.child("terms")
            for term in terms.all("term") if terms else []:
                key = (term.get("name"), term.get("form", "long"))
                single, multiple = term.child("single"), term.child("multiple")
                self.terms[key] = (single.text, multiple.text) if single is not None else (term.text, term.text)
                if multiple is not None and single is None:
                    self.terms[key] = (multiple.text, multiple.text)


def parse(data):
    """CslStyle from the bytes of a .csl file; raises CslError with a Vietnamese message."""
    if len(data) > MAX_BYTES:
        raise CslError("tệp kiểu CSL lớn hơn 1 MB")
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in data.upper():
        raise CslError("tệp có khai báo DOCTYPE/ENTITY, không đọc vì lý do an toàn")
    try:
        element = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise CslError("tệp kiểu CSL không phải XML hợp lệ (%s)" % exc) from exc
    if element.tag != NS + "style":
        raise CslError("không phải tệp kiểu CSL (thiếu phần tử <style> của CSL)")
    unsupported = []
    root = _convert(element, unsupported)
    style = CslStyle(root, ["phần tử CSL không hỗ trợ (bỏ qua): <%s>" % tag for tag in unsupported])
    if style.citation is None or style.citation.child("layout") is None:
        raise CslError("tệp kiểu CSL thiếu <citation><layout>")
    for macro in _macro_refs(root):
        if macro not in style.macros:
            raise CslError("tệp kiểu CSL gọi macro không có: %s" % macro)
    if style.cls not in ("in-text", "note"):
        raise CslError("class của kiểu CSL phải là in-text hoặc note")
    return style


def _macro_refs(node):
    if node.get("macro"):
        yield node.get("macro")
    for child in node.children:
        yield from _macro_refs(child)
