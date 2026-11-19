# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: a converted formula takes the room its MathType equation took, so the pages do not move.

Math's box is 9-19 % shorter than MathType's for the same point size; a formula sized to it shortened every line that
holds one (s037: 48 pages became 46). The formula keeps its own size and its baseline on the text baseline, and the
frame's spacing fills the rest of the equation's room: above, below and on both sides. For a Writer object anchored as
a character, the vertical position is that of the room's top (spacing included), relative to the baseline; the layout
writes it back for every orientation, so the old object's position is where its room was."""

NONE = 0  # com.sun.star.text.VertOrientation.NONE
AS_CHARACTER = "AS_CHARACTER"  # com.sun.star.text.TextContentAnchorType (a UNO enum: compared by its value)
SPACING = ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin")


def room(old):
    """(top relative to the baseline, height, width) in mm100 the equation took in its line, spacing included."""
    height = old.Size.Height + old.TopMargin + old.BottomMargin
    width = old.Size.Width + old.LeftMargin + old.RightMargin
    top = old.VertOrientPosition
    if not top and old.VertOrient != NONE:  # never laid out: bottom on the baseline
        top = -height
    return top, height, width


def spacing(old_room, size, base_line):
    """{spacing: mm100} and the room's top for a formula of size (width, height) whose baseline is base_line below its
    top, placed on the text baseline inside old_room. Where the formula is larger than the room it is not cut: the
    spacing on that side is 0 and the room grows."""
    top, height, width = old_room
    formula_top = -base_line
    upper = max(0, formula_top - top)
    lower = max(0, top + height - (formula_top + size[1]))
    side = max(0, (width - size[0]) // 2)
    return {"TopMargin": upper, "BottomMargin": lower, "LeftMargin": side, "RightMargin": side}, formula_top - upper


def keep_room(new, old, base_line):
    """Place the formula new where the equation old was: on the text baseline, with its line's room kept when it is
    anchored as a character; elsewhere without spacing, as before."""
    if getattr(new.AnchorType, "value", new.AnchorType) != AS_CHARACTER:
        for name in SPACING:
            new.setPropertyValue(name, 0)
        return
    values, top = spacing(room(old), (new.Size.Width, new.Size.Height), int(base_line))
    for name, value in values.items():
        new.setPropertyValue(name, int(value))
    new.VertOrient = NONE
    new.VertOrientPosition = int(top)
