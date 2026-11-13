# SPDX-License-Identifier: AGPL-3.0-only
"""hst-document-tab-switch-no-flash.patch: a document tab switch paints the shown window before the previous one hides.

A tab switch shows one top-level window and hides another. vcl paints a newly shown window later (paint idle) and
Skia copies it to the screen later still, so hiding the previous tab right away showed the desktop for a frame on
every switch (error report HSTO-000006; tests/runtime/check-windows-tab-switch-flash.py measures it on Windows).
Offline: every place that parks the previous tab after showing another one paints that one first."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-document-tab-switch-no-flash.patch"
CXX = "framework/source/services/documenttabgroup.cxx"
HXX = "framework/inc/documenttabgroup.hxx"


def hunks(path=CXX):
    """[(context and added lines of one hunk, removed lines)] of the patch, for `path`."""
    out, current, inside = [], None, False
    for line in PATCH.read_text(encoding="utf-8").split("\n---\n", 1)[1].splitlines():
        if line.startswith("+++ b/"):
            inside, current = line[6:] == path, None
            continue
        if not inside:
            continue
        if line.startswith("@@"):
            current = ([], [])
            out.append(current)
        elif current is None or line.startswith(("--- a/", "+++ b/")):
            continue
        elif line.startswith("-"):
            current[1].append(line[1:])
        else:
            current[0].append(line[1:])
    return out


class DocumentTabSwitchNoFlash(unittest.TestCase):
    def test_last_in_series_after_the_tab_patches(self):
        series = [n for n in (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
                  if not n.startswith("#")]
        self.assertEqual(series.count(PATCH.name), 1)
        for earlier in ("hst-document-tabs.patch", "hst-macos-tab-windows.patch", "hst-module-window-groups.patch"):
            self.assertGreater(series.index(PATCH.name), series.index(earlier))

    def test_touches_the_tab_group_only(self):
        text = PATCH.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^\+\+\+ b/(\S+)", text, re.M), [HXX, CXX])
        self.assertIn("License: modified upstream files keep their license (MPL-2.0).", text.split("\n---\n")[0])

    def test_paint_then_flush(self):
        helper = "\n".join(hunks()[0][0])
        body = helper[helper.index("void lcl_paintNow"):]
        self.assertLess(body.index("PaintImmediately()"), body.index("GetOutDev()->Flush()"))
        self.assertIn("isDisposed()", body)

    def test_every_park_after_a_show_paints_first(self):
        """Hunks that park a tab: the shown window is painted before park(). Removed: comments, the synchronous park
        of a switch and the user events that parked (both now the idle)."""
        allowed = ("park(*pOld);", "if (Member* pOld = find(xPrevious); pOld && xPrevious != xFrame)",
                   "Application::PostUserEvent(LINK(this, DocumentTabGroup, ParkPreviousHdl));")
        parks = 0
        for lines, removed in hunks()[1:]:
            self.assertTrue(all(r.strip().startswith("//") or r.strip() in allowed for r in removed), removed)
            code = "\n".join(lines)
            if "park(*" in code:
                parks += 1
                self.assertLess(code.index("lcl_paintNow("), code.index("park(*"), code)
        self.assertEqual(parks, 2)  # the deferred park, a tab dropped on another window
        closing = [lines for lines, _removed in hunks()[1:] if any("closed tab" in line for line in lines)]
        self.assertEqual(len(closing), 1)
        code = "\n".join(closing[0])
        self.assertLess(code.index("Show(true"), code.index("lcl_paintNow(pNextWindow)"))

    def test_switch_hides_the_previous_tab_from_a_lowest_priority_idle(self):
        """vcl's layout, paint and Skia flush idles run first; the previous tab stays under the shown one till then."""
        header = "\n".join(hunks(HXX)[-1][0] + [x for h in hunks(HXX) for x in h[0]])
        self.assertIn("Idle m_aParkIdle", header)
        self.assertIn("DECL_LINK(ParkIdleHdl, Timer*, void);", header)
        code = "\n".join(x for h in hunks() for x in h[0])
        self.assertIn("m_aParkIdle.SetPriority(TaskPriority::LOWEST);", code)
        self.assertIn("IMPL_LINK_NOARG(DocumentTabGroup, ParkIdleHdl, Timer*, void) { ParkPreviousHdl(nullptr); }", code)
        switch = next("\n".join(lines) for lines, _r in hunks() if any("ParkIdleHdl), so the desktop" in x for x in lines))
        self.assertLess(switch.index("lcl_paintNow(pTargetWindow)"), switch.index("m_aParkIdle.Start()"))
        self.assertNotIn("park(*pOld)", switch)
        removed = [x for _l, r in hunks() for x in r]
        self.assertIn("            park(*pOld);", removed)
        self.assertEqual(sum(x.count("PostUserEvent(LINK(this, DocumentTabGroup, ParkPreviousHdl))") for x in removed), 2)
        self.assertIn("    m_aParkIdle.Stop();", code)

    def test_parked_tab_looked_up_again_after_painting(self):
        """Painting can run events (a tab closed meanwhile): the deferred park finds its member again."""
        code = "\n".join(next(lines for lines, _r in hunks() if any("painting can run events" in x for x in lines)))
        self.assertLess(code.index("lcl_paintNow"), code.index("find(xToPark, &pGroup); // painting"))
        self.assertIn("xToPark == lcl_get(pGroup->xActive)", code)


if __name__ == "__main__":
    unittest.main()
