# SPDX-License-Identifier: AGPL-3.0-only
"""The layout builder shared with the wizard: the extension's pure-logic modules, imported from the source tree."""
import sys

from .odf import BASE

sys.path.insert(0, str(BASE / "extensions/hst-vietnamese-tools/python"))
from hst_office.nd30 import get_type, rules_for  # noqa: E402,F401
from hst_office.nd30_layout import build_layout, skeleton  # noqa: E402,F401
