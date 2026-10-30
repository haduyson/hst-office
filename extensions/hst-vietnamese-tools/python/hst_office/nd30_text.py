# SPDX-License-Identifier: AGPL-3.0-only
"""Direct paragraph/character formatting helpers shared by the ND30 Writer renderer (uno objects passed in)."""
FONT = "Times New Roman"
ADJUST = {"left": 0, "right": 1, "justify": 2, "center": 3}  # com.sun.star.style.ParagraphAdjust
NO_LINE = 32767  # com.sun.star.table.BorderLineStyle.NONE
SOLID = 0
PARAGRAPH_BREAK = 0  # com.sun.star.text.ControlCharacter


def mm(value):
    return int(round(float(value) * 100))


def pt_to_mm100(points):
    return int(round(float(points) * 35.28))


def border(width_pt=0.0):
    import uno
    line = uno.createUnoStruct("com.sun.star.table.BorderLine2")
    if width_pt:
        line.LineStyle, line.LineWidth, line.OuterLineWidth, line.Color = SOLID, pt_to_mm100(width_pt), pt_to_mm100(width_pt), 0
    else:
        line.LineStyle = NO_LINE
    return line


def format_paragraph(cur, block, cell_mm, bottom_rule=False):
    """Set every paragraph attribute explicitly: new paragraphs inherit the previous one's attributes."""
    import uno
    cur.ParaAdjust = ADJUST[block.get("align", "left")]
    cur.ParaFirstLineIndent = mm(block.get("indent_first_mm", 0))
    cur.ParaTopMargin = pt_to_mm100(block.get("spacing_before_pt", 0))
    cur.ParaBottomMargin = pt_to_mm100(block.get("spacing_after_pt", 0))
    side = mm(block.get("indent_left_mm", 0))
    if bottom_rule:
        side = max(0, mm((cell_mm - block["rule_mm"]) / 2.0))
    cur.ParaLeftMargin, cur.ParaRightMargin = side, side if bottom_rule else 0
    spacing = uno.createUnoStruct("com.sun.star.style.LineSpacing")
    spacing.Mode, spacing.Height = 1, int(round(block.get("line_spacing", 1.0) * 100))  # PROP, percent
    cur.ParaLineSpacing = spacing
    cur.BottomBorder = border(0.75) if bottom_rule else border()
    cur.ParaKeepTogether = False


def format_run(cur, run):
    import uno
    cur.CharFontName = FONT
    cur.CharHeight = float(run["size"])
    cur.CharWeight = 150.0 if run["bold"] else 100.0
    cur.CharPosture = uno.Enum("com.sun.star.awt.FontSlant", "ITALIC" if run["italic"] else "NONE")
    cur.CharColor = 0
