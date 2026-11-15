# SPDX-License-Identifier: AGPL-3.0-only
"""Large-file open fixes in patches/libreoffice (offline: reads the patch hunks).

- hst-calc-xlsx-shared-formula-results.patch: a shared formula's cached number is kept (ResetDirty + SetChanged(false)
  like a formula of its own), with a CppunitTest that builds an .xlsx whose cached results differ from the formula.
- hst-threadpool-no-timeout-abort.patch: release builds no longer throw out of ThreadTaskTag::waitUntilDone after
  10 minutes (the waiting frame owns the running tasks' data; the throw aborted the office).
- hst-calc-pattern-registry-hash-index.patch: CellAttributeHelper looks candidates up in a hash index instead of
  scanning every entry of the style, and rebuilds the index wherever registered entries change in place.
- hst-writer-layout-nexts-only-with-objects.patch: SwTextFrame::Format collects the next-chain (all following
  paragraphs during the first layout) only when the page has anchored objects."""
from pathlib import Path
import re
import unittest

PATCHES = Path(__file__).resolve().parents[2] / "patches/libreoffice"
NAMES = ("hst-calc-xlsx-shared-formula-results.patch", "hst-threadpool-no-timeout-abort.patch",
         "hst-calc-pattern-registry-hash-index.patch", "hst-writer-layout-nexts-only-with-objects.patch")


def changes(name):
    """{path: (removed lines, added lines, lines after the patch)} of a unified diff."""
    out, current = {}, None
    for line in (PATCHES / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:].split("\t")[0], ([], [], []))
        elif current is None or line.startswith(("@@", "--- a/")):
            continue
        elif line.startswith("-"):
            current[0].append(line[1:])
        elif line.startswith("+"):
            current[1].append(line[1:])
            current[2].append(line[1:])
        elif line.startswith(" "):
            current[2].append(line[1:])
    return out


class LargeFileOpenPatches(unittest.TestCase):
    def test_series_order(self):
        series = [n for n in (PATCHES / "series").read_text(encoding="utf-8").split() if not n.startswith("#")]
        self.assertEqual([series.index(n) for n in NAMES], sorted(series.index(n) for n in NAMES))

    def test_shared_formula_results_kept(self):
        ch = changes(NAMES[0])
        self.assertEqual(set(ch), {"sc/source/filter/oox/formulabuffer.cxx", "sc/qa/unit/subsequent_filters_test5.cxx"})
        removed, added, _ = ch["sc/source/filter/oox/formulabuffer.cxx"]
        code = [line.strip() for line in added if not line.strip().startswith("//")]
        self.assertEqual(code, ["pCell->ResetDirty();", "pCell->SetChanged(false);"])
        self.assertTrue(all(line.strip().startswith(("/*", "*")) for line in removed))
        test = "\n".join(ch["sc/qa/unit/subsequent_filters_test5.cxx"][1])
        self.assertIn("testXlsxSharedFormulaCachedResults", test)
        self.assertIn('t=\\"shared\\"', test)
        self.assertIn("CPPUNIT_ASSERT_EQUAL(8.0", test)  # no cached result: still calculated

    def test_threadpool_does_not_throw(self):
        ch = changes(NAMES[1])
        self.assertEqual(set(ch), {"comphelper/source/misc/threadpool.cxx"})
        removed, added, after = ch["comphelper/source/misc/threadpool.cxx"]
        self.assertTrue(any("throw std::runtime_error" in line for line in removed))
        self.assertFalse(any("throw" in line for line in added + after if not line.strip().startswith("//")))
        self.assertTrue(any("SAL_WARN" in line for line in added))
        self.assertTrue(any("assert(result != std::cv_status::timeout)" in line for line in after))  # debug builds

    def test_pattern_registry_hash_index(self):
        ch = changes(NAMES[2])
        self.assertEqual(set(ch), {"sc/inc/patattr.hxx", "sc/source/core/data/patattr.cxx", "sc/qa/unit/ucalc.cxx"})
        removed = "\n".join(ch["sc/source/core/data/patattr.cxx"][0])
        added = "\n".join(ch["sc/source/core/data/patattr.cxx"][1])
        # the per-style linear scan of registerAndCheck() is replaced by the hash lookup
        self.assertIn("maRegisteredCellAttributes.find(pCandidateStyleName", removed)
        self.assertIn("for (const ScPatternAttr* pCheck : it->second)", removed)
        self.assertIn("maRegisteredByHash.equal_range(rCandidate.GetHashCode())", added)
        self.assertIn("addToHashIndex(pCandidate);", added)
        self.assertIn("removeFromHashIndex(&rCandidate);", added)
        # every in-place change of registered entries refreshes the index
        self.assertGreaterEqual(len(re.findall(r"^\s*rebuildHashIndex\(\);", added, re.M)), 6)
        header = "\n".join(ch["sc/inc/patattr.hxx"][1])
        self.assertIn("std::unordered_multimap<size_t, const ScPatternAttr*>", header)
        self.assertIn("mnIndexedHashCode", header)
        self.assertIn("testCellAttributeRegistryManyFormats", "\n".join(ch["sc/qa/unit/ucalc.cxx"][1]))

    def test_writer_next_chain_only_with_objects(self):
        ch = changes(NAMES[3])
        self.assertEqual(set(ch), {"sw/source/core/text/frmform.cxx"})
        removed, added, after = ch["sw/source/core/text/frmform.cxx"]
        text = "\n".join(after)
        guard = text.index("pPage && pPage->GetSortedObjs())")
        loop = text.index("for (SwFrame const* pNext = GetNext(); pNext; pNext = pNext->GetNext())")
        self.assertLess(guard, loop)
        self.assertLess(loop, text.index("FormatImpl(pRenderContext, EnsurePara(), intersectingObjs);"))
        self.assertIn("nexts.push_back(pNext);", "\n".join(removed))  # re-indented under the guard


if __name__ == "__main__":
    unittest.main()
