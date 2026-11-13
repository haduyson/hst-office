# SPDX-License-Identifier: AGPL-3.0-only
"""Field codes of HST citations and of the bibliography in a document. Pure Python (no uno).

A citation is a text fieldmark (type UNHANDLED) whose code is
    ADDIN HST_CITATION {"v":1,"citationID":"…","mode":"normal","items":[{"id","locator","label","prefix","suffix",
                        "suppressAuthor","authorOnly","itemData":{CSL-JSON}}]}
and whose result is the formatted citation; the bibliography is one fieldmark "ADDIN HST_BIBLIOGRAPHY {"v":1}".
The JSON deliberately follows the shape of Zotero's CSL_CITATION, so citations written by Zotero or Mendeley
("ADDIN ZOTERO_ITEM CSL_CITATION {…}", "ADDIN CSL_CITATION {…}") are read too (they are not rewritten).
Every item carries its own copy of the reference (itemData), so a document sent to someone else stays editable.
"""
import json
import uuid

CITATION = "ADDIN HST_CITATION "
BIBLIOGRAPHY = "ADDIN HST_BIBLIOGRAPHY"
PREFIX = "ADDIN HST_"
FOREIGN = ("ADDIN ZOTERO_ITEM CSL_CITATION ", "ADDIN CSL_CITATION ")
VERSION = 1
MAX_CODE_BYTES = 32 * 1024  # other word processors keep longer codes, but a citation never needs more
CITE_KEYS = ("locator", "label", "prefix", "suffix")
CITE_FLAGS = ("suppressAuthor", "authorOnly")


class CodeError(ValueError):
    """A field code that is not a usable citation."""


def kind_of(code):
    """"citation", "bibliography", "foreign" (Zotero/Mendeley citation) or None."""
    if not isinstance(code, str):
        return None
    if code.startswith(CITATION):
        return "citation"
    if code.startswith(BIBLIOGRAPHY):
        return "bibliography"
    if code.startswith(FOREIGN):
        return "foreign"
    return None


def new_citation_id():
    return "c" + uuid.uuid4().hex[:16]


def _cite(raw):
    cite = {"id": raw["id"]}
    for key in CITE_KEYS:
        if isinstance(raw.get(key), str) and raw[key]:
            cite[key] = raw[key]
    for key in CITE_FLAGS:
        if raw.get(key) is True:
            cite[key] = True
    return cite


def encode_citation(cluster, items):
    """The code of one citation: ``cluster`` = {"citationID", "items": [cites], "mode"}, ``items`` = {id: itemData}
    (already reduced for embedding). Raises CodeError when the code would be larger than MAX_CODE_BYTES."""
    if not cluster.get("items"):
        raise CodeError("một trích dẫn phải có ít nhất một nguồn")
    body = {"v": VERSION, "citationID": cluster.get("citationID") or new_citation_id(),
            "mode": cluster.get("mode") if cluster.get("mode") in ("normal", "narrative") else "normal",
            "items": []}
    for raw in cluster["items"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise CodeError("nguồn trích dẫn thiếu id")
        cite = _cite(raw)
        data = items.get(raw["id"])
        if isinstance(data, dict):
            cite["itemData"] = dict(data, id=raw["id"])
        body["items"].append(cite)
    code = CITATION + json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise CodeError("dữ liệu của trích dẫn quá lớn (hơn 32 KB)")
    return code


def encode_bibliography():
    return BIBLIOGRAPHY + " " + json.dumps({"v": VERSION}, separators=(",", ":"))


def _json_after(code, prefix):
    try:
        body = json.loads(code[len(prefix):])
    except ValueError as exc:
        raise CodeError("mã trích dẫn không phải JSON hợp lệ") from exc
    if not isinstance(body, dict):
        raise CodeError("mã trích dẫn không phải đối tượng JSON")
    return body


def decode_citation(code):
    """(cluster, items) of a citation code: cluster = {"citationID", "items": [cites without itemData], "mode"},
    items = {id: itemData}. Zotero/Mendeley codes are converted the same way. Raises CodeError."""
    kind = kind_of(code)
    if kind == "citation":
        body = _json_after(code, CITATION)
        if not isinstance(body.get("v"), int) or body["v"] > VERSION:
            raise CodeError("trích dẫn do phiên bản HST Office mới hơn tạo")
        raw_items = body.get("items")
    elif kind == "foreign":
        prefix = next(p for p in FOREIGN if code.startswith(p))
        body = _json_after(code, prefix)
        raw_items = [_from_csl_citation(c) for c in body.get("citationItems") or [] if isinstance(c, dict)]
    else:
        raise CodeError("không phải mã trích dẫn")
    if not isinstance(raw_items, list) or not raw_items:
        raise CodeError("trích dẫn không có nguồn nào")
    cites, items = [], {}
    for raw in raw_items:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise CodeError("nguồn trích dẫn thiếu id")
        cites.append(_cite(raw))
        if isinstance(raw.get("itemData"), dict):
            items[raw["id"]] = dict(raw["itemData"], id=raw["id"])
    mode = body.get("mode") if body.get("mode") in ("normal", "narrative") else "normal"
    cluster = {"citationID": str(body.get("citationID") or ""), "items": cites, "mode": mode}
    return cluster, items


def _from_csl_citation(raw):
    """A citationItem of Zotero/Mendeley in HST's cite shape (ids become strings)."""
    data = raw.get("itemData") if isinstance(raw.get("itemData"), dict) else None
    item_id = raw.get("id", data.get("id") if data else None)
    cite = {"id": str(item_id) if item_id not in (None, "") else ""}
    for key in CITE_KEYS:
        if raw.get(key) not in (None, ""):
            cite[key] = str(raw[key])
    if raw.get("suppress-author"):
        cite["suppressAuthor"] = True
    if raw.get("author-only"):
        cite["authorOnly"] = True
    if data:
        cite["itemData"] = data
    return cite
