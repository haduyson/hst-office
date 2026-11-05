# SPDX-License-Identifier: AGPL-3.0-only
"""Direct paragraph/character formatting helpers shared by the ND30 Writer renderer (uno objects passed in)."""
FONT = "Times New Roman"
ADJUST = {"left": 0, "right": 1, "justify": 2, "center": 3}  # com.sun.star.style.ParagraphAdjust
NO_LINE = 32767  # com.sun.star.table.BorderLineStyle.NONE
SOLID = 0
PARAGRAPH_BREAK = 0  # com.sun.star.text.ControlCharacter
LINE_PROP, LINE_FIX = 0, 3  # com.sun.star.style.LineSpacingMode
RULE_PT = 0.75


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


def line_spacing(block):
    """Proportional (1.15 lines = 115%) or, for profiles that fix it, exact in points."""
    import uno
    spacing = uno.createUnoStruct("com.sun.star.style.LineSpacing")
    if block.get("line_exact_pt"):
        spacing.Mode, spacing.Height = LINE_FIX, pt_to_mm100(block["line_exact_pt"])
    else:
        spacing.Mode, spacing.Height = LINE_PROP, int(round(block.get("line_spacing", 1.0) * 100))
    return spacing


def format_paragraph(cur, block, cell_mm, bottom_rule=False):
    """Set every paragraph attribute explicitly: new paragraphs inherit the previous one's attributes."""
    cur.ParaAdjust = ADJUST[block.get("align", "left")]
    cur.ParaFirstLineIndent = mm(block.get("indent_first_mm", 0))
    cur.ParaTopMargin = pt_to_mm100(block.get("spacing_before_pt", 0))
    cur.ParaBottomMargin = pt_to_mm100(block.get("spacing_after_pt", 0))
    side = mm(block.get("indent_left_mm", 0))
    if bottom_rule:
        side = max(0, mm((cell_mm - block["rule_mm"]) / 2.0))
    cur.ParaLeftMargin, cur.ParaRightMargin = side, side if bottom_rule else 0
    cur.ParaLineSpacing = line_spacing(block)
    cur.BottomBorder = border(RULE_PT) if bottom_rule else border()
    cur.TopBorder = border(RULE_PT) if block.get("top_rule") else border()
    cur.TopBorderDistance = mm(1) if block.get("top_rule") else 0
    cur.ParaKeepTogether = bool(block.get("keep_with_next"))


def format_run(cur, run):
    import uno
    cur.CharFontName = FONT
    cur.CharHeight = float(run["size"])
    cur.CharWeight = 150.0 if run["bold"] else 100.0
    cur.CharPosture = uno.Enum("com.sun.star.awt.FontSlant", "ITALIC" if run["italic"] else "NONE")
    cur.CharUnderline = 1 if run.get("underline") else 0
    cur.CharColor = 0
