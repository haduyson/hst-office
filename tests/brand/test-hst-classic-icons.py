# SPDX-License-Identifier: AGPL-3.0-only
"""The Cổ điển style: HST glyphs only for requests Colibre does not resolve, never shadowing Colibre."""
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/brand"))
import hst_classic_icons as classic  # noqa: E402

spec = importlib.util.spec_from_file_location("hst_theme", ROOT / "scripts/brand/build-hst-icon-theme.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"/>'


def colibre_tree(root, files, links, theme="colibre_svg", links_theme="colibre"):
    """A minimal LibreOffice icon-themes/ dir: Colibre SVG files and the PNG theme's links.txt."""
    for name in files:
        path = root / theme / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(SVG)
    (root / links_theme).mkdir(parents=True, exist_ok=True)
    (root / links_theme / "links.txt").write_text("".join(f"{a} {b}\n" for a, b in links.items()))
    return root


class CoverageTest(unittest.TestCase):
    def test_names_resolve_like_vcl(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = colibre_tree(Path(tmp), ["cmd/sc_bold.svg", "cmd/32/bold.svg", "cmd/lc_bold.svg"],
                                {"cmd/sc_fett.png": "cmd/sc_bold.png", "cmd/lc_fett.png": "cmd/lc_bold.png"})
            cover = classic.Coverage(tree, "colibre_svg")
            for name in ("cmd/sc_bold.png", "cmd/sc_bold.svg", "cmd/sc_fett.png", "cmd/32/fett.png"):
                self.assertTrue(cover.covers(name), name)  # links are rewritten to .svg; lc_ links also give 32/
            for name in ("cmd/sc_nd30wizard.png", "cmd/sc_italic.png"):
                self.assertFalse(cover.covers(name), name)

    def test_a_missing_colibre_theme_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                classic.Coverage(Path(tmp), "colibre_svg")


class OverlayTest(unittest.TestCase):
    def overlay(self, theme="hst_classic"):
        with tempfile.TemporaryDirectory() as tmp:
            # Colibre draws bold (all sizes) and the italic 16 px icon only.
            files = ["cmd/sc_bold.svg", "cmd/lc_bold.svg", "cmd/32/bold.svg", "cmd/sc_italic.svg",
                     "res/mainapp_16.svg"]
            tree = colibre_tree(Path(tmp), files, {}, classic.CLASSIC[theme][1],
                                classic.CLASSIC[theme][1].replace("_svg", ""))
            return builder.resources(theme, tree)

    def test_only_what_colibre_lacks_is_layered(self):
        files = self.overlay()
        links = dict(line.split() for line in files["links.txt"].decode().splitlines() if not line.startswith("#"))
        for request in ("cmd/sc_bold.png", "cmd/lc_bold.png", "cmd/32/bold.png", "cmd/sc_italic.png",
                        "res/mainapp_16.png"):
            self.assertNotIn(request, links)  # Colibre's icon is used
        for request in ("cmd/lc_italic.png", "cmd/32/italic.svg", "cmd/sc_nd30wizard.png", "cmd/sc_convertencoding.png",
                        "cmd/lc_showsolutions.png"):
            self.assertIn(links[request], files)  # HST fills Colibre's gaps
        # overlay files never sit where Colibre could look them up directly
        self.assertTrue(all(name.startswith(classic.PREFIX) for name in files if name not in classic.EXTRA))
        self.assertIn("CC0", files["COPYING.txt"].decode())

    def test_hst_glyphs_take_colibre_ink(self):
        for theme, (_, _, ink) in classic.CLASSIC.items():
            files = self.overlay(theme)
            links = dict(line.split() for line in files["links.txt"].decode().splitlines() if not line.startswith("#"))
            glyph = files[links["cmd/lc_italic.png"]].decode()
            self.assertIn(ink, glyph)
            self.assertNotIn("currentColor", glyph)
            mark = files[links["cmd/lc_showsolutions.png"]].decode()
            self.assertIn(builder.MARK_COLOURS[theme], mark)  # the HASON TECH mark keeps its brand blue

    def test_archive_is_deterministic_and_svg_only(self):
        files = self.overlay()
        packed = builder.archive(files)
        self.assertEqual(packed, builder.archive(dict(reversed(list(files.items())))))
        with zipfile.ZipFile(io.BytesIO(packed)) as z:
            self.assertIsNone(z.testzip())
            self.assertFalse(any(n.endswith(".png") for n in z.namelist()))

    def test_the_classic_themes_need_the_tree(self):
        with self.assertRaises(ValueError):
            builder.resources("hst_classic")


if __name__ == "__main__":
    unittest.main()
