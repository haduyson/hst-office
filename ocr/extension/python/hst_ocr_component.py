# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""UNO component of the HST OCR extension (META-INF/manifest.xml). Imports the handler only when first used."""
import importlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:  # the office's Python loader does not add the extension's python/ folder
    sys.path.insert(0, _HERE)

import unohelper  # noqa: E402

IMPLEMENTATION = "vn.hasontech.hst.ocr.DispatchProvider"  # = hst_ocr_uno.handler.IMPLEMENTATION


def _create(ctx, *args):
    return importlib.import_module("hst_ocr_uno.handler").Handler(ctx, *args)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(_create, IMPLEMENTATION, ("com.sun.star.frame.ProtocolHandler",))
