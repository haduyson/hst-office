# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST Công thức: turn MathType equations (Equation Editor 3.x, MathType 4-7) into editable Math formulas in Writer,
Sheets, Slides and Draw, one object or all as one undo step. The object's OLE data is read back (storeToEntry), a new
Math object takes its place and reads it with com.sun.star.comp.Math.MathTypeFilter (MTEF 5: HST's patch); if that
fails the equation stays. The formula keeps the scale Word shows (formula_size). In Writer a formula anchored as a
character sits on the text baseline inside the room its equation took (formula_place); elsewhere it keeps the
picture's corner."""
import time

from . import formula_ole, formula_place, formula_size

FILTER = "com.sun.star.comp.Math.MathTypeFilter"
OLE_SHAPE = "com.sun.star.drawing.OLE2Shape"
LOADED = 0  # com.sun.star.embed.EmbedStates.LOADED
PROGRESS_SECONDS = 0.5  # each progress update lets the office lay out and repaint: hundreds cost more than converting
KEEP_TEXT = ("AnchorType", "HoriOrient", "HoriOrientPosition", "HoriOrientRelation", "VertOrientRelation", "TextWrap")


def _stored(ctx, embedded):
    """The bytes the object stores, b"" when it cannot be stored."""
    try:
        storage = ctx.ServiceManager.createInstanceWithContext("com.sun.star.embed.StorageFactory", ctx).createInstance()
        embedded.storeToEntry(storage, "ole", (), ())
        stream = storage.openStreamElement("ole", 1).getInputStream()  # ElementModes.READ
        chunks = []
        while True:
            count, data = stream.readBytes(None, 65536)
            chunks.append(bytes(data.value))
            if count < 65536:
                return b"".join(chunks)
    except Exception:  # noqa: BLE001 - an object that cannot be stored is simply not converted
        return b""


def ole_data(ctx, embedded):
    """The bytes of an embedded OLE object's data, b"" when it cannot be stored. On Windows the office may have
    started the object to show it (state RUNNING), and a running object without its server refuses storeToEntry:
    it is unloaded and stored again."""
    data = _stored(ctx, embedded)
    try:
        if data or embedded.getCurrentState() == LOADED:
            return data
        embedded.changeState(LOADED)
    except Exception:  # noqa: BLE001 - an object that cannot be unloaded is not converted
        return b""
    return _stored(ctx, embedded)


def import_formula(ctx, model, data):
    """Fill a new formula's model from MathType OLE data; False when the import refuses it."""
    import uno
    stream = ctx.ServiceManager.createInstanceWithContext("com.sun.star.io.SequenceInputStream", ctx)
    stream.initialize((uno.ByteSequence(data),))
    importer = ctx.ServiceManager.createInstanceWithContext(FILTER, ctx)
    importer.setTargetDocument(model)
    value = uno.createUnoStruct("com.sun.star.beans.PropertyValue", Name="InputStream", Value=stream)
    return bool(importer.filter((value,)))


def _mathtype_data(ctx, embedded):
    data = ole_data(ctx, embedded) if embedded is not None else b""
    return data if formula_ole.is_mathtype(data) else b""


def writer_objects(doc):
    """Writer's embedded objects that are not formulas yet."""
    objects = doc.getEmbeddedObjects()
    found = (objects.getByName(name) for name in objects.getElementNames())
    return [o for o in found if not formula_ole.is_math_clsid(o.CLSID)]


def _replace_text_object(ctx, doc, old, data):
    anchor = old.getAnchor()
    new = doc.createInstance("com.sun.star.text.TextEmbeddedObject")
    new.CLSID = formula_ole.MATH
    for name in KEEP_TEXT:
        new.setPropertyValue(name, old.getPropertyValue(name))
    anchor.getText().insertTextContent(anchor, new, False)
    model = new.getEmbeddedObject()
    if not import_formula(ctx, model, data):
        new.dispose()
        return False
    formula_size.keep_word_scale(model, old)
    new.Size = formula_size.visual_size(new.EmbeddedObject)
    formula_place.fit_room(model, new, old)
    formula_place.keep_room(new, old, model.BaseLine)  # the pages do not move
    old.dispose()
    return True


def shape_pages(doc):
    """Draw pages holding the shapes: one per sheet (Sheets), slides and masters (Slides, Draw)."""
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        sheets = doc.getSheets()
        return [sheets.getByIndex(i).getDrawPage() for i in range(sheets.getCount())]
    owners = (doc.getDrawPages(), doc.getMasterPages())
    return [owner.getByIndex(i) for owner in owners for i in range(owner.getCount())]


def shape_objects(doc):
    """(page, shape) of the OLE shapes that are not formulas yet, groups included."""
    found = []

    def walk(page, container):
        for i in range(container.getCount()):
            shape = container.getByIndex(i)
            if shape.getShapeType() == "com.sun.star.drawing.GroupShape":
                walk(page, shape)
            elif shape.getShapeType() == OLE_SHAPE and not formula_ole.is_math_clsid(shape.CLSID):
                found.append((container, shape))
    for page in shape_pages(doc):
        walk(page, page)
    return found


def _replace_shape(ctx, doc, container, old, data):
    new = doc.createInstance(OLE_SHAPE)
    container.add(new)
    new.CLSID = formula_ole.MATH
    if not import_formula(ctx, new.Model, data):
        container.remove(new)
        return False
    formula_size.keep_word_scale(new.Model, old)
    new.Size = formula_size.visual_size(new.EmbeddedObject)
    new.Position = old.Position
    if old.getPropertySetInfo().hasPropertyByName("Anchor"):  # Sheets: same cell or page anchor
        new.Anchor = old.Anchor
        new.Position = old.Position
    container.remove(old)
    return True


def candidates(doc):
    """[(container or None, object)] that may be MathType equations, in document order."""
    if doc.supportsService("com.sun.star.text.TextDocument"):
        return [(None, o) for o in writer_objects(doc)]
    return shape_objects(doc)


def convert_one(ctx, doc, container, obj):
    """None if the object is not a MathType equation, else True (converted) or False (kept as it was)."""
    data = _mathtype_data(ctx, obj.EmbeddedObject)
    if not data:
        return None
    if container is None:
        return _replace_text_object(ctx, doc, obj, data)
    return _replace_shape(ctx, doc, container, obj, data)


def _progress(doc, text, count):
    """The document window's progress bar, or None (hidden documents, tests)."""
    try:
        indicator = doc.getCurrentController().getFrame().createStatusIndicator()
        indicator.start(text, count)
        return indicator
    except Exception:  # noqa: BLE001 - converting works without a progress bar
        return None


def _settle(ctx):
    """Let the office finish the layout deferred while the views were locked (it resizes the new formulas), in the
    same undo step."""
    try:
        ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx).processEventsToIdle()
    except Exception:  # noqa: BLE001 - an office without it lays out later, as usual
        pass


def convert_all(ctx, doc, undo_title, only=None):
    """(converted, kept) for all MathType equations, or for the objects in `only`; one undo step. The views are not
    redrawn until the end; a progress bar counts the objects, updated every PROGRESS_SECONDS."""
    from .undo import undo_step
    done = kept = 0
    found = [(c, o) for c, o in candidates(doc) if only is None or o in only]
    indicator = _progress(doc, undo_title, len(found)) if len(found) > 5 else None
    try:
        with undo_step(doc, undo_title):  # the layout after unlocking resizes the objects: inside the same step
            doc.lockControllers()
            shown = time.monotonic()
            try:
                for index, (container, obj) in enumerate(found):
                    result = convert_one(ctx, doc, container, obj)
                    if result is not None:
                        done, kept = (done + 1, kept) if result else (done, kept + 1)
                    if indicator is not None and time.monotonic() - shown >= PROGRESS_SECONDS:
                        indicator.setValue(index + 1)
                        shown = time.monotonic()
            finally:
                doc.unlockControllers()
            _settle(ctx)
    finally:
        if indicator is not None:
            indicator.end()
    return done, kept
