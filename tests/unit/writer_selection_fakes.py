# SPDX-License-Identifier: AGPL-3.0-only
"""Fakes of Writer's selection objects for tests/unit/test_writer_selection.py. The view cursor throws "no text
selection" from its text methods, as SwXTextViewCursor does whenever cells, a picture, frame, shape or comment are
selected: code under test may only read its properties."""


class NoTextSelection(Exception):
    pass


class Obj:
    def __init__(self, services=(), **props):
        self.services, self.props = set(services), props

    def supportsService(self, name):
        return name in self.services

    def getPropertyValue(self, name):
        if name not in self.props:
            raise KeyError(name)
        return self.props[name]

    def __getattr__(self, name):
        if name in ("services", "props"):
            raise AttributeError(name)
        return self.props.get(name)


class Range(Obj):
    def __init__(self, text, string="", **props):
        super().__init__(**props)
        self.text, self.string = text, string

    def getText(self):
        return self.text

    def getString(self):
        return self.string

    def getStart(self):
        return self


class ViewCursor(Obj):
    """Only properties work, like the real one outside a text selection."""
    def getText(self):
        raise NoTextSelection("no text selection")

    getStart = getString = gotoEnd = getText


class Ranges(Obj):
    def __init__(self, *ranges):
        super().__init__(services=("com.sun.star.text.TextRanges",))
        self.ranges = ranges

    def getCount(self):
        return len(self.ranges)

    def getByIndex(self, index):
        return self.ranges[index]


class Controller:
    def __init__(self, selection, **cursor_props):
        self.selection, self.cursor = selection, ViewCursor(**cursor_props)

    def getSelection(self):
        if isinstance(self.selection, Exception):
            raise self.selection
        return self.selection

    def getViewCursor(self):
        return self.cursor


class Text(Obj):
    """A text (body, frame, header ... or a cell): enumerates its paragraphs and tables."""
    def __init__(self, services=()):
        super().__init__(services=services)
        self.elements = [Obj(("com.sun.star.text.Paragraph",))]

    def createEnumeration(self):
        items = iter(list(self.elements))
        box = {"next": next(items, None)}

        class Enumeration:
            def hasMoreElements(self):
                return box["next"] is not None

            def nextElement(self):
                value, box["next"] = box["next"], next(items, None)
                return value
        return Enumeration()


class Doc:
    def __init__(self, readonly=False):
        self.body, self.readonly = Text(), readonly

    def isReadonly(self):
        return self.readonly

    def getText(self):
        return self.body


class Cell(Text):
    """A table cell as its text (SwXCell)."""
    def __init__(self, table):
        super().__init__(services=("com.sun.star.text.CellProperties",))
        self.table = table

    def getStart(self):
        return Range(self, TextSection=self.table.section)


class Table(Obj):
    """A table placed in `holder` (a Text); its one cell is `cell`."""
    count = 0

    def __init__(self, holder, section=None):
        super().__init__(services=("com.sun.star.text.TextTable",))
        Table.count += 1
        self.name, self.section = "Table%d" % Table.count, section
        self.cell = Cell(self)
        holder.elements.append(self)

    def getName(self):
        return self.name

    def getCellNames(self):
        return ("A1",)

    def getCellByName(self, _name):
        return self.cell
