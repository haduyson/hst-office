# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư, Word documents: which recipient list a Word mail-merge document names, and where that file is now.
Pure Python (reads the .docx package itself).

Word keeps the list in word/settings.xml w:mailMerge: w:dataSource (a relationship of settings.xml whose Target is
"file:///C:\\folder\\list.xlsx"), the OLE DB w:connectString ("…;Data Source=C:\\folder\\list.xlsx;…"), and the
w:query ("SELECT * FROM `Sheet1$`" for a sheet, "SELECT * FROM C:\\folder\\list.csv" for a text file). Like Word, the
list is looked for at that path, then relative to the document, then by its name next to the document."""
import ntpath
import os
import re
import zipfile
from urllib.parse import unquote
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORD_PACKAGES = (".docx", ".docm", ".dotx", ".dotm")
LISTS = (".xlsx", ".xls", ".xlsm", ".ods", ".csv", ".txt")


class Link:
    """The list a document names: `path` as written (may be a Windows path), `sheet` (None for a text file)."""

    def __init__(self, path, sheet=None):
        self.path, self.sheet = path, sheet

    @property
    def name(self):
        return ntpath.basename(self.path.replace("/", "\\"))

    def __repr__(self):
        return "Link(%r, %r)" % (self.path, self.sheet)


def _value(element, tag):
    found = element.find(W + tag) if element is not None else None
    return found.get(W + "val") if found is not None else None


def target_path(target):
    """A relationship Target as a path: file:///C:\\a\\b.xlsx -> C:\\a\\b.xlsx, file:///home/a.xlsx -> /home/a.xlsx,
    file://server/share/a.xlsx -> \\\\server\\share\\a.xlsx; anything else as written (relative)."""
    text = unquote(target or "").strip()
    lower = text.lower()
    if lower.startswith("file:///"):
        rest = text[8:]
        return rest if re.match(r"[A-Za-z]:[\\/]", rest) else "/" + rest
    if lower.startswith("file://"):
        return "\\\\" + text[7:].replace("/", "\\")
    return text


def _sheet(query, table):
    """Sheet name from w:odso/w:table ("Sheet1$") or the query ("SELECT * FROM `Sheet1$`")."""
    text = table
    if not text and query:
        match = re.search(r"FROM\s+(`[^`]+`|\[[^\]]+\]|'[^']+'|\S+)", query, re.I)
        text = match.group(1) if match else None
    if not text:
        return None
    text = text.strip("`[]'\" ")
    return text[:-1] if text.endswith("$") else text


def parse(settings_xml, rels_xml=None):
    """The Link of a settings.xml (bytes) and its relationships, or None without a mail merge."""
    root = ElementTree.fromstring(settings_xml)
    merge = root.find(W + "mailMerge")
    if merge is None:
        return None
    targets = {}
    if rels_xml:
        for rel in ElementTree.fromstring(rels_xml).iter(PKG + "Relationship"):
            targets[rel.get("Id")] = rel.get("Target")
    path = None
    source = merge.find(W + "dataSource")
    if source is not None and targets.get(source.get(R + "id")):
        path = target_path(targets[source.get(R + "id")])
    query = _value(merge, "query") or ""
    connect = _value(merge, "connectString") or ""
    if not path:
        match = re.search(r"Data Source=([^;]+)", connect, re.I)
        path = match.group(1).strip('"') if match else None
    if not path:
        match = re.search(r"FROM\s+(.+?)\s*$", query, re.I)
        path = match.group(1).strip("`[]'\"") if match and re.search(r"\.\w{3,4}$", match.group(1)) else None
    if not path:
        return None
    odso = merge.find(W + "odso")
    text_file = _value(merge, "dataType") == "textFile" or path.lower().endswith((".csv", ".txt"))
    return Link(path, None if text_file else _sheet(query, _value(odso, "table")))


def read(docx_path):
    """The Link of a Word package on disk, or None (no mail merge, not a package, unreadable)."""
    try:
        with zipfile.ZipFile(docx_path) as package:
            names = set(package.namelist())
            if "word/settings.xml" not in names:
                return None
            rels = package.read("word/_rels/settings.xml.rels") if "word/_rels/settings.xml.rels" in names else None
            return parse(package.read("word/settings.xml"), rels)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError, KeyError):
        return None


def is_remote(path):
    """A network or web location: opening it may ask for credentials, so the user confirms first."""
    text = path.replace("/", "\\")
    return text.startswith("\\\\") or bool(re.match(r"[a-z][a-z0-9+.-]+://", path, re.I))


def candidates(path, document_folder):
    """Where to look, in Word's order: the path, the path relative to the document, the name next to the
    document. Windows paths are understood on every system."""
    drive = bool(re.match(r"[A-Za-z]:[\\/]", path))
    native = path if os.sep == "\\" else (None if drive else path.replace("\\", "/"))
    found = []
    if native and os.path.isabs(native):
        found.append(native)
    elif native and document_folder:
        found.append(os.path.normpath(os.path.join(document_folder, native)))
    if document_folder:
        found.append(os.path.join(document_folder, ntpath.basename(path)))
    return list(dict.fromkeys(found))


def locate(path, document_folder):
    """The first candidate that is a file of a supported kind, else None (remote paths are never probed)."""
    if is_remote(path):
        return None
    for candidate in candidates(path, document_folder):
        if candidate.lower().endswith(LISTS) and os.path.isfile(candidate):
            return candidate
    return None
