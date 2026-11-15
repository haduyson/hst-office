# SPDX-License-Identifier: AGPL-3.0-only
"""Reference items: CSL-JSON (the format Zotero, Mendeley, doi.org and Crossref share) plus HST extras.

HST extras: ``"hst-vi": true`` on a Vietnamese name (see citation_names) and ``custom.hst`` on the item
(``{"modified": "<ISO time>", "languageGroup": "vi"}``). ``normalize_item`` is the single validation boundary: every
importer, the library and the document layer pass items through it. Pure Python (no uno).
"""
import copy
import datetime
import unicodedata
import uuid

from . import citation_dates as dates
from . import citation_names as names

# Types offered in HST dialogs, with their Vietnamese labels (any other CSL type is kept and printed generically).
TYPE_LABELS = (
    ("book", "Sách"), ("chapter", "Chương sách"), ("article-journal", "Bài tạp chí khoa học"),
    ("paper-conference", "Bài hội thảo, kỷ yếu"), ("thesis", "Luận văn, luận án"), ("report", "Báo cáo"),
    ("legislation", "Văn bản pháp luật"), ("webpage", "Trang web"), ("article-newspaper", "Bài báo"),
    ("article-magazine", "Bài tạp chí phổ thông"), ("dataset", "Bộ dữ liệu"), ("manuscript", "Bản thảo"),
    ("patent", "Bằng sáng chế"), ("software", "Phần mềm"), ("document", "Tài liệu khác"),
)
CSL_TYPES = frozenset((
    "article", "article-journal", "article-magazine", "article-newspaper", "bill", "book", "broadcast", "chapter",
    "classic", "collection", "dataset", "document", "entry", "entry-dictionary", "entry-encyclopedia", "event",
    "figure", "graphic", "hearing", "interview", "legal_case", "legislation", "manuscript", "map",
    "motion_picture", "musical_score", "pamphlet", "paper-conference", "patent", "performance", "periodical",
    "personal_communication", "post", "post-weblog", "regulation", "report", "review", "review-book", "software",
    "song", "speech", "standard", "thesis", "treaty", "webpage"))
NAME_VARS = ("author", "editor", "translator", "container-author", "collection-editor", "editorial-director",
             "director", "interviewer", "recipient", "reviewed-author", "composer", "illustrator", "original-author",
             "chair", "compiler", "contributor", "curator", "organizer", "performer", "producer", "guest", "host",
             "narrator", "editor-translator", "executive-producer", "script-writer", "series-creator")
DATE_VARS = ("issued", "accessed", "event-date", "original-date", "submitted", "available-date")
TEXT_VARS = frozenset((
    "abstract", "annote", "archive", "archive_collection", "archive_location", "archive-place", "authority",
    "call-number", "chapter-number", "citation-key", "citation-label", "collection-number", "collection-title",
    "container-title", "container-title-short", "dimensions", "division", "DOI", "edition", "event", "event-title",
    "event-place", "genre", "ISBN", "ISSN", "issue", "jurisdiction", "keyword", "language", "license", "medium",
    "note", "number", "number-of-pages", "number-of-volumes", "original-publisher", "original-publisher-place",
    "original-title", "page", "page-first", "part-number", "part-title", "PMCID", "PMID", "printing-number",
    "publisher", "publisher-place", "references", "reviewed-genre", "reviewed-title", "scale", "section", "source",
    "status", "supplement-number", "title", "title-short", "URL", "version", "volume", "volume-title"))
NAME_KEYS = ("family", "given", "literal", "suffix", "dropping-particle", "non-dropping-particle")
MAX_TEXT = 100_000  # one field; abstracts longer than this are cut
EMBED_DROP = ("abstract", "annote", "keyword", "references")
EMBED_NOTE_MAX = 500


def new_id():
    return "hst-" + uuid.uuid4().hex


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _text(value):
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (int, float)):
        value = str(int(value)) if float(value).is_integer() else str(value)
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFC", value).strip()[:MAX_TEXT]


def normalize_name(value):
    """A clean CSL name object (strings are parsed with citation_names.parse_name); None when empty."""
    if isinstance(value, str):
        value = names.parse_name(value)
    if not isinstance(value, dict):
        return None
    name = {key: _text(value[key]) for key in NAME_KEYS if _text(value.get(key))}
    if name.get("literal"):
        name = {"literal": name["literal"]}
    elif not name.get("family") and name.get("given"):
        name = {"literal": name["given"]}  # a lone given name (e.g. a pen name) is printed as written
    if not name:
        return None
    if "hst-vi" in value and not name.get("literal"):
        name["hst-vi"] = bool(value["hst-vi"])
    return name


def normalize_item(raw):
    """(item, warnings): the validated CSL-JSON item. Raises ValueError when ``raw`` is not an object."""
    if not isinstance(raw, dict):
        raise ValueError("một mục tài liệu phải là đối tượng JSON")
    warnings = []
    item = {"id": _text(raw.get("id")) or new_id()}
    kind = _text(raw.get("type")) or "document"
    if kind not in CSL_TYPES:
        warnings.append("kiểu tài liệu “%s” không hỗ trợ, đổi thành “Tài liệu khác”" % kind)
        kind = "document"
    item["type"] = kind
    for key in sorted(TEXT_VARS):
        text = _text(raw.get(key))
        if text:
            item[key] = text
    for key in NAME_VARS:
        values = raw.get(key)
        if isinstance(values, (str, dict)):
            values = [values]
        if isinstance(values, list):
            clean = [n for n in (normalize_name(v) for v in values) if n]
            if clean:
                item[key] = clean
    for key in DATE_VARS:
        date = dates.normalize(raw.get(key))
        if date:
            item[key] = date
    custom = raw.get("custom")
    if isinstance(custom, dict):
        item["custom"] = copy.deepcopy(custom)
    if not item.get("title") and not item.get("author"):
        warnings.append("mục %s không có nhan đề và tác giả" % item["id"])
    return item, warnings


def hst_meta(item):
    """The item's ``custom.hst`` object (created when missing)."""
    custom = item.setdefault("custom", {})
    if not isinstance(custom.get("hst"), dict):
        custom["hst"] = {}
    return custom["hst"]


def touch(item):
    """Record the edit time: the document layer keeps the newest copy of an item that two citations disagree on."""
    hst_meta(item)["modified"] = now_iso()
    return item


def modified(item):
    return ((item.get("custom") or {}).get("hst") or {}).get("modified", "")


def for_embedding(item):
    """Copy carried inside a document citation: no abstract, keywords or long notes (keeps field codes small)."""
    result = {k: copy.deepcopy(v) for k, v in item.items() if k not in EMBED_DROP}
    if len(result.get("note", "")) > EMBED_NOTE_MAX:
        del result["note"]
    return result


def year(item):
    return dates.year(item.get("issued"))
