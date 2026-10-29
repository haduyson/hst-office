# SPDX-License-Identifier: AGPL-3.0-only
"""UNO component entry point registered in META-INF/manifest.xml (application/vnd.sun.star.uno-component;type=Python)."""
import os
import sys

# The office's Python loader does not add this extension's python/ directory to sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import unohelper  # noqa: E402

from hst_office.dispatch import IMPLEMENTATION_NAME, Handler  # noqa: E402

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Handler, IMPLEMENTATION_NAME, ("com.sun.star.frame.ProtocolHandler",))
