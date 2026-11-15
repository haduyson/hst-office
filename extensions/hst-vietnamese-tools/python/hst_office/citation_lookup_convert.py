# SPDX-License-Identifier: AGPL-3.0-only
"""Turn lookup answers into CSL-JSON items: doi.org (CSL-JSON), Crossref REST, NCBI E-utilities esummary,
arXiv Atom and Open Library. Abstracts are not kept (they may be under copyright); markup in titles is removed.
Pure Python (no uno, no network)."""
import html
import json
import re
import xml.etree.ElementTree as ElementTree

from . import citation_dates as dates
from . import citation_model as model
from . import citation_names as names

CROSSREF_TYPES = {"journal-article": "article-journal", "book-chapter": "chapter", "book-section": "chapter",
                  "book-part": "chapter", "proceedings-article": "paper-conference", "posted-content": "article",
                  "dissertation": "thesis", "report": "report", "book": "book", "monograph": "book",
                  "edited-book": "book", "reference-book": "book", "dataset": "dataset", "standard": "standard",
                  "reference-entry": "entry-encyclopedia", "peer-review": "review"}
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def _clean(text):
    text = re.sub(r"<[^>]+>", "", html.unescape(str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


def _first(value):
    return _clean(value[0]) if isinstance(value, list) and value else _clean(value) if isinstance(value, str) else ""


def _people(values):
    result = []
    for person in values or []:
        if not isinstance(person, dict):
            continue
        if person.get("family"):
            result.append({"family": _clean(person["family"]), "given": _clean(person.get("given", ""))})
        elif person.get("name") or person.get("literal"):
            result.append({"literal": _clean(person.get("name") or person.get("literal"))})
    return result


def _finish(raw):
    raw.pop("abstract", None)
    return model.normalize_item(raw)[0]


def from_csl_json(body):
    """doi.org content negotiation answer (application/vnd.citationstyles.csl+json)."""
    data = json.loads(body)
    data = data[0] if isinstance(data, list) and data else data
    if not isinstance(data, dict):
        return []
    raw = {k: v for k, v in data.items() if k in model.TEXT_VARS or k in model.DATE_VARS or k in ("type",)}
    raw.update({k: _people(data.get(k)) for k in ("author", "editor", "translator") if data.get(k)})
    for key in ("title", "container-title", "container-title-short", "publisher"):
        if key in data:
            raw[key] = _first(data[key])
    raw.pop("id", None)
    if raw.get("type") not in model.CSL_TYPES:  # doi.org sometimes answers with the Crossref type name
        raw["type"] = CROSSREF_TYPES.get(raw.get("type"), "document")
    return [_finish(raw)]


def crossref_work(work):
    raw = {"type": CROSSREF_TYPES.get(work.get("type"), "document"), "title": _first(work.get("title")),
           "container-title": _first(work.get("container-title")),
           "container-title-short": _first(work.get("short-container-title")),
           "volume": work.get("volume"), "issue": work.get("issue"), "page": work.get("page"),
           "publisher": work.get("publisher"), "publisher-place": work.get("publisher-location"),
           "DOI": work.get("DOI"), "URL": work.get("URL"), "language": work.get("language")}
    subtitle = _first(work.get("subtitle"))
    if subtitle and raw["title"] and subtitle.lower() not in raw["title"].lower():
        raw["title"] += ": " + subtitle
    for key in ("ISBN", "ISSN"):
        if work.get(key):
            raw[key] = "; ".join(work[key]) if isinstance(work[key], list) else str(work[key])
    for key in ("author", "editor", "translator"):
        if work.get(key):
            raw[key] = _people(work[key])
    for key in ("issued", "published-print", "published-online", "published"):
        if (work.get(key) or {}).get("date-parts") and work[key]["date-parts"][0][0]:
            raw["issued"] = {"date-parts": work[key]["date-parts"]}
            break
    return _finish({k: v for k, v in raw.items() if v})


def from_crossref(body):
    message = json.loads(body).get("message")
    return [crossref_work(message)] if isinstance(message, dict) and "items" not in message else []


def from_crossref_query(body):
    """[(item, score)] of a query.bibliographic answer, best first."""
    items = (json.loads(body).get("message") or {}).get("items") or []
    return [(crossref_work(work), float(work.get("score") or 0)) for work in items if isinstance(work, dict)]


def from_pubmed(body, pmid):
    record = (json.loads(body).get("result") or {}).get(str(pmid))
    if not isinstance(record, dict) or record.get("error"):
        return []
    raw = {"type": "article-journal" if not record.get("booktitle") else "book", "PMID": str(pmid),
           "title": _clean(record.get("title", "")).rstrip("."), "container-title": record.get("fulljournalname"),
           "container-title-short": record.get("source"), "volume": record.get("volume"),
           "issue": record.get("issue"), "page": record.get("pages"), "ISSN": record.get("issn"),
           "issued": dates.parse(record.get("pubdate", "")), "language": (record.get("lang") or [""])[0]}
    for article_id in record.get("articleids") or []:
        if article_id.get("idtype") == "doi":
            raw["DOI"] = article_id.get("value")
        if article_id.get("idtype") == "pmc":
            raw["PMCID"] = article_id.get("value")
    raw["author"] = [_vancouver_name(a["name"]) for a in record.get("authors") or []
                     if a.get("authtype", "Author") == "Author" and a.get("name")]
    return [_finish({k: v for k, v in raw.items() if v})]


def _vancouver_name(text):
    """"Fauci AS" -> {"family": "Fauci", "given": "A. S."}; a collective name stays whole."""
    match = re.match(r"^(.+?)\s+([A-Z]{1,4})$", text.strip())
    if not match:
        return {"literal": text.strip()}
    return {"family": match.group(1), "given": names.initials(match.group(2))}


def from_arxiv(body):
    if b"<!DOCTYPE" in body[:2000].upper() or b"<!ENTITY" in body.upper():
        return []
    entry = ElementTree.fromstring(body).find(_ATOM + "entry")
    if entry is None or (entry.findtext(_ATOM + "title") or "").strip().lower() == "error":
        return []
    identifier = re.sub(r"v\d+$", "", (entry.findtext(_ATOM + "id") or "").rsplit("/abs/", 1)[-1])
    raw = {"type": "article", "title": _clean(entry.findtext(_ATOM + "title")), "publisher": "arXiv",
           "number": "arXiv:" + identifier, "URL": "https://arxiv.org/abs/" + identifier, "genre": "Preprint",
           "issued": dates.parse((entry.findtext(_ATOM + "published") or "")[:10]),
           "DOI": entry.findtext(_ARXIV + "doi"),
           "author": [names.parse_name(_clean(a.findtext(_ATOM + "name")), organization=False)
                      for a in entry.findall(_ATOM + "author")]}
    return [_finish({k: v for k, v in raw.items() if v})]


def from_openlibrary(body, isbn):
    record = json.loads(body).get("ISBN:" + isbn)
    if not isinstance(record, dict):
        return []
    title = _clean(record.get("title", "")) + (": " + _clean(record["subtitle"]) if record.get("subtitle") else "")
    publishers = [p.get("name", "") for p in record.get("publishers") or []]
    places = [p.get("name", "") for p in record.get("publish_places") or []]
    raw = {"type": "book", "title": title, "ISBN": isbn, "issued": dates.parse(record.get("publish_date", "")),
           "publisher": "; ".join(p for p in publishers if p), "publisher-place": "; ".join(p for p in places if p),
           "number-of-pages": str(record.get("number_of_pages") or ""),
           "author": [names.parse_name(a.get("name", ""), organization=False) for a in record.get("authors") or []]}
    return [_finish({k: v for k, v in raw.items() if v})]
