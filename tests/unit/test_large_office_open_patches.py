# SPDX-License-Identifier: AGPL-3.0-only
"""Large office-document open fixes in patches/libreoffice (offline: reads the patch hunks).

- hst-docx-comments-parse-once.patch: comments.xml is read once and cut per <w:comment>; every comment parses only
  its own element (with the original prolog and root tags) instead of the whole part, with a fallback to the old full
  parse for anything unexpected, and a CppunitTest that imports 22 comments.
- hst-writer-autostyle-hashed-lookup.patch: SfxGrabBagItem::hashCode() also hashes string values and StylePool nodes
  find hashable children through a hash index (runs with many distinct colours were O(N^2) to import).
- hst-calc-condformat-row-height.patch: relative conditions compile their RPN once; GetNeededSize skips conditions
  whose styles cannot change the size.
- hst-writer-table-name-cache.patch: GetUniqueTableName keeps its scan during a writerfilter import and checks only
  the newest table format, with a fallback to the full scan.
- hst-calc-condformat-row-results-cache.patch: during a row height pass, column independent condition formulas are
  evaluated once per row."""
from pathlib import Path
import unittest

from test_large_file_open_patches import PATCHES, changes

NAMES = ("hst-docx-comments-parse-once.patch", "hst-writer-autostyle-hashed-lookup.patch",
         "hst-calc-condformat-row-height.patch", "hst-writer-table-name-cache.patch")


class LargeOfficeOpenPatches(unittest.TestCase):
    def test_series_appended_in_order(self):
        series = [n for n in (PATCHES / "series").read_text(encoding="utf-8").split() if not n.startswith("#")]
        idx = [series.index(n) for n in NAMES]
        self.assertEqual(idx, sorted(idx))

    def test_comments_parsed_once(self):
        ch = changes(NAMES[0])
        self.assertEqual(set(ch), {"sw/source/writerfilter/inc/ooxml/OOXMLDocument.hxx",
                                   "sw/source/writerfilter/ooxml/OOXMLStreamImpl.hxx",
                                   "sw/source/writerfilter/ooxml/OOXMLStreamImpl.cxx",
                                   "sw/source/writerfilter/ooxml/OOXMLDocumentImpl.cxx",
                                   "sw/qa/writerfilter/ooxml/ooxml.cxx"})
        impl = "\n".join(ch["sw/source/writerfilter/ooxml/OOXMLDocumentImpl.cxx"][2])
        self.assertIn("void OOXMLDocument::splitComments", impl)
        self.assertIn("if (!mpCommentParts)", impl)  # built once, on the first comment
        self.assertIn("comphelper::SequenceInputStream", impl)
        for fallback in ('"<![CDATA["', "std::find(r.begin(), itProbeEnd, 0)", '!= "comment" || aId.empty()'):
            self.assertIn(fallback, impl)
        stream = "\n".join(ch["sw/source/writerfilter/ooxml/OOXMLStreamImpl.cxx"][2])
        self.assertIn("if (mxDocumentInput.is())", stream)
        self.assertIn("testCommentsEachGetOwnText", "\n".join(ch["sw/qa/writerfilter/ooxml/ooxml.cxx"][1]))

    def test_autostyle_hashed_lookup(self):
        ch = changes(NAMES[1])
        self.assertEqual(set(ch), {"svl/source/items/grabbagitem.cxx", "svl/source/items/stylepool.cxx",
                                   "svl/CppunitTest_svl_items.mk", "svl/qa/unit/items/test_grabbagitem.cxx"})
        bag = "\n".join(ch["svl/source/items/grabbagitem.cxx"][1])
        self.assertIn("uno::TypeClass_STRING", bag)  # only strings: equal items keep equal hashes
        pool = "\n".join(ch["svl/source/items/stylepool.cxx"][2])
        self.assertIn("std::unordered_multimap<size_t, Node*> maHashedChildren;", pool)
        self.assertIn("maHashedChildren.equal_range(nKey)", pool)
        self.assertIn("mChildren.emplace_back( pNextNode );", pool)  # child order kept for the iterators
        self.assertIn("test_grabbagitem", "\n".join(ch["svl/CppunitTest_svl_items.mk"][1]))

    def test_condformat_row_height(self):
        ch = changes(NAMES[2])
        cond = "\n".join(ch["sc/source/core/data/conditio.cxx"][2])
        self.assertIn("lcl_IsPositionIndependentCode", cond)
        self.assertIn("GetRelCode(mpRelCode1, *pFormula1, rPos)", cond)
        self.assertEqual(cond.count("mpRelCode1.reset();"), cond.count("pFCell1.reset();"))  # dropped together
        col = "\n".join(ch["sc/source/core/data/column2.cxx"][2])
        self.assertIn("lcl_CondFormatMayChangeSize(rDocument, nTab, *pAttrArray->GetPattern(nRow))", col)
        self.assertIn("pSet = pSet->GetParent()", col)  # the style's parents count too
        self.assertIn("testCondFormatRelativeExpressionCompiledOnce", "\n".join(ch["sc/qa/unit/ucalc_condformat.cxx"][1]))

    def test_table_name_cache(self):
        ch = changes(NAMES[3])
        tbl = "\n".join(ch["sw/source/core/docnode/ndtbl.cxx"][2])
        self.assertIn("if (IsInWriterfilterImport() && bSamePrefix && nCount <= rCache.nCount + 1)", tbl)
        self.assertIn("rCache = TableNameCache();", tbl)  # the full scan rebuilds
        self.assertIn("maTableNameCache.bValid = false;", "\n".join(ch["sw/source/core/doc/docchart.cxx"][1]))

    def test_condformat_row_results_cache(self):
        name = "hst-calc-condformat-row-results-cache.patch"
        series = [n for n in (PATCHES / "series").read_text(encoding="utf-8").split() if not n.startswith("#")]
        self.assertGreater(series.index(name), series.index(NAMES[2]))  # builds on the compiled RPN copies
        ch = changes(name)
        cond = "\n".join(ch["sc/source/core/data/conditio.cxx"][2])
        self.assertIn("static bool lcl_IsColumnIndependentCode", cond)
        for opcode in ("ocRow", "ocColumn", "ocOffset", "ocIndirect", "ocName", "ocRandom", "ocGetActTime"):
            self.assertIn("case %s:" % opcode, cond)
        self.assertIn("IsRecalcModeAlways()", cond)
        self.assertIn("if (t->GetSingleRef()->IsColRel())", cond)
        # the per-row results go with the compiled copy
        self.assertEqual(cond.count("mpRelCode1.reset(); mnColumnFree1 = -1; maRowResults1.clear();"),
                         cond.count("mpRelCode1.reset();"))
        self.assertIn("ScDocument::CondRowCacheScope aCondRowCache(", "\n".join(ch["sc/source/core/data/table1.cxx"][1]))
        self.assertIn("testCondFormatRowResultsInRowHeightPass", "\n".join(ch["sc/qa/unit/ucalc_condformat.cxx"][1]))


if __name__ == "__main__":
    unittest.main()
