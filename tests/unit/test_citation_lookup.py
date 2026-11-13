# SPDX-License-Identifier: AGPL-3.0-only
"""Online lookup, tested offline with recorded answers: identifiers, requests (no contact address unless one is
configured), conversion of every service, fallbacks, rate limits, the switch-off and the HTTPS helper's URL rules."""
import os
import unittest

import _paths

from hst_office import citation_lookup as lookup
from hst_office import citation_lookup_http as http
from hst_office.citation_lookup_ids import LookupFailure, parse_identifier

RECORDED = os.path.join(_paths.ROOT, "tests", "fixtures", "citations", "lookup")
ANSWERS = (("https://doi.org/10.1038/nature14539", "doi-org-10.1038-nature14539.json"),
           ("https://api.crossref.org/works/10.54607/", "crossref-vietnamese-inverted-name.json"),
           ("https://api.crossref.org/works/10.1038/", "crossref-10.1038-nature14539.json"),
           ("https://eutils.ncbi.nlm.nih.gov/", "pubmed-esummary-32109011.json"),
           ("https://export.arxiv.org/", "arxiv-1706.03762.xml"),
           ("https://openlibrary.org/api/books?bibkeys=ISBN:9780393071016", "openlibrary-isbn-9780393071016.json"),
           ("https://api.crossref.org/works?", "crossref-query-bibliographic.json"))


class Recorded:
    def __init__(self, broken=()):
        self.requests, self.broken = [], broken

    def __call__(self, request):
        self.requests.append(request)
        if any(request["url"].startswith(prefix) for prefix in self.broken):
            raise TimeoutError("deadline")
        for prefix, name in ANSWERS:
            if request["url"].startswith(prefix):
                with open(os.path.join(RECORDED, name), "rb") as handle:
                    return 200, handle.read()
        return 404, b""


def gate():
    ticks = iter(range(0, 10_000, 10))
    return lookup.RateGate(clock=lambda: next(ticks))


class Identifiers(unittest.TestCase):
    def test_kinds(self):
        cases = {"10.1038/nature14539": ("doi", "10.1038/nature14539"),
                 "https://doi.org/10.54607/hcmue.js.18.8.3112(2021)": ("doi", "10.54607/hcmue.js.18.8.3112(2021)"),
                 "doi: 10.1056/NEJMe2002387": ("doi", "10.1056/NEJMe2002387"),
                 "PMID: 32109011": ("pmid", "32109011"), "32109011": ("pmid", "32109011"),
                 "arXiv:1706.03762v7": ("arxiv", "1706.03762"), "https://arxiv.org/abs/hep-th/9901001": ("arxiv",
                                                                                                         "hep-th/9901001"),
                 "978-0-393-07101-6": ("isbn", "9780393071016"), "0-306-40615-2": ("isbn", "9780306406157")}
        for text, expected in cases.items():
            self.assertEqual(parse_identifier(text), expected, text)
        for text in ("", "hello", "978-0-393-07101-7", "x" * 400):
            with self.assertRaises(LookupFailure):
                parse_identifier(text)


class Requests(unittest.TestCase):
    def test_contact_address_only_when_configured(self):
        plain = lookup.requests_for("pmid", "1", lookup.LookupConfig())
        self.assertIn("tool=HSTOffice", plain[0][1])
        self.assertNotIn("email", plain[0][1])
        self.assertNotIn("mailto", lookup.requests_for("doi", "10.1/x", lookup.LookupConfig())[1][1])
        configured = lookup.LookupConfig(contact="lookup@example.org")
        self.assertIn("email=lookup%40example.org", lookup.requests_for("pmid", "1", configured)[0][1])
        self.assertIn("mailto=lookup%40example.org", lookup.requests_for("doi", "10.1/x", configured)[1][1])
        for kind, value in (("doi", "10.1/x"), ("pmid", "1"), ("arxiv", "1706.03762"), ("isbn", "9780393071016")):
            for _, url, _ in lookup.requests_for(kind, value, configured):
                self.assertTrue(http.allowed(url), url)


