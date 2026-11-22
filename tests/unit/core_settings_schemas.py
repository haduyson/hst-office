# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The HST settings schemas (org.hasontech.hstoffice.*) as the core configuration defines them.

They are added to officecfg by patches/libreoffice/hst-extension-settings-core.patch (packed into main.xcd); the bundled
extension no longer ships them. Tests read them from the patch, no LibreOffice tree needed."""
import os
import re
import xml.etree.ElementTree as ET

import _paths

PATCH = os.path.join(_paths.ROOT, "patches", "libreoffice", "hst-extension-settings-core.patch")
SCHEMA_DIR = "officecfg/registry/schema/org/hasontech/hstoffice/"
OOR = "{http://openoffice.org/2001/registry}"


def _patch():
    with open(PATCH, encoding="utf-8") as handle:
        return handle.read()


def components():
    """Names of the components the patch adds, e.g. ["Banners", ..., "Welcome"]."""
    return sorted(re.findall(r"^\+\+\+ b/" + re.escape(SCHEMA_DIR) + r"(\w+)\.xcs$", _patch(), re.M))


def schema_text(component):
    """The full text of officecfg/registry/schema/org/hasontech/hstoffice/<component>.xcs as the patch creates it."""
    marker = "+++ b/" + SCHEMA_DIR + component + ".xcs\n"
    text = _patch()
    start = text.index(marker) + len(marker)
    lines = []
    for line in text[start:].splitlines():
        if line.startswith("@@"):
            continue
        if not line.startswith("+"):
            break
        lines.append(line[1:])
    return "\n".join(lines) + "\n"


def schema_root(component):
    """The parsed <oor:component-schema> element (the DOCTYPE is dropped: ElementTree does not load DTDs)."""
    return ET.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", schema_text(component)).encode("utf-8"))
