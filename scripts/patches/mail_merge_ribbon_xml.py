# SPDX-License-Identifier: AGPL-3.0-only
"""XML pieces of the Writer "Gửi thư" (Mailings) tab groups for generate-mail-merge-ribbon.py: notebookbar toolboxes,
grids and their captions in the indentation and property order of the existing Tabbed notebookbar.ui."""
from xml.sax.saxutils import escape

PROTOCOL = "org.hst.office.mailmerge:"
GRID_INDENT = " " * 22  # a group grid inside pmhbMailings Tab


def _lines(text, indent):
    return "".join(indent + line + "\n" if line else "\n" for line in text.strip("\n").split("\n"))


def button(button_id, command, label, icon="", tooltip="", menu=False):
    """One GtkToolButton (HST command, translatable label with context TabbedWriter|<id>); `menu`: a
    GtkMenuToolButton, whose ▾ menu comes from the controllers of the extension's Controller.xcu."""
    props = ['<property name="visible">True</property>', '<property name="can-focus">False</property>',
             '<property name="label" translatable="yes" context="TabbedWriter|%s">%s</property>' % (button_id, escape(label))]
    if tooltip:
        props.append('<property name="tooltip-text" translatable="yes" context="TabbedWriter|%sTip">%s</property>'
                     % (button_id, escape(tooltip)))
    props.append('<property name="action-name">%s%s</property>' % (PROTOCOL, command))
    if icon:
        props.append('<property name="icon-name">%s</property>' % icon)
    body = "\n".join("  " + p for p in props)
    return ('<child>\n  <object class="%s" id="%s">\n%s\n  </object>\n  <packing>\n'
            '    <property name="expand">False</property>\n    <property name="homogeneous">False</property>\n'
            '  </packing>\n</child>' % ("GtkMenuToolButton" if menu else "GtkToolButton", button_id, body))


def toolbox(box_id, buttons, style, big=False):
    """A sfxlo-NotebookbarToolBox; `big`: the tall buttons spanning both rows (icon size 3)."""
    head = ['<property name="visible">True</property>', '<property name="can-focus">False</property>']
    if big:
        head += ['<property name="valign">center</property>', '<property name="vexpand">True</property>']
    head += ['<property name="toolbar-style">%s</property>' % style, '<property name="show-arrow">False</property>']
    if big:
        head.append('<property name="icon_size">3</property>')
    children = "\n".join(_lines(b, "  ").rstrip("\n") for b in buttons)
    return ('<object class="sfxlo-NotebookbarToolBox" id="%s">\n%s\n%s\n</object>'
            % (box_id, "\n".join("  " + h for h in head), children))


def cell(content, left, top, height=1, width=1):
    pack = ['<property name="left-attach">%d</property>' % left, '<property name="top-attach">%d</property>' % top]
    if height > 1:
        pack.append('<property name="height">%d</property>' % height)
    if width > 1:
        pack.append('<property name="width">%d</property>' % width)
    return '<child>\n%s  <packing>\n%s\n  </packing>\n</child>' % (_lines(content, "  "), "\n".join("    " + p for p in pack))


def caption(label_id, context, text):
    return ('<object class="GtkLabel" id="%s">\n  <property name="visible">True</property>\n'
            '  <property name="can-focus">False</property>\n  <property name="valign">end</property>\n'
            '  <property name="vexpand">True</property>\n'
            '  <property name="label" translatable="yes" context="TabbedWriter|%s">%s</property>\n'
            '  <attributes>\n    <attribute name="style" value="normal"/>\n    <attribute name="scale" value="0.9"/>\n'
            '  </attributes>\n</object>' % (label_id, context, escape(text)))


SEPARATOR = ('<object class="GtkSeparator">\n  <property name="visible">True</property>\n'
             '  <property name="can-focus">False</property>\n  <property name="orientation">vertical</property>\n</object>')


def group(grid_id, label_id, context, text, cells, columns, position):
    """A group grid: its cells, the caption across `columns` in row 2 and the separator after it."""
    children = list(cells) + [cell(caption(label_id, context, text), 0, 2, width=columns),
                              cell(SEPARATOR, columns, 0, height=3)]
    body = "\n".join(_lines(c, "  ").rstrip("\n") for c in children)
    grid = ('<object class="GtkGrid" id="%s">\n  <property name="visible">True</property>\n'
            '  <property name="can-focus">False</property>\n  <property name="margin-start">4</property>\n'
            '  <property name="margin-end">2</property>\n  <property name="margin-top">6</property>\n'
            '  <property name="margin-bottom">6</property>\n  <property name="row-spacing">3</property>\n'
            '  <property name="column-spacing">3</property>\n%s\n  <accessibility>\n'
            '    <relation type="labelled-by" target="%s"/>\n  </accessibility>\n</object>' % (grid_id, body, label_id))
    child = ('<child>\n%s  <packing>\n    <property name="expand">False</property>\n'
             '    <property name="fill">True</property>\n    <property name="position">%d</property>\n'
             '  </packing>\n</child>' % (_lines(grid, "  "), position))
    return _lines(child, GRID_INDENT)