class Lookups(unittest.TestCase):
    def run_lookup(self, text, transport=None, config=None):
        return lookup.lookup(text, config or lookup.LookupConfig(version="1.0.2"), transport or Recorded(), gate())

    def test_every_service(self):
        doi = self.run_lookup("10.1038/nature14539")
        self.assertEqual((doi["service"], doi["items"][0]["type"], doi["items"][0]["container-title"]),
                         ("doi.org", "article-journal", "Nature"))
        self.assertNotIn("abstract", doi["items"][0])
        pubmed = self.run_lookup("PMID 32109011")["items"][0]
        self.assertEqual((pubmed["DOI"], pubmed["author"][0]), ("10.1056/NEJMe2002387",
                                                                {"family": "Fauci", "given": "A. S."}))
        arxiv = self.run_lookup("1706.03762")["items"][0]
        self.assertEqual((arxiv["number"], arxiv["issued"], len(arxiv["author"])), ("arXiv:1706.03762",
                                                                                     {"date-parts": [[2017, 6, 12]]}, 8))
        book = self.run_lookup("9780393071016")["items"][0]
        self.assertEqual((book["type"], book["author"][0]["family"]), ("book", "Krugman"))

    def test_vietnamese_crossref_answer_gets_name_fixes(self):
        found = self.run_lookup("10.54607/hcmue.js.18.8.3112(2021)")  # doi.org 404 -> Crossref
        self.assertEqual(found["service"], "crossref")
        kinds = [s["kind"] for s in found["suggestions"]]
        self.assertEqual(kinds, ["name-order", "sentence-case", "language"])
        self.assertEqual(found["suggestions"][0]["new"], {"family": "Nguyễn", "given": "Văn An", "hst-vi": True})

    def test_fallback_when_doi_org_times_out(self):
        transport = Recorded(broken=("https://doi.org/",))
        self.assertEqual(self.run_lookup("10.1038/nature14539", transport)["service"], "crossref")
        self.assertEqual(len(transport.requests), 2)

    def test_failures(self):
        with self.assertRaises(LookupFailure) as caught:
            self.run_lookup("10.9999/not-recorded")  # doi.org 404, Crossref 404
        self.assertEqual(caught.exception.kind, "not-found")
        with self.assertRaises(LookupFailure) as caught:
            self.run_lookup("9786040000002")
        self.assertIn("978-604", caught.exception.message)
        with self.assertRaises(LookupFailure) as caught:
            self.run_lookup("10.1038/nature14539", config=lookup.LookupConfig(enabled=False))
        self.assertEqual(caught.exception.kind, "disabled")
        with self.assertRaises(LookupFailure) as caught:
            self.run_lookup("1706.03762", Recorded(broken=("https://export.arxiv.org/",)))
        self.assertEqual(caught.exception.kind, "network")
        with self.assertRaises(LookupFailure) as caught:
            self.run_lookup("10.1038/x", lambda request: (429, b""))
        self.assertEqual(caught.exception.kind, "rate")

    def test_rate_gate(self):
        now = [0.0]
        polite = lookup.RateGate(clock=lambda: now[0])
        polite.check("export.arxiv.org")
        with self.assertRaises(LookupFailure):
            polite.check("export.arxiv.org")
        now[0] = 3.5
        polite.check("export.arxiv.org")
        polite.check("doi.org")
        polite.check("doi.org")

    def test_reference_line_matching(self):
        matches = lookup.lookup_reference("LeCun Bengio Hinton 2015 Deep learning Nature", lookup.LookupConfig(),
                                          Recorded(), gate=gate())
        self.assertEqual([(i["DOI"], round(s)) for i, s in matches], [("10.1038/nature14539", 66),
                                                                       ("10.1145/3448250", 48)])
        with self.assertRaises(LookupFailure):
            lookup.lookup_reference("short", lookup.LookupConfig(), Recorded())


class Helper(unittest.TestCase):
    def test_url_rules(self):
        self.assertTrue(http.allowed("https://doi.org/10.1/x"))
        for url in ("http://doi.org/10.1/x", "https://evil.example/x", "https://doi.org.evil.example/",
                    "https://user@doi.org/x", "https://doi.org:8443/x", "file:///etc/passwd"):
            self.assertFalse(http.allowed(url), url)
        with self.assertRaises(ValueError):
            http.get("https://evil.example/", "application/json", "1.0.2")
        with self.assertRaises(ValueError):
            http.get("https://doi.org/10.1/x", "application/json", "1.0.2\r\nX-Injected: 1")


if __name__ == "__main__":
    unittest.main()
