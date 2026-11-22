# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Radio buttons, check boxes and spin fields of a dialogs.Dialog as large as the platform draws them.

Dialog layouts are fixed Map AppFont units, which follow the UI font, but a GTK3 theme draws the radio/check indicator
and the spin buttons in fixed pixels (vcl/unx/gtk3/salnativewidgets-gtk.cxx). With a small UI font, GDK_DPI_SCALE
below 1 or a theme with a large indicator, a 10-unit radio row is lower than its indicator and the rows 12 units apart
overlap; GTK3 puts both spin buttons side by side, so a 40-unit number field has no room left for its digits.

fit_choice_rows grows each radio button or check box to the peer's preferred height, first into the free room below it,
then by moving every control under it (and the dialog bottom) down by the rest. fit_spin_widths widens each spin field
to its preferred width and moves the controls right of it on the same row. A control that already fits is left alone,
so on Windows, macOS and the default GTK themes the layout does not change at all.
"""
from .dialog_edit_heights import pixels_to_units, room_below

CHOICES = ("com.sun.star.awt.UnoControlRadioButtonModel", "com.sun.star.awt.UnoControlCheckBoxModel")


def _peer_and_models(dialog):
    """The dialog peer and its (name, control model) pairs; None when there is no peer to measure with."""
    try:
        peer = dialog.dialog.getPeer()
        models = [(name, dialog.model.getByName(name)) for name in dialog.model.ElementNames]
    except Exception:  # noqa: BLE001 - dialog without peer or model (disposed): keep the layout
        return None, []
    return peer, models


def _preferred(dialog, name):
    """The control's preferred size in pixels, or None when the peer gives no size information."""
    try:
        return dialog.dialog.getControl(name).getPreferredSize()
    except Exception:  # noqa: BLE001 - control or peer gone: keep the layout
        return None


def fit_choice_rows(dialog):
    """Grow every radio button / check box of `dialog` (its peer exists) to its preferred height; push the rest down."""
    peer, models = _peer_and_models(dialog)
    if peer is None:
        return
    choices = [(name, model) for name, model in models
               if any(model.supportsService(service) for service in CHOICES)]
    for name, model in sorted(choices, key=lambda item: (item[1].PositionY, item[1].PositionX)):
        size = _preferred(dialog, name)
        if size is None:
            continue
        try:
            need = pixels_to_units(peer, size.Height)
        except Exception:  # noqa: BLE001 - no unit conversion: keep the layout height
            continue
        if need <= model.Height:
            continue
        old_bottom = model.PositionY + model.Height  # the control grows downwards, its top stays
        shift = max(0, need - room_below(dialog, name))
        model.Height = need
        if shift:
            for other, below in models:
                if other != name and below.PositionY >= old_bottom:
                    below.PositionY = below.PositionY + shift
            dialog.model.Height = dialog.model.Height + shift


def fit_spin_widths(dialog):
    """Widen every spin field of `dialog` (its peer exists) to its preferred width, within the dialog's right margin,
    moving the controls right of it on the same row along."""
    peer, models = _peer_and_models(dialog)
    if peer is None or not models:
        return
    right_limit = dialog.model.Width - min(model.PositionX for _, model in models)  # the left margin, mirrored
    spins = [(name, model) for name, model in models if getattr(model, "Spin", False) is True]
    for name, field in sorted(spins, key=lambda item: (item[1].PositionX, item[1].PositionY)):
        size = _preferred(dialog, name)
        if size is None:
            continue
        try:
            need = pixels_to_units(peer, size.Width, horizontal=True)
        except Exception:  # noqa: BLE001 - no unit conversion: keep the layout width
            continue
        if need <= field.Width:
            continue
        old_right = field.PositionX + field.Width
        row = [model for other, model in models
               if other != name and model.PositionX >= old_right
               and model.PositionY < field.PositionY + field.Height and field.PositionY < model.PositionY + model.Height]
        rightmost = max([old_right] + [model.PositionX + model.Width for model in row])
        grow = min(need - field.Width, right_limit - rightmost)
        if grow <= 0:
            continue
        field.Width = field.Width + grow
        for model in row:
            model.PositionX = model.PositionX + grow


def fit_all(dialog):
    """Both fits, in the order that keeps rows aligned: rows first (they move whole rows), then the widths."""
    fit_choice_rows(dialog)
    fit_spin_widths(dialog)
