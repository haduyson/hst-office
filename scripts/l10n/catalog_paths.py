# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve the Vietnamese resources used by a prepared tree or Linux installation."""
from pathlib import Path
import xml.etree.ElementTree as ET


def vi_po_dir(tree):
    tree = Path(tree)
    composed = tree / "hst/l10n/translations/source/vi"
    return composed if composed.is_dir() else tree / "translations/source/vi"


def ui_mo_path(instdir, ui):
    with open(ui, "rb") as handle:
        interface = next(ET.iterparse(handle, events=("start",)))[1]
    domain = interface.attrib["domain"]
    return Path(instdir) / "program/resource/vi/LC_MESSAGES" / (domain + ".mo")


def active_mos(directory):
    """Include every domain the UI can use, with its HST replacement where installed."""
    files = sorted(Path(directory).glob("*.mo"))
    names = {p.name for p in files}
    return [p for p in files if "hst-" + p.name not in names]
