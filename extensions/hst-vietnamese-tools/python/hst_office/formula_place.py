# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST Công thức: a converted formula takes the room its MathType equation took, so the pages do not move.

Math's box is 9-19 % shorter than MathType's for the same point size; a formula sized to it shortened every line that
holds one (s037: 48 pages became 46). The formula keeps its own size and its baseline on the text baseline, and the
frame's spacing fills the rest of the equation's room: above, below and on both sides. Where Math reaches beyond the
room above or below the baseline (an arrow's label sits higher than in MathType), the formula moves by up to 1 pt when
that keeps it inside, else it is drawn smaller to fit, by at most a quarter; beyond that the room grows.
For a Writer object anchored as a character, the vertical position is that of the room's top (spacing included),
relative to the baseline; the layout writes it back for every orientation, so the old object's position is where its
room was."""

from . import formula_size

NONE = 0  # com.sun.star.text.VertOrientation.NONE
FIT_LIMIT = 0.25  # a formula reaching beyond its room is drawn smaller, by at most this share
SHIFT_LIMIT = 35  # mm100 (1 pt): a formula that fits the room's height moves off the baseline this far, unseen
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
    if size[1] <= height:  # it fits in the room's height: moved, by at most SHIFT_LIMIT, to stay inside it
        inside = min(max(formula_top, top), top + height - size[1])
        if abs(inside - formula_top) <= SHIFT_LIMIT:
            formula_top = inside
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


def fit_scale(old_room, size, base_line):
    """The scale that brings a formula of size (width, height), base_line below its top, inside old_room above and
    below the baseline; 1.0 when it fits, or when that would take more than FIT_LIMIT off it."""
    top, height, _ = old_room
    ascent, descent = base_line, size[1] - base_line
    room_ascent, room_descent = -top, top + height
    if size[1] <= height and max(ascent - room_ascent, descent - room_descent) <= SHIFT_LIMIT:
        return 1.0  # spacing() moves it inside
    scale = 1.0
    if ascent > room_ascent > 0:
        scale = room_ascent / ascent
    if descent > max(room_descent, 0):
        scale = min(scale, max(room_descent, 0) / descent)
    return scale if 1 - FIT_LIMIT <= scale < 1 else 1.0


def fit_room(model, new, old):
    """Draw the formula of new smaller where it reaches beyond the room of old above or below the baseline (Math sets
    an arrow's label higher, and some formulas lower, than MathType); returns the scale applied, 1.0 when none."""
    if getattr(new.AnchorType, "value", new.AnchorType) != AS_CHARACTER:
        return 1.0
    scale = fit_scale(room(old), (new.Size.Width, new.Size.Height), int(model.BaseLine))
    if scale < 1:
        model.Formula = formula_size.scale_sizes(model.Formula, scale)
        new.Size = formula_size.visual_size(new.EmbeddedObject)
    return scale
