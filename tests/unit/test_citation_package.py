# SPDX-License-Identifier: AGPL-3.0-only
"""The extension package carries exactly the citation styles of data/citation/styles, and the lookup helper is the
only citation module allowed to open HTTPS connections."""
import io
import os
import sys
import unittest
import zipfile

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "scripts"))
import extension_content as content  # noqa: E402

STYLES = os.path.join(_paths.ROOT, "data", "citation", "styles")


def package(files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return zipfile.ZipFile(io.BytesIO(data.getvalue()))


class Styles(unittest.TestCase):
    def test_matching_stale_missing_extra(self):
        names = sorted(n for n in os.listdir(STYLES) if n.endswith(".json"))
        files = {"python/hst_office/citation_engine.py": b""}
        for name in names:
            with open(os.path.join(STYLES, name), "rb") as handle:
                files["data/citation-styles/" + name] = handle.read()
        errors = []
        content.check_citation_styles(package(files), set(files), errors)
        self.assertEqual(errors, [])
        broken = dict(files)
        broken["data/citation-styles/" + names[0]] = b"{}"
        del broken["data/citation-styles/" + names[1]]
        broken["data/citation-styles/extra.json"] = b"{}"
        content.check_citation_styles(package(broken), set(broken), errors)
        self.assertEqual(len(errors), 2)
        self.assertIn("extra.json", errors[0])
        self.assertIn("stale", errors[1])

    def test_network_rules(self):
        lookup_http = "python/hst_office/citation_lookup_http.py"
        self.assertEqual(content.CITATION_LOOKUP_HTTP, lookup_http)
        source = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", lookup_http)
        with open(source, encoding="utf-8") as handle:
            self.assertIsNone(content.UPDATE_FETCH_IMPORT.search(handle.read()))
        folder = os.path.dirname(source)
        for name in os.listdir(folder):
            if name.startswith("citation_") and name != "citation_lookup_http.py":
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    self.assertIsNone(content.NETWORK_IMPORT.search(handle.read()), name)


if __name__ == "__main__":
    unittest.main()
