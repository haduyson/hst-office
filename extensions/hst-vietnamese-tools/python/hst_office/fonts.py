# SPDX-License-Identifier: AGPL-3.0-only
"""Installed-font lookup used to warn when a required font (ND30: Times New Roman) is missing."""


def installed_font_names(ctx):
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    device = toolkit.createScreenCompatibleDevice(1, 1)
    return {d.Name.lower() for d in device.getFontDescriptors()}


def is_font_missing(ctx, name):
    """True only when the font list could be read and does not contain `name` (unknown state is not a warning)."""
    try:
        return name.lower() not in installed_font_names(ctx)
    except Exception:  # noqa: BLE001 - font enumeration is advisory
        return False
