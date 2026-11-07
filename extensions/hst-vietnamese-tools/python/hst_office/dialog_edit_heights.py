# SPDX-License-Identifier: AGPL-3.0-only
"""One-line edits of a dialogs.Dialog as high as the platform draws them, within the room below them.

A fixed AppFont height is not enough everywhere: macOS draws a native edit box with a fixed 29 px frame whose text area
starts 6 px below the top (vcl/osx salnativewidgets), so a 12-unit edit (about 22 px) pinned the text to the top border
and cut the descenders of g/y; the gen backend (20 px) cut the hook of Ủ. The peer's preferred height
(Edit::CalcMinimumSize) is the text height plus borders, or the native frame when that is higher. Edits that are
already high enough keep their layout height.
"""


def room_below(dialog, name):
    """Map AppFont units from the top of `name` to the top of the nearest control below it that it overlaps
    horizontally (the dialog bottom when there is none). Overlay lists don't count: they are drawn over the fields."""
    model = dialog.model.getByName(name)
    room = dialog.model.Height - model.PositionY
    for other in dialog.model.ElementNames:
        below = dialog.model.getByName(other)
        if (other != name and other not in dialog._overlays and below.PositionY > model.PositionY
                and below.PositionX < model.PositionX + model.Width and model.PositionX < below.PositionX + below.Width):
            room = min(room, below.PositionY - model.PositionY)
    return room


def fit_edits(dialog):
    """Grow every single-line edit of `dialog` (its peer exists) to its preferred height, capped by room_below."""
    from com.sun.star.awt import Size
    from com.sun.star.util.MeasureUnit import APPFONT
    peer = dialog.dialog.getPeer()
    for name in dialog._single_lines:
        model = dialog.model.getByName(name)
        try:
            pixels = dialog.dialog.getControl(name).getPreferredSize().Height
            need = peer.convertSizeToLogic(Size(0, pixels), APPFONT).Height
            while peer.convertSizeToPixel(Size(0, need), APPFONT).Height < pixels:
                need += 1
        except Exception:  # noqa: BLE001 - no size information: keep the layout height
            continue
        if need > model.Height:
            model.Height = max(model.Height, min(need, room_below(dialog, name)))
