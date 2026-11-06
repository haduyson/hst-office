# SPDX-License-Identifier: AGPL-3.0-only
"""Artifact contracts: VCL layout, command coverage, reproducibility and UI scope."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("hst_theme", "scripts/brand/build-hst-icon-theme.py")


class HstThemeTest(unittest.TestCase):
    def test_scanner_layout_and_direct_links(self):
        for theme in builder.PALETTES:
            files = builder.resources(theme)
            packed = builder.archive(files)
            self.assertEqual(packed, builder.archive(dict(reversed(list(files.items())))))
            with zipfile.ZipFile(io.BytesIO(packed)) as z:
                self.assertIsNone(z.testzip())
                self.assertIn("links.txt", z.namelist())
                self.assertIn("LICENSE-CC-BY-4.0.txt", z.namelist())
                self.assertFalse(any(n.endswith(".png") for n in z.namelist()))
                self.assertFalse(any("\\" in n for n in z.namelist()))
                for line in z.read("links.txt").decode().splitlines():
                    if line.startswith("#"):
                        continue
                    alias, target = line.split()
                    self.assertNotIn(alias, z.namelist())
                    self.assertIn(target, z.namelist())
                for key, size in (("cmd/sc_bold.svg", 16), ("cmd/lc_bold.svg", 24), ("cmd/32/bold.svg", 32)):
                    svg = ET.fromstring(z.read(key))
                    self.assertEqual(svg.get("width"), str(size))
                    self.assertEqual(svg.get("height"), str(size))

    def test_all_495_static_commands_have_resources(self):
        files = builder.resources("hst")
        links = dict(line.split() for line in files["links.txt"].decode().splitlines() if not line.startswith("#"))
        families = json.loads((builder.SOURCE / "metadata/families.json").read_text())
        commands = set()
        for family in families:
            if family.get("skip"):
                continue
            if not family.get("extension_tab"):
                commands.update(family["commands"])
            for key in family["keys"]:
                for size in (16, 24, 32):
                    request = builder.sized(key, size)
                    self.assertIn(links.get(request, request), files)
        self.assertEqual(len(commands), 495)
        # These fixed controller labels are not ordinary UNO command names.
        for number in (10863, 10864, 10868, 10869):
            self.assertIn(links[f"svx/res/sc{number}.png"] if f"svx/res/sc{number}.png" in links
                          else links[f"res/sc{number}.png"], files)

    def test_extension_tab_commands_have_their_own_glyphs(self):
        # VCL names a command image after the path of its URL: org.hst.office.vi:SplitName -> splitname.
        names = ("convertencoding", "numbertowords", "formatdate", "formatvnd", "importcsv", "removediacritics",
                 "splitname", "sortbygivenname", "deleteblankrows", "showsolutions")
        reused = {"formatpercent": "numberformatpercent", "nd30wizard": "insertdoc"}
        for theme in builder.PALETTES:
            files = builder.resources(theme)
            links = dict(line.split() for line in files["links.txt"].decode().splitlines() if not line.startswith("#"))
            for name in names:
                # Giải pháp HASON TECH shows the company mark in brand blue, not the glyph ink.
                colour = (builder.MARK_COLOURS if name == "showsolutions" else builder.PALETTES)[theme].encode()
                for size in (16, 24, 32):
                    key = builder.svg_key(builder.sized(f"cmd/{name}.png", size))
                    self.assertIn(key, files)
                    self.assertIn(colour, files[key])
                    self.assertEqual(links[key[:-4] + ".png"], key)
            for name, target in reused.items():
                for size in (16, 24, 32):
                    self.assertEqual(links[builder.sized(f"cmd/{name}.png", size)],
                                     builder.svg_key(builder.sized(f"cmd/{target}.png", size)))
            masters = {files[builder.svg_key(builder.sized(f"cmd/{name}.png", 32))] for name in names}
            self.assertEqual(len(masters), len(names))

    def test_solutions_button_is_the_trademark_mark_outside_cc_by(self):
        def polygons(path):
            return [n.get("points") for n in ET.parse(ROOT / path).iter("{http://www.w3.org/2000/svg}polygon")]
        mark = "branding/icon-themes/hasontech-mark.svg"
        self.assertEqual(polygons(mark), polygons("branding/icons/app/hst-office.svg"))
        families = json.loads((builder.SOURCE / "metadata/families.json").read_text())
        self.assertEqual([f["glyph"] for f in families if f.get("trademark")], ["showsolutions"])
        self.assertFalse((builder.SOURCE / "glyphs/stage-1/showsolutions.svg").exists())
        for theme in builder.PALETTES:
            files = builder.resources(theme)
            svg = files["cmd/32/showsolutions.svg"]
            self.assertNotIn(b"CC-BY", svg)
            self.assertNotIn(b"currentColor", svg)
            self.assertEqual(ET.fromstring(svg).get("width"), "32")
            copying = files["COPYING.txt"].decode()
            self.assertIn("cmd/32/showsolutions.svg", copying)
            self.assertIn("not a CC BY glyph", copying)

    def test_check_is_read_only_and_stale_output_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            builder.sync(path, {"links.txt": b"one"})
            (path / "stale.png").write_bytes(b"old")
            with self.assertRaises(ValueError):
                builder.sync(path, {"links.txt": b"two"}, check=True)
            self.assertEqual((path / "links.txt").read_bytes(), b"one")
            self.assertTrue((path / "stale.png").exists())
            builder.sync(path, {"links.txt": b"two"})
            self.assertFalse((path / "stale.png").exists())

    def test_runtime_shape_subtypes_and_native_navigation_sizes(self):
        files = builder.resources("hst_dark")
        for glyph in ("basicshapes.diamond", "arrowshapes.left-right-arrow",
                      "calloutshapes.round-rectangular-callout", "flowchartshapes.flowchart-internal-storage"):
            for prefix in ("cmd/sc_", "cmd/lc_", "cmd/32/"):
                self.assertIn(prefix + glyph + ".svg", files)
        overflow = ET.fromstring(files["sfx2/res/chevron.svg"])
        self.assertEqual((overflow.get("width"), overflow.get("height")), ("14", "16"))
        self.assertIn(b"#DBE7F1", files["sfx2/res/chevron.svg"])
        menu = ET.fromstring(files["res/notebookbar.svg"])
        self.assertEqual((menu.get("width"), menu.get("height")), ("16", "16"))
        self.assertNotEqual(files["res/notebookbar.svg"], files["cmd/sc_menubar.svg"])


if __name__ == "__main__":
    unittest.main()
