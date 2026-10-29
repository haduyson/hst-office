# SPDX-License-Identifier: AGPL-3.0-only
"""Locate and load the shared JSON data (ND30 rules, encoding maps, number formats, locales).

Inside the packaged extension the data lives in <ext>/data and <ext>/locales; in the source tree it is
read from the repository's data/vietnamese so the same files serve templates, tests and the extension.
"""
import json
import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
EXT_ROOT = os.path.dirname(os.path.dirname(PACKAGE_DIR))
REPO_ROOT = os.path.dirname(os.path.dirname(EXT_ROOT))


def _candidates(name):
    yield os.path.join(EXT_ROOT, "data", name)
    yield os.path.join(REPO_ROOT, "data", "vietnamese", name)


def load_data(name):
    """Load data/vietnamese/<name> (e.g. 'nd30.json'); raises FileNotFoundError with the searched paths."""
    tried = []
    for path in _candidates(name):
        tried.append(path)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError("HST data file %s not found in: %s" % (name, ", ".join(tried)))


def load_locale(language):
    """Return the UI strings for 'vi' or 'en'; unknown languages fall back to English."""
    code = "vi" if str(language).lower().startswith("vi") else "en"
    with open(os.path.join(EXT_ROOT, "locales", code + ".json"), encoding="utf-8") as handle:
        return json.load(handle)
