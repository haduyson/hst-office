# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-writer-html-paste-readable-colors.patch and hst-writer-html-paste-no-absolute-frames.patch:
HTML pasted from a web page reads as normal text on the Writer page. Checks that the thresholds in
the helper separate the colours of the evidence (Chromium clipboards of Facebook in dark and light
mode, 21/11/2026) as intended, and that every hook in the HTML import runs only when pasting or
inserting (not when an HTML file is opened). The behaviour itself is CppunitTest_sw_hst_html_paste."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
COLORS = PATCHES / "hst-writer-html-paste-readable-colors.patch"
FRAMES = PATCHES / "hst-writer-html-paste-no-absolute-frames.patch"
HELPER = "sw/source/filter/html/hsthtmlpaste.hxx"


def added_lines(patch):
    """{path: [added lines]} of a patch."""
    out, current = {}, None
    for line in patch.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], [])
        elif current is not None and line.startswith("+"):
            current.append(line[1:])
    return out


def constant(name):
    text = "\n".join(added_lines(COLORS)[HELPER])
    return float(re.search(r"constexpr (?:double|int) %s = ([0-9.]+);" % name, text).group(1))


def luminance(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_on_white(rgb):
    return 1.05 / (luminance(rgb) + 0.05)


def dark_band(rgb):
    return (luminance(rgb) <= constant("MAX_DARK_BAND_LUMINANCE")
            and max(rgb) - min(rgb) <= constant("MAX_DARK_BAND_CHROMA"))


class Thresholds(unittest.TestCase):
    def test_text_colours_of_the_evidence(self):
        base, strict = constant("MIN_TEXT_CONTRAST"), constant("MIN_TEXT_CONTRAST_FROM_DARK_BAND")
        # dropped anywhere: dark-mode body text, peach text of the coloured-background post
        for rgb in [(226, 229, 233), (255, 200, 145)]:
            self.assertLess(contrast_on_white(rgb), base, rgb)
        # kept on white: light-mode text and grey, red, blue, green, light grey
        for rgb in [(8, 8, 9), (101, 104, 108), (255, 0, 0), (0, 0, 255), (0, 128, 0), (204, 204, 204)]:
            self.assertGreaterEqual(contrast_on_white(rgb), base, rgb)
        # dropped from a dark band: dark-mode secondary grey and link blue; kept: grey and red
        for rgb in [(176, 179, 184), (88, 166, 255)]:
            self.assertLess(contrast_on_white(rgb), strict, rgb)
        for rgb in [(139, 148, 158), (240, 40, 73), (28, 30, 33)]:
            self.assertGreaterEqual(contrast_on_white(rgb), strict, rgb)

    def test_dark_bands(self):
        # dark-mode surfaces: Facebook, GitHub, ChatGPT, Solarized
        for rgb in [(37, 39, 40), (51, 51, 52), (58, 59, 60), (24, 25, 26), (13, 17, 23), (22, 27, 34),
                    (33, 33, 33), (0, 43, 54)]:
            self.assertTrue(dark_band(rgb), rgb)
        # light-mode surfaces and dark design colours of light pages stay
        for rgb in [(255, 255, 255), (240, 242, 245), (13, 71, 161), (139, 0, 0), (211, 47, 47)]:
            self.assertFalse(dark_band(rgb), rgb)


class Hooks(unittest.TestCase):
    def test_series_order(self):
        series = (PATCHES / "series").read_text(encoding="utf-8").split()
        self.assertLess(series.index(COLORS.name), series.index(FRAMES.name))

    def test_every_hook_is_paste_only(self):
        for patch in (COLORS, FRAMES):
            for path, lines in added_lines(patch).items():
                if not path.startswith("sw/source/filter/html/") or "/hsthtmlpaste." in path:
                    continue
                code = [line for line in lines if line.strip() and not line.strip().startswith("//")]
                calls = [line for line in code if "Hst" in line or "hst::" in line]
                if path.endswith("swhtml.hxx"):
                    continue
                self.assertTrue(calls, path)
                for line in calls:
                    self.assertIn("!IsNewDoc()", "\n".join(code[max(0, code.index(line) - 1):code.index(line) + 1]),
                                  "%s: %s" % (path, line))

    def test_no_ui_files(self):
        for patch in (COLORS, FRAMES):
            self.assertFalse([p for p in added_lines(patch) if p.endswith(".ui")])


if __name__ == "__main__":
    unittest.main()
