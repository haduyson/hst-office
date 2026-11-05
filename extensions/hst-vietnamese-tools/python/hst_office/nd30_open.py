# SPDX-License-Identifier: AGPL-3.0-only
"""Open a register of the catalog as a new workbook: it is a spreadsheet template, not something to insert in a text."""
import os

import uno
from com.sun.star.beans import PropertyValue

from .data_files import EXT_ROOT


def register_path(type_id):
    return os.path.join(EXT_ROOT, "template", "hst-van-thu", type_id + ".ots")


def open_register(ctx, type_id):
    path = register_path(type_id)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    template = PropertyValue()
    template.Name, template.Value = "AsTemplate", True
    return desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, (template,))
