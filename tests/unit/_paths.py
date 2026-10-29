# SPDX-License-Identifier: AGPL-3.0-only
"""Make hst_office importable for plain-python unit tests (no uno needed)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "vietnamese")
