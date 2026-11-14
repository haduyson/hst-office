# SPDX-License-Identifier: AGPL-3.0-only
"""Model of the ribbon KeyTips, shared by the parity table builder and its check.

The C++ side lives in sfx2/source/notebookbar: HstKeyTipTable.hxx (general tables, `assign`), HstKeyTipOffice.hxx
(generated: the familiar suite's letters per module, tab and command, `preferred`, `prioritise`). This module reads those
tables, walks the tab pages of a notebookbar.ui in the order HstRibbonKeyTips.cxx collects its targets, and replays the
assignment, so that a letter that would lose on its tab is caught without a GUI.
"""
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from office_parity_ui import ITEM_CLASSES, command_name  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLE_HEADER = "sfx2/source/notebookbar/HstKeyTipTable.hxx"
# HST app -> (module token of the .ui path, notebookbar.ui in the source tree)
MODULES = {"writer": ("swriter", "sw/uiconfig/swriter/ui/notebookbar.ui"),
           "calc": ("scalc", "sc/uiconfig/scalc/ui/notebookbar.ui"),
           "impress": ("simpress", "sd/uiconfig/simpress/ui/notebookbar.ui"),
           "draw": ("sdraw", "sd/uiconfig/sdraw/ui/notebookbar.ui")}
MENU_BUTTONS = ("svtlo-ManagedMenuButton", "GtkMenuButton", "GtkButton")
OFFICE_MARK = "!"


def parse_table(header_text, name):
    """{id: tip} of one `inline constexpr Key NAME[] = {...};` table of a KeyTip header."""
    found = re.search(name + r"\[\]\s*=\s*\{(.*?)\n\};", header_text, re.S)
    if not found:
        raise ValueError(f"no table {name} in the KeyTip header")
    body = re.sub(r"//[^\n]*", "", found.group(1))
    return dict(re.findall(r'\{\s*"([^"]+)",\s*"([^"]*)"\s*\}', body))


def prefix_clash(a, b):
    return a.startswith(b) or b.startswith(a)


def assign(preferred):
    """Python twin of hst::keytips::assign: one tip per entry, prefix-free, free letters then Y1.., Z1.."""
    result, used = [""] * len(preferred), []

    def clashes(tip):
        return any(prefix_clash(tip, other) for other in used)

    for i, tip in enumerate(preferred):
        if tip and not clashes(tip):
            result[i] = tip
            used.append(tip)
    letters, second = "ABCDEFGHIJKLMNOPQRSTUVWX", "123456789ABCDEFGHIJKLMNOPQRSTUVWXZ"
    n_letter = n_second = 0
    first = "Y"
    for i in range(len(result)):
        while not result[i] and n_letter < len(letters):
            candidate = letters[n_letter]
            n_letter += 1
            if not clashes(candidate):
                result[i] = candidate
        while not result[i]:
            if n_second == len(second):
                n_second, first = 0, "Z"
            result[i] = first + second[n_second]
            n_second += 1
        used.append(result[i])
    return result


def prioritise(preferred):
    """Python twin of hst::keytips::prioritise: marked (familiar suite) tips win; a general tip that clashes with one
    of them is dropped, so that entry gets a free letter."""
    marked = [p[1:] for p in preferred if p.startswith(OFFICE_MARK)]
    out = []
    for tip in preferred:
        if tip.startswith(OFFICE_MARK):
            out.append(tip[1:])
        else:
            out.append("" if tip and any(prefix_clash(tip, m) for m in marked) else tip)
    return out


def _props(obj):
    return {p.get("name").replace("_", "-"): p for p in obj.findall("property")}


def _walk(obj, out, hidden):
    props = _props(obj)
    hidden = hidden or (props.get("visible") is not None and props["visible"].text == "False")
    klass, ident = obj.get("class"), obj.get("id") or ""
    if not hidden and klass in ITEM_CLASSES:
        action = props.get("action-name")
        if action is not None and action.text:
            out.append(command_name(action.text))
    elif not hidden and klass in MENU_BUTTONS:
        out.append(ident.split(":", 1)[0])  # menu buttons are looked up by their widget id
    for child in obj.findall("child"):
        for sub in child.findall("object"):
            _walk(sub, out, hidden)


def tab_pages(ui_path):
    """[(tab label id, [command or widget id, ...])] of a Tabbed notebookbar.ui, in document order."""
    root = ET.parse(ui_path).getroot()
    control = next(o for o in root.iter("object") if o.get("class") == "sfxlo-NotebookbarTabControl")
    pages, pending = [], None
    for child in control.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        if child.get("type") != "tab":
            pending = obj
            continue
        items = []
        if pending is not None:
            _walk(pending, items, False)
        pages.append((obj.get("id"), items))
        pending = None
    return pages


def preferred(office, general, module, tab, ident):
    """Python twin of hst::keytips::preferred."""
    tip = office.get(f"{module}/{tab}/{ident}")
    return OFFICE_MARK + tip if tip else general.get(ident, "")


def simulate(tree, office, general):
    """{app: {tab: [(ident, tip)]}}: the letters every ribbon item of the tree would get (all items shown)."""
    result = {}
    for app, (module, ui) in MODULES.items():
        path = os.path.join(tree, ui)
        if not os.path.exists(path):
            continue
        for tab, items in tab_pages(path):
            tips = assign(prioritise([preferred(office, general, module, tab, i) for i in items]))
            result.setdefault(app, {})[tab] = list(zip(items, tips))
    return result


def series_patches(patch_dir):
    with open(os.path.join(patch_dir, "series"), encoding="utf-8") as handle:
        return [n.strip() for n in handle if n.strip() and not n.lstrip().startswith("#")]


def file_section(text, path):
    """The part of a patch that changes `path` (its ---/+++ header and hunks), or None."""
    parts = re.split(r"(?m)^(?=--- (?:a/|/dev/null))", text)
    return next((p for p in parts if re.search(rf"(?m)^\+\+\+ b/{re.escape(path)}\s*$", p)), None)


def header_from_series(patch_dir, path, work):
    """Text of `path` as the series leaves it (a patch of the series creates it); `patch` applies the later hunks
    inside the temporary directory `work`."""
    out = os.path.join(work, path)
    for name in series_patches(patch_dir):
        with open(os.path.join(patch_dir, name), encoding="utf-8") as handle:
            section = file_section(handle.read(), path)
        if section is None:
            continue
        if section.startswith("--- /dev/null"):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            body = section.split("\n")[3:]
            with open(out, "w", encoding="utf-8") as handle:
                handle.write("".join(line[1:] + "\n" for line in body if line.startswith("+")))
        elif os.path.exists(out):
            subprocess.run(["patch", "-d", work, "-p1", "-s", "-f"], input=section, text=True, check=True)
    with open(out, encoding="utf-8") as handle:
        return handle.read()
