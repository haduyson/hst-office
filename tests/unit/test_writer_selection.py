# SPDX-License-Identifier: AGPL-3.0-only
"""Writer selection probing (writer_selection, nd30_insertion) and the commands that use it, on fakes of the office's
objects (writer_selection_fakes) whose view cursor throws from its text methods like the real one."""
import unittest

import _paths  # noqa: F401
from hst_office import encoding_writer, nd30_insertion, writer_selection as ws
from writer_selection_fakes import Controller, Doc, Obj, Range, Ranges, Table, Text


def point(doc, controller):
    return nd30_insertion.insertion_point(doc, controller)


class SelectionKinds(unittest.TestCase):
    def test_kinds_from_the_selection_service(self):
        self.assertEqual(ws.selection(Controller(Ranges()))[0], ws.TEXT)
        self.assertEqual(ws.selection(Controller(Obj(("com.sun.star.text.TextTableCursor",))))[0], ws.CELLS)
        for other in (Obj(("com.sun.star.text.TextGraphicObject",)), Obj(("com.sun.star.text.TextFrame",)),
                      Obj(("com.sun.star.drawing.ShapeCollection",)), None, RuntimeError("no view")):
            self.assertEqual(ws.selection(Controller(other))[0], ws.OBJECT, other)

    def test_single_text_range(self):
        body = Obj()
        rng = Range(body, "12")
        self.assertEqual(ws.single_text_range(Controller(Ranges(rng))), (rng, None))
        self.assertEqual(ws.single_text_range(Controller(Ranges(rng, rng)))[1], "multiple-selections")
        shapes = Obj(("com.sun.star.drawing.ShapeCollection",))  # has getCount too, but is no text
        self.assertEqual(ws.single_text_range(Controller(shapes))[1], "unsupported-selection")
        self.assertEqual(ws.single_text_range(Controller(None))[1], "unsupported-selection")

    def test_protected_follows_parent_sections(self):
        outer = Obj(IsProtected=True, ParentSection=None)
        inner = Obj(IsProtected=False, ParentSection=outer)
        self.assertTrue(ws.protected(Obj(TextSection=inner)))
        self.assertFalse(ws.protected(Obj(TextSection=Obj(IsProtected=False, ParentSection=None))))
        self.assertFalse(ws.protected(Obj()))


class Nd30InsertionPoint(unittest.TestCase):
    def test_cursor_in_body_text(self):
        doc = Doc()
        p = point(doc, Controller(Ranges(Range(doc.body))))
        self.assertEqual((p["reasons"], p["table"]), ([], None))

    def test_objects_and_comments_are_refused_without_raising(self):
        """The error report: getText() of the view cursor threw 'no text selection' into the dispatcher."""
        for sel in (Obj(("com.sun.star.text.TextGraphicObject",)), Obj(("com.sun.star.text.TextFrame",)),
                    Obj(("com.sun.star.text.TextEmbeddedObject",)), Obj(("com.sun.star.drawing.ShapeCollection",)), None):
            self.assertEqual(point(Doc(), Controller(sel))["reasons"], ["not-text-cursor"], sel)
        self.assertEqual(point(Doc(True), Controller(None))["reasons"], ["read-only", "not-text-cursor"])

    def test_cursor_or_cells_in_a_body_table_go_after_the_table(self):
        doc = Doc()
        table = Table(doc.body)
        cell = table.cell
        p = point(doc, Controller(Ranges(Range(cell)), TextTable=table))
        self.assertEqual((p["reasons"], p["table"]), ([], table))
        p = point(doc, Controller(Obj(("com.sun.star.text.TextTableCursor",)), TextTable=table))
        self.assertEqual((p["reasons"], p["table"]), ([], table))

    def test_nested_table_uses_the_outermost(self):
        doc = Doc()
        outer = Table(doc.body)
        inner = Table(outer.cell)
        self.assertIs(point(doc, Controller(Ranges(Range(inner.cell)), TextTable=inner))["table"], outer)

    def test_table_in_a_frame_or_header_is_not_body_text(self):
        doc = Doc()
        table = Table(Text())  # held by a frame's text
        self.assertEqual(point(doc, Controller(Ranges(Range(table.cell)), TextTable=table))["reasons"], ["not-body-text"])

    def test_frame_header_footnote_text_is_not_body_text(self):
        self.assertEqual(point(Doc(), Controller(Ranges(Range(Obj()))))["reasons"], ["not-body-text"])

    def test_selected_text_is_never_replaced(self):
        doc = Doc()
        self.assertEqual(point(doc, Controller(Ranges(Range(doc.body, "abc"))))["reasons"], ["selection"])
        self.assertEqual(point(doc, Controller(Ranges(Range(doc.body), Range(doc.body))))["reasons"], ["selection"])

    def test_protected_section_and_protected_table(self):
        doc = Doc()
        locked = Obj(IsProtected=True, ParentSection=None)
        self.assertEqual(point(doc, Controller(Ranges(Range(doc.body, TextSection=locked))))["reasons"], ["protected-cursor"])
        table = Table(doc.body, section=locked)
        self.assertEqual(point(doc, Controller(Ranges(Range(table.cell)), TextTable=table))["reasons"], ["protected-cursor"])


class EncodingSelection(unittest.TestCase):
    def test_check_selection_from_the_controller(self):
        doc = Doc()
        doc.RecordChanges = False
        doc.getRedlines = lambda: type("Redlines", (), {"hasElements": lambda _self: False})()
        rng = Range(doc.body, "abc")
        self.assertEqual(encoding_writer.check_selection(doc, Controller(Ranges(rng))), (rng, []))
        self.assertEqual(encoding_writer.check_selection(doc, Controller(Obj(("com.sun.star.text.TextFrame",))))[1],
                         ["unsupported-selection"])
        self.assertEqual(encoding_writer.check_selection(doc, Controller(Ranges(Range(doc.body))))[1], ["no-selection"])


if __name__ == "__main__":
    unittest.main()
