# SPDX-License-Identifier: AGPL-3.0-only
"""Online lookup of a reference by DOI, PubMed ID, arXiv ID or ISBN, and matching a pasted reference line through
Crossref. Runs only when the user clicks "Tra cứu"; nothing here is called in the background.

What is sent: only the identifier (or the pasted line for "Tìm theo dòng đã dán"), the User-Agent
"HSTOffice/<release>" and, when the administrator configured one, the project contact address (Crossref ``mailto``,
NCBI ``email``). No cookie, no document content. Order: DOI via doi.org (Crossref as fallback) > PMID via NCBI
E-utilities > arXiv > ISBN via Open Library. Results go through the "sửa tên Việt" suggestions.

Network access is injected: ``transport(request) -> (status, body bytes)``; production uses ``http_transport``
(citation_lookup_http.py in its own process with a hard deadline). Tests pass recorded answers.
"""
import json
import time
import urllib.parse

from . import citation_lookup_convert as convert
from . import citation_vn_fix as vn_fix
from .citation_lookup_ids import LookupFailure, parse_identifier

HOSTS = ("doi.org", "api.crossref.org", "data.crossref.org", "api.datacite.org", "data.datacite.org",
         "eutils.ncbi.nlm.nih.gov", "export.arxiv.org", "openlibrary.org")
MIN_INTERVAL = {"export.arxiv.org": 3.0, "eutils.ncbi.nlm.nih.gov": 0.34, "openlibrary.org": 1.0}
DEADLINE = 20
CSL_JSON = "application/vnd.citationstyles.csl+json"


class LookupConfig:
    """Settings read by the UNO layer: ``enabled`` (administrators can switch lookups off), ``contact`` (project
    address for Crossref/NCBI; empty until the owner decides — never the user's address unless they typed it),
    ``version`` (release id for the User-Agent) and ``proxy`` (same proxy settings as the update check)."""

    def __init__(self, enabled=True, contact="", version="0", proxy=None):
        self.enabled, self.contact, self.version, self.proxy = enabled, (contact or "").strip(), version, proxy


class RateGate:
    """Polite spacing per host (arXiv asks for one request every 3 seconds, NCBI three per second)."""

    def __init__(self, clock=time.monotonic):
        self.clock, self.last = clock, {}

    def check(self, host):
        now, wait = self.clock(), MIN_INTERVAL.get(host, 0)
        if host in self.last and now - self.last[host] < wait:
            raise LookupFailure("rate", "Vui lòng đợi %.0f giây rồi tra cứu lại." % max(1, wait - (now - self.last[host])))
        self.last[host] = now


_GATE = RateGate()


def requests_for(kind, value, config):
    """[(service, url, accept)] in fallback order."""
    quoted = urllib.parse.quote(value, safe="/()")
    contact = config.contact
    if kind == "doi":
        crossref = "https://api.crossref.org/works/" + quoted + ("?mailto=" + urllib.parse.quote(contact) if contact else "")
        return [("doi.org", "https://doi.org/" + quoted, CSL_JSON), ("crossref", crossref, "application/json")]
    if kind == "pmid":
        query = {"db": "pubmed", "retmode": "json", "id": value, "tool": "HSTOffice"}
        if contact:
            query["email"] = contact
        return [("ncbi", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urllib.parse.urlencode(query),
                 "application/json")]
    if kind == "arxiv":
        return [("arxiv", "https://export.arxiv.org/api/query?id_list=" + quoted, "application/atom+xml")]
    return [("openlibrary", "https://openlibrary.org/api/books?bibkeys=ISBN:%s&format=json&jscmd=data" % value,
             "application/json")]


def _convert(service, body, value):
    if service == "doi.org":
        return convert.from_csl_json(body)
    if service == "crossref":
        return convert.from_crossref(body)
    if service == "ncbi":
        return convert.from_pubmed(body, value)
    if service == "arxiv":
        return convert.from_arxiv(body)
    return convert.from_openlibrary(body, value)


def _fetch(service, url, accept, config, transport, gate):
    if not config.enabled:
        raise LookupFailure("disabled", "Tra cứu trực tuyến đã bị quản trị viên tắt.")
    gate.check(urllib.parse.urlsplit(url).hostname)
    try:
        status, body = transport({"url": url, "accept": accept, "version": config.version, "proxy": config.proxy,
                                  "contact": config.contact})
    except (OSError, ValueError) as exc:  # deadline, no answer, refused redirect: try the next service
        raise LookupFailure("network", "Không kết nối được tới dịch vụ tra cứu. Bạn vẫn có thể nhập tay.") from exc
    if status == 429:
        raise LookupFailure("rate", "Dịch vụ tra cứu đang bận; vui lòng thử lại sau ít phút.")
    return status, body


def lookup(text, config, transport, gate=None):
    """{"items": [CSL item], "service": str, "suggestions": [...]} for an identifier; raises LookupFailure."""
    kind, value = parse_identifier(text)
    gate = gate or _GATE
    failure = None
    for service, url, accept in requests_for(kind, value, config):
        try:
            status, body = _fetch(service, url, accept, config, transport, gate)
        except LookupFailure as exc:
            if exc.kind in ("disabled", "rate"):
                raise
            failure = exc
            continue
        if status == 200 and body:
            try:
                items = _convert(service, body, value)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:  # includes JSON and XML parse errors
                failure = LookupFailure("refused", "Dịch vụ %s trả về dữ liệu không đọc được." % service)
                failure.__cause__ = exc
                continue
            if items:
                return {"items": items, "service": service, "suggestions": vn_fix.suggest(items)}
    if failure:
        raise failure
    hint = " Sách Việt Nam (ISBN 978-604) thường không có trong Open Library." if kind == "isbn" else ""
    raise LookupFailure("not-found", "Không tìm thấy %s %s; hãy nhập tay.%s" % (kind.upper(), value, hint))


def lookup_reference(text, config, transport, rows=3, gate=None):
    """Crossref matches for a pasted reference line: [(item, score)], best first; the user confirms one."""
    line = " ".join((text or "").split())[:500]
    if len(line) < 10:
        raise LookupFailure("invalid", "Dòng tài liệu tham khảo quá ngắn để tìm.")
    query = {"query.bibliographic": line, "rows": str(rows)}
    if config.contact:
        query["mailto"] = config.contact
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(query)
    status, body = _fetch("crossref", url, "application/json", config, transport, gate or _GATE)
    if status != 200:
        raise LookupFailure("not-found", "Crossref không trả lời (mã %s)." % status)
    try:
        return convert.from_crossref_query(body)
    except (ValueError, AttributeError) as exc:
        raise LookupFailure("refused", "Crossref trả về dữ liệu không đọc được.") from exc


def http_transport(timeout=DEADLINE):
    """Transport that runs citation_lookup_http.py in its own process (killed at the deadline)."""
    from . import banner_fetch

    def run(request):
        reply = json.loads(banner_fetch._run(json.dumps(request).encode("utf-8"), timeout, "citation_lookup_http.py"))
        return int(reply["status"]), reply.get("body", "").encode("utf-8")
    return run
