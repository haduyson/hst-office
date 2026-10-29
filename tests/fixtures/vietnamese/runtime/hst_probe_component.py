# SPDX-License-Identifier: AGPL-3.0-only
"""Test-only UNO component (never shipped): exposes hst_probe_macro functions through XJob so the runtime
check can execute the installed extension's code inside the office process."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import unohelper  # noqa: E402
from com.sun.star.task import XJob  # noqa: E402

import hst_probe_macro  # noqa: E402


class Probe(unohelper.Base, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self, arguments):
        values = {a.Name: a.Value for a in arguments}
        return getattr(hst_probe_macro, values["name"])(*values["args"])


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Probe, "org.hst.test.Probe", ("org.hst.test.Probe",))
