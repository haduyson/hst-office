# SPDX-License-Identifier: AGPL-3.0-only
"""The offline user guide (extensions/hst-vietnamese-tools/help, opened by F1) ships inside the product:
no GitHub or upstream-project names or links, no remote resources, every local link and image resolves."""
import glob
import os
import re
import unittest

import _paths

HELP = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "help")
EXT = os.path.dirname(HELP)
FORBIDDEN = re.compile(r"github|libreoffice|openoffice|document foundation", re.I)


def pages():
    return sorted(glob.glob(os.path.join(HELP, "*.html")))


class UserGuide(unittest.TestCase):
    def test_has_pages(self):
        self.assertIn(os.path.join(HELP, "index.html"), pages())

    def test_no_forbidden_names(self):
        for path in pages() + glob.glob(os.path.join(HELP, "*.css")):
            text = open(path, encoding="utf-8").read()
            self.assertIsNone(FORBIDDEN.search(text), "%s: %s" % (os.path.basename(path), FORBIDDEN.search(text)))

    def test_only_hasontech_links_with_utm(self):
        for path in pages():
            text = open(path, encoding="utf-8").read()
            for url in re.findall(r"""(?:href|src)=["'](https?:[^"']+)["']""", text):
                self.assertTrue(re.match(r"https://hasontech\.vn/", url), url)
                self.assertIn("utm_medium=help", url.replace("&amp;", "&"))
            self.assertNotRegex(text, r"""src=["']https?:""")

    def test_contact_is_hasontech(self):
        text = "".join(open(p, encoding="utf-8").read() for p in pages())
        self.assertIn("mailto:lienhe@hasontech.vn", text)

    def test_local_links_and_images_resolve(self):
        for path in pages():
            text = open(path, encoding="utf-8").read()
            for ref in re.findall(r"""(?:href|src)=["']([^"':#]+)(?:#[^"']*)?["']""", text):
                target = os.path.normpath(os.path.join(os.path.dirname(path), ref))
                self.assertTrue(os.path.exists(target) or target.startswith(os.path.join(EXT, "icons")),
                                "%s -> %s" % (os.path.basename(path), ref))


if __name__ == "__main__":
    unittest.main()
