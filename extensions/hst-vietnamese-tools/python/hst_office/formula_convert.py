# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: turn MathType equations (Equation Editor 3.x, MathType 4-7) into editable Math formulas, in Writer,
Sheets, Slides and Draw, one object or all of them as one undo step: the object's OLE data is read back from the object
(storeToEntry), a new Math object takes its place and reads it with com.sun.star.comp.Math.MathTypeFilter (MTEF 5
needs hst-math-constructs-mathtype5.patch); if that import fails the original equation stays untouched.
In Writer a formula anchored as a character sits on the text baseline, as Writer aligns Math objects (Word's run
position shift carried by the OLE picture is dropped). Elsewhere the formula keeps the picture's top left."""
from . import formula_ole

FILTER = "com.sun.star.comp.Math.MathTypeFilter"
OLE_SHAPE = "com.sun.star.drawing.OLE2Shape"
CONTENT = 1  # com.sun.star.embed.Aspects.MSOLE_CONTENT
LOADED = 0  # com.sun.star.embed.EmbedStates.LOADED
AS_CHARACTER = 1  # com.sun.star.text.TextContentAnchorType.AS_CHARACTER
NONE = 0  # com.sun.star.text.VertOrientation.NONE
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
    from com.sun.star.beans import PropertyValue
    stream = ctx.ServiceManager.createInstanceWithContext("com.sun.star.io.SequenceInputStream", ctx)
    stream.initialize((uno.ByteSequence(data),))
    importer = ctx.ServiceManager.createInstanceWithContext(FILTER, ctx)
    importer.setTargetDocument(model)
    value = PropertyValue()
    value.Name, value.Value = "InputStream", stream
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
    size = new.EmbeddedObject.getVisualAreaSize(CONTENT)
    new.Size = size
    for name in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin"):
        new.setPropertyValue(name, 0)
    if new.AnchorType == AS_CHARACTER:  # formula baseline on the text baseline
        new.VertOrient = NONE
        new.VertOrientPosition = -int(model.BaseLine)
    old.dispose()
    return True


def shape_pages(doc):
    """Draw pages holding the shapes: one per sheet (Sheets), slides and masters (Slides, Draw)."""
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        sheets = doc.getSheets()
        return [sheets.getByIndex(i).getDrawPage() for i in range(sheets.getCount())]
    pages = []
    for owner in (doc.getDrawPages(), doc.getMasterPages()):
        pages += [owner.getByIndex(i) for i in range(owner.getCount())]
    return pages


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
    new.Size = new.EmbeddedObject.getVisualAreaSize(CONTENT)
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
    """Let the office finish the layout it deferred while the views were locked (Writer resizes each new formula
    then), so those changes belong to the same undo step."""
    try:
        ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx).processEventsToIdle()
    except Exception:  # noqa: BLE001 - an office without it lays out later, as usual
        pass


def convert_all(ctx, doc, undo_title, only=None):
    """(converted, kept) for all MathType equations, or for the objects in `only`; one undo step. The views are not
    redrawn until the end, and a progress bar counts the objects."""
    from .undo import undo_step
    done = kept = 0
    found = [(c, o) for c, o in candidates(doc) if only is None or o in only]
    indicator = _progress(doc, undo_title, len(found)) if len(found) > 5 else None
    try:
        with undo_step(doc, undo_title):  # the layout after unlocking resizes the objects: inside the same step
            doc.lockControllers()
            try:
                for index, (container, obj) in enumerate(found):
                    result = convert_one(ctx, doc, container, obj)
                    if result is not None:
                        done, kept = (done + 1, kept) if result else (done, kept + 1)
                    if indicator is not None:
                        indicator.setValue(index + 1)
            finally:
                doc.unlockControllers()
            _settle(ctx)
    finally:
        if indicator is not None:
            indicator.end()
    return done, kept
