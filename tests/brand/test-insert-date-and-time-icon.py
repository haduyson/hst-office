# SPDX-License-Identifier: AGPL-3.0-only
"""Insert ▸ Date and Time (.uno:InsertDateAndTime) of the Slides ribbon has an icon in every theme HST ships: the
HST themes alias it to their date field glyph (integration-map.json), and the Slides ribbon patch links it to the
date field icon in Colibre and Colibre dark, which had none (so hst_classic, built on Colibre, gets it too)."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-ribbon-mockup-impress.patch"
SIZES = {"cmd/sc_": "cmd/sc_", "cmd/lc_": "cmd/lc_", "cmd/32/": "cmd/32/"}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("hst_theme_date_icon", "scripts/brand/build-hst-icon-theme.py")


def added_links(patch_text, theme):
    """{link: target} added by the patch to icon-themes/<theme>/links.txt."""
    section = re.search(rf"(?ms)^\+\+\+ b/icon-themes/{theme}/links\.txt\n(.*?)(?=^diff |\Z)", patch_text)
    if section is None:
        return {}
    return dict(line[1:].split() for line in section.group(1).splitlines() if line.startswith("+"))


class InsertDateAndTimeIconTest(unittest.TestCase):
    def test_hst_themes_alias_the_date_field_glyph(self):
        for theme in builder.FULL_THEMES:
            files = builder.resources(theme)
            links = dict(line.split() for line in files["links.txt"].decode().splitlines() if not line.startswith("#"))
            for prefix in SIZES:
                for ext in ("png", "svg"):
                    target = links.get(f"{prefix}insertdateandtime.{ext}")
                    self.assertEqual(target, f"{prefix}datefield.svg", (theme, prefix, ext))
                    self.assertIn(target, files, (theme, target))

    def test_colibre_themes_link_the_date_field_icon(self):
        text = PATCH.read_text(encoding="utf-8")
        for theme in ("colibre", "colibre_dark"):
            links = added_links(text, theme)
            self.assertEqual(links, {f"{prefix}insertdateandtime.png": f"{prefix}datefield.png" for prefix in SIZES},
                             theme)


if __name__ == "__main__":
    unittest.main()
