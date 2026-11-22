# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""One-line edits of a dialogs.Dialog as high as the platform draws them, within the room below them.

A fixed AppFont height is not enough everywhere: macOS draws a native edit box with a fixed 29 px frame whose text area
starts 6 px below the top (vcl/osx salnativewidgets), so a 12-unit edit (about 22 px) pinned the text to the top border
and cut the descenders of g/y; the gen backend (20 px) cut the hook of Ủ. The peer's preferred height
(Edit::CalcMinimumSize) is the text height plus borders, or the native frame when that is higher. Edits that are
already high enough keep their layout height.
"""


def pixels_to_units(peer, pixels, horizontal=False):
    """The fewest Map AppFont units that `peer` draws at least `pixels` pixels high (or wide)."""
    from com.sun.star.awt import Size
    from com.sun.star.util.MeasureUnit import APPFONT

    def size(value):
        return Size(value, 0) if horizontal else Size(0, value)

    def along(result):
        return result.Width if horizontal else result.Height
    need = along(peer.convertSizeToLogic(size(pixels), APPFONT))
    for _ in range(64):  # the logic size rounds down by at most a unit or two; bounded against a broken conversion
        if along(peer.convertSizeToPixel(size(need), APPFONT)) >= pixels:
            break
        need += 1
    return need


def room_below(dialog, name):
    """Map AppFont units from the top of `name` to the top of the nearest control below it that it overlaps
    horizontally (the dialog bottom when there is none)."""
    model = dialog.model.getByName(name)
    room = dialog.model.Height - model.PositionY
    for other in dialog.model.ElementNames:
        below = dialog.model.getByName(other)
        if (other != name and below.PositionY > model.PositionY
                and below.PositionX < model.PositionX + model.Width and model.PositionX < below.PositionX + below.Width):
            room = min(room, below.PositionY - model.PositionY)
    return room


def fit_edits(dialog):
    """Grow every single-line edit of `dialog` (its peer exists) to its preferred height, capped by room_below."""
    peer = dialog.dialog.getPeer()
    for name in dialog._single_lines:
        model = dialog.model.getByName(name)
        try:
            need = pixels_to_units(peer, dialog.dialog.getControl(name).getPreferredSize().Height)
        except Exception:  # noqa: BLE001 - no size information: keep the layout height
            continue
        if need > model.Height:
            model.Height = max(model.Height, min(need, room_below(dialog, name)))
