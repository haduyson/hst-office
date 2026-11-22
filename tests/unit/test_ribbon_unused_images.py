# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Every top-level GtkImage the patch series adds to a Tabbed notebookbar.ui is still some button's image once the
whole series is applied. VclBuilder keeps an image no button takes as a second child window of the NotebookBar,
which turns its layout off: the ribbon shrinks to a few pixels (HST Draw opened without its ribbon that way).
Reads the patches only: definitions and references are counted net over the series (+ adds, - removes)."""
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
NOTEBOOKBARS = ("sw/uiconfig/swriter/ui/notebookbar.ui", "sc/uiconfig/scalc/ui/notebookbar.ui",
                "sd/uiconfig/simpress/ui/notebookbar.ui", "sd/uiconfig/sdraw/ui/notebookbar.ui")
TOP_IMAGE = re.compile(r'^  <object class="GtkImage" id="([^"]+)">')
IMAGE_REF = re.compile(r'<property name="image">([^<]+)</property>')


def series():
    with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
        return [line.split()[0] for line in handle if line.strip() and not line.startswith("#")]


def sections(text):
    """(path, hunk lines) of every file section of a patch."""
    for part in re.split(r"(?m)^(?=--- a/)", text)[1:]:
        match = re.match(r"--- a/\S+\n\+\+\+ b/(\S+)", part)
        if match:
            yield match.group(1), part.splitlines()[2:]


def net_images(names):
    """{notebookbar: (defined id -> net count, referenced id -> net count)} over the given patches in order."""
    result = {path: ({}, {}) for path in NOTEBOOKBARS}
    for name in names:
        with open(os.path.join(PATCHES, name), encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        for path, lines in sections(text):
            if path not in result:
                continue
            defined, referenced = result[path]
            for line in lines:
                sign = {"+": 1, "-": -1}.get(line[:1])
                if not sign:
                    continue
                body = line[1:]
                if match := TOP_IMAGE.match(body):
                    defined[match.group(1)] = defined.get(match.group(1), 0) + sign
                for ref in IMAGE_REF.findall(body):
                    referenced[ref] = referenced.get(ref, 0) + sign
    return result


def unused(result):
    return {path: sorted(i for i, n in defined.items() if n > 0 and referenced.get(i, 0) <= 0)
            for path, (defined, referenced) in result.items()}


class RibbonUnusedImages(unittest.TestCase):
    def test_no_series_image_is_left_without_a_button(self):
        self.assertEqual(unused(net_images(series())), {path: [] for path in NOTEBOOKBARS})

    def test_the_rule_sees_the_draw_image_left_by_the_mockup(self):
        names = series()
        before_fix = names[:names.index("hst-ribbon-draw-unused-image.patch")]
        self.assertEqual(unused(net_images(before_fix))["sd/uiconfig/sdraw/ui/notebookbar.ui"],
                         ["imgHstArrangeTransform"])


if __name__ == "__main__":
    unittest.main()
