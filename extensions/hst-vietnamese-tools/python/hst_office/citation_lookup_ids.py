# SPDX-License-Identifier: AGPL-3.0-only
"""Identifiers the user types into "Tra cứu": DOI, PubMed ID, arXiv ID or ISBN (checked before anything is sent).
Pure Python (no uno, no network)."""
import re

from . import citation_dedupe as dedupe


class LookupFailure(Exception):
    """A lookup that produced no item; ``kind`` is invalid, not-found, network, rate, refused or disabled."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind, self.message = kind, message


_ARXIV_NEW = re.compile(r"^(?:arxiv:\s*|https?://arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(v\d+)?(?:\.pdf)?$", re.I)
_ARXIV_OLD = re.compile(r"^(?:arxiv:\s*|https?://arxiv\.org/(?:abs|pdf)/)?([a-z][a-z.-]+/\d{7})(v\d+)?$", re.I)
_PMID = re.compile(r"^(?:pmid:?\s*)?(\d{1,8})$", re.I)
_DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/\S+")


def parse_identifier(text):
    """(kind, value) for "doi" | "pmid" | "arxiv" | "isbn"; LookupFailure("invalid") otherwise."""
    text = (text or "").strip()
    if not text or len(text) > 300:
        raise LookupFailure("invalid", "Hãy nhập mã DOI, PubMed ID (PMID), arXiv ID hoặc ISBN.")
    doi = dedupe.clean_doi(text)
    if not doi:
        found = _DOI_IN_TEXT.search(text)
        doi = dedupe.clean_doi(found.group(0)) if found else ""
    if doi:
        return "doi", doi
    for pattern in (_ARXIV_NEW, _ARXIV_OLD):
        match = pattern.match(text)
        if match:
            return "arxiv", match.group(1)
    match = _PMID.match(text)
    if match and not re.fullmatch(r"\d{10}|\d{13}", text):
        return "pmid", match.group(1)
    isbn = dedupe.isbn13(text)
    if isbn:
        return "isbn", isbn
    if re.fullmatch(r"[\d\s-]{9,17}[\dXx]", text):
        raise LookupFailure("invalid", "ISBN không hợp lệ (sai số kiểm tra).")
    raise LookupFailure("invalid", "Không nhận ra mã DOI, PubMed ID (PMID), arXiv ID hay ISBN trong “%s”." % text[:60])
