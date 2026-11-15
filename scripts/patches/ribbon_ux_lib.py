# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of the ribbon UX rework generators (scripts/patches/generate-ribbon-ux-*.py): the XML helpers
(ribbon_ux_lib_core.py) and the suppression and .po helpers (ribbon_ux_lib_files.py) under one name."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ribbon_ux_lib_core import *  # noqa: E402,F401,F403
from ribbon_ux_lib_core import RibbonUxError  # noqa: E402,F401
from ribbon_ux_lib_edit import *  # noqa: E402,F401,F403
from ribbon_ux_lib_files import *  # noqa: E402,F401,F403
