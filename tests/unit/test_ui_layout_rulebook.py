# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Static lint of the HST dialog layout rulebook on the .ui files of the patched tree (coat tier 3).

Rules (values from hst::design::layout, see plans/261120-0850-hst-ui-coat-tier2-3/reports/layout-rulebook.md):
- min-gap: two neighbouring controls with a border (entries, spin buttons, combo boxes, lists, buttons, notebooks)
  in a GtkGrid or GtkBox are never closer than MinGap (4 px), across or down (check and radio buttons carry their
  own padding and are checked by list-gap);
- row-gap: two controls with a border stacked in a grid column or a vertical box are RowGap (6 px) apart at least;
- list-gap: other controls stacked (check and radio buttons, labels, a check button over an entry) are not set 0-3 px
  apart: MinGap at least (phase 10: grids of labels, check and radio buttons get 4, or keep 6);
- label-height: no fixed height-request on a label or a button with a label (stacked Vietnamese marks get cut);
- ellipsize: no ellipsized label in a dialog of the list (its text must show in full).
The spacing rules hold for every dialog and tab page .ui file (not the ribbon, sidebar panels or toolbar
popups, see NOT_DIALOG); the label rules for the .ui files of the ranked dialog list
(tests/runtime/hst_dialog_layout_cases.py). Intentional exceptions, each with its reason:
tests/unit/data/ui-layout-exceptions.json.

The tree is the LibreOffice source with patches/libreoffice/series applied: HST_LO_SRC (a full patched tree, or a
copy of its */uiconfig and officecfg files), or HST_LO_PRISTINE (a pristine tree: its .ui files are copied to a
temporary directory and the series is applied to them with filterdiff + patch). Without either the tree checks
skip; the self-tests on built-in good and bad .ui documents always run.

Report mode (no unittest):
    python3 tests/unit/test_ui_layout_rulebook.py --report TREE [--json OUT] [--sweep-files OUT]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
import hst_dialog_layout_cases as cases  # noqa: E402

MIN_GAP = 4  # hst::design::layout::MinGap
ROW_GAP = 6  # hst::design::layout::RowGap (owner decision D3)
BUTTON_SPACING = 6  # vcl DialogStyle::button_spacing
EXCEPTIONS = os.path.join(HERE, "data", "ui-layout-exceptions.json")
SERIES = os.path.join(ROOT, "patches", "libreoffice", "series")

# Widgets drawn with a border of their own (unless their relief is none).
BORDERED = {"GtkEntry", "GtkSearchEntry", "GtkSpinButton", "GtkComboBox", "GtkComboBoxText", "GtkButton",
            "GtkToggleButton", "GtkMenuButton", "GtkFontButton", "GtkColorButton", "GtkTreeView", "GtkIconView",
            "GtkTextView", "GtkNotebook", "GtkFileChooserButton", "GtkAppChooserButton"}
# Controls without a border of their own: still never closer than MinGap to a neighbour.
CONTROLS = BORDERED | {"GtkCheckButton", "GtkRadioButton", "GtkScale", "GtkSwitch", "GtkLinkButton"}
TEXT_WIDGETS = {"GtkLabel", "GtkButton", "GtkToggleButton", "GtkCheckButton", "GtkRadioButton", "GtkMenuButton",
                "GtkLinkButton"}
NONE, CONTROL, BORDER = 0, 1, 2
SCROLLED_VIEWS = {"GtkTreeView", "GtkTextView", "GtkIconView"}


def prop(obj, name):
    """Value of <property name=...> on the object itself; '-' and '_' are the same in GtkBuilder names."""
    wanted = name.replace("_", "-")
    for child in obj.findall("property"):
        if child.get("name", "").replace("_", "-") == wanted:
            return (child.text or "").strip()
    return None


def packing(child, name, default=None):
    pack = child.find("packing")
    if pack is None:
        return default
    value = prop(pack, name)
    return default if value is None else value


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def shown(obj):
    """GtkBuilder hides what is not marked visible: such widgets are shown by code, often one of two alternatives in
    the same cell (Paragraph's line spacing percentage or measure), so a pair with one of them is left to the runtime
    check, which sees what is really shown."""
    return (prop(obj, "visible") or "").lower() in ("true", "1", "yes")


def kind(obj, edge=None):
    """NONE, CONTROL or BORDER: what obj shows at one of its edges ("top", "bottom", "start", "end"; None: anywhere).
    A frame shows its label at the top; a box shows its first or last shown child along its axis and all of them
    across it; a grid the children of its first or last row or column. Hidden widgets show nothing."""
    cls = obj.get("class", "")
    if not shown(obj):
        return NONE
    relief_none = (prop(obj, "relief") or "").lower() in ("none", "gtk_relief_none")
    if cls in BORDERED:
        return CONTROL if relief_none and cls in ("GtkButton", "GtkToggleButton", "GtkMenuButton") else BORDER
    if cls == "GtkScrolledWindow":
        # framed when it scrolls a list, text or icon view, or draws a shadow; a scrolled page of controls is not
        inner = [o.get("class") for _c, o in items(obj)]
        shadow = (prop(obj, "shadow-type") or "none").lower()
        if any(c in SCROLLED_VIEWS for c in inner) or shadow not in ("none", "gtk_shadow_none"):
            return BORDER
        return max((kind(o, edge) for _c, o in items(obj)), default=NONE)
    if cls in CONTROLS:
        return CONTROL
    if cls == "GtkExpander" and edge == "top":
        return CONTROL
    children = [(c, o) for c, o in items(obj) if shown(o)]
    if not children:
        return NONE
    if cls == "GtkFrame" and edge == "top" and any(c.get("type") == "label" for c in obj.findall("child")):
        return NONE
    if edge and cls in ("GtkGrid", "GtkTable"):
        spans = [(o, as_int(packing(c, "left-attach")), as_int(packing(c, "top-attach")),
                  as_int(packing(c, "width"), 1) or 1, as_int(packing(c, "height"), 1) or 1) for c, o in children]
        if edge in ("top", "bottom"):
            pick = min if edge == "top" else max
            line = pick(t if edge == "top" else t + h for _o, _l, t, _w, h in spans)
            chosen = [o for o, _l, t, _w, h in spans if (t if edge == "top" else t + h) == line]
        else:
            pick = min if edge == "start" else max
            line = pick(left if edge == "start" else left + w for _o, left, _t, w, _h in spans)
            chosen = [o for o, left, _t, w, _h in spans if (left if edge == "start" else left + w) == line]
        return max(kind(o, edge) for o in chosen)
    if edge and cls in BOXES:
        vertical = box_vertical(obj)
        along = edge in (("top", "bottom") if vertical else ("start", "end"))
        if along:
            starts = [o for c, o in children if not (packing(c, "pack-type") or "start").lower().endswith("end")]
            ends = [o for c, o in children if (packing(c, "pack-type") or "start").lower().endswith("end")]
            first = (starts or list(reversed(ends)))[0]
            last = (ends or starts)[0] if ends else starts[-1]
            return kind(first if edge in ("top", "start") else last, edge)
    return max(kind(o, edge) for _c, o in children)


NOT_LAID_OUT = ("GtkSizeGroup", "GtkAdjustment", "GtkListStore", "GtkTreeStore")
BOXES = ("GtkBox", "GtkVBox", "GtkHBox", "GtkButtonBox", "GtkHButtonBox", "GtkVButtonBox")


def box_vertical(box):
    if box.get("class") in ("GtkVBox", "GtkVButtonBox"):
        return True
    return (prop(box, "orientation") or "horizontal").lower().endswith("vertical")


def items(container):
    """[(child element, object)] of the container's direct children that are laid out (not labels of frames)."""
    out = []
    for child in container.findall("child"):
        if child.get("type") in ("label", "tab", "titlebar", "action"):
            continue
        obj = child.find("object")
        if obj is not None and obj.get("class") not in NOT_LAID_OUT:
            out.append((child, obj))
    return out


def margin(obj, side):
    value = prop(obj, "margin-" + side)
    if value is None and side in ("start", "end"):
        value = prop(obj, "margin-" + ("left" if side == "start" else "right"))
    return as_int(value) if value is not None else as_int(prop(obj, "margin"))


def finding(path, container, rule, detail, a=None, b=None):
    return {"file": path, "container": container.get("id") or container.get("class"), "rule": rule,
            "detail": detail, "between": [x.get("id") or x.get("class") for x in (a, b) if x is not None]}


def pair_findings(path, container, a, b, gap, vertical):
    out = []
    ka, kb = kind(a, "bottom" if vertical else "end"), kind(b, "top" if vertical else "start")
    if ka == BORDER and kb == BORDER:
        if gap < MIN_GAP:
            out.append(finding(path, container, "min-gap", f"{gap} px {'down' if vertical else 'across'}", a, b))
        elif vertical and gap < ROW_GAP:
            out.append(finding(path, container, "row-gap", f"{gap} px down", a, b))
    elif vertical and ka and kb and gap < MIN_GAP:  # check/radio/label rows too: >= 4 (phase 10), 0 included
        out.append(finding(path, container, "list-gap", f"{gap} px down", a, b))
    return out


def grid_findings(path, grid):
    rows = as_int(prop(grid, "row-spacing"))
    cols = as_int(prop(grid, "column-spacing"))
    cells = []
    for child, obj in items(grid):
        if not shown(obj):
            continue  # hidden cells take no row or column (VclGrid and GtkGrid skip them)
        left, top = as_int(packing(child, "left-attach")), as_int(packing(child, "top-attach"))
        width, height = as_int(packing(child, "width"), 1) or 1, as_int(packing(child, "height"), 1) or 1
        cells.append((obj, left, top, width, height))
    out = []
    for obj, left, top, width, height in cells:
        for vertical in (True, False):
            if vertical:
                nearest = [c for c in cells if c[2] >= top + height and c[1] < left + width and c[1] + c[3] > left]
                first = min((c[2] for c in nearest), default=None)
                # a row between the two, filled in any column, makes the real gap larger than one spacing
                between = any(top + height <= c[2] < first for c in cells) if first is not None else False
                spacing = rows
            else:
                nearest = [c for c in cells if c[1] >= left + width and c[2] < top + height and c[2] + c[4] > top]
                first = min((c[1] for c in nearest), default=None)
                between = any(left + width <= c[1] < first for c in cells) if first is not None else False
                spacing = cols
            if between:
                continue
            for other in [c for c in nearest if (c[2] if vertical else c[1]) == first]:
                gap = spacing + (margin(obj, "bottom") + margin(other[0], "top") if vertical
                                 else margin(obj, "end") + margin(other[0], "start"))
                out += pair_findings(path, grid, obj, other[0], gap, vertical)
    return out


def box_findings(path, box):
    vertical = box_vertical(box)
    spacing = prop(box, "spacing")
    # a button box without a spacing of its own gets the toolkit's (VCL DialogStyle::button_spacing, GTK alike)
    spacing = as_int(spacing) if spacing is not None else (BUTTON_SPACING if "ButtonBox" in box.get("class") else 0)
    groups = {"start": [], "end": []}
    for child, obj in items(box):
        if not shown(obj):
            continue  # hidden children take no place: their shown neighbours meet
        pack = (packing(child, "pack-type") or "start").lower()
        groups["end" if pack.endswith("end") else "start"].append(obj)
    groups["end"].reverse()  # end-packed children are laid out from the end: reversed, they read in screen order
    out = []
    near_a, near_b = ("bottom", "top") if vertical else ("end", "start")
    for group in groups.values():
        for a, b in zip(group, group[1:]):
            gap = spacing + margin(a, near_a) + margin(b, near_b)
            out += pair_findings(path, box, a, b, gap, vertical)
    return out


def text_findings(path, obj):
    out = []
    cls = obj.get("class")
    if cls not in TEXT_WIDGETS or (cls != "GtkLabel" and prop(obj, "label") is None):
        return out
    if as_int(prop(obj, "height-request"), -1) > 0:
        out.append(finding(path, obj, "label-height", f"height-request {prop(obj, 'height-request')}"))
    if cls == "GtkLabel" and (prop(obj, "ellipsize") or "none").lower() not in ("none", "pango_ellipsize_none"):
        out.append(finding(path, obj, "ellipsize", f"ellipsize {prop(obj, 'ellipsize')}"))
    return out


def lint(path, text, label_rules=True):
    """Findings of one .ui document (its text); `path` names it in the findings."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        return [{"file": path, "container": "", "rule": "parse", "detail": str(error), "between": []}]
    out = []
    for obj in root.iter("object"):
        cls = obj.get("class", "")
        if cls in ("GtkGrid", "GtkTable"):
            out += grid_findings(path, obj)
        elif cls in BOXES:
            out += box_findings(path, obj)
        if label_rules:
            out += text_findings(path, obj)
    return out


# Not dialogs: the ribbon, sidebar panels and toolbar popups have layouts of their own (tier 2, or out of scope)
NOT_DIALOG = re.compile(r"(^|/)(notebookbar[^/]*|sidebar[^/]*|[^/]*panel[^/]*|[^/]*toolbar[^/]*|[^/]*popup[^/]*|"
                        r"[^/]*popover[^/]*|[^/]*dropdown|docking[^/]*|navigationbar|[^/]*control|[^/]*window|"
                        r"floating[^/]*)\.ui$")


# Files loaded into windows that are not dialogs although their names do not say so
NOT_DIALOG_FILES = {"sfx2/uiconfig/ui/startcenter.ui", "svx/uiconfig/ui/mediaplayback.ui",
                    "xmlsecurity/uiconfig/ui/hstpdfviewer.ui", "sw/uiconfig/swriter/ui/commentwidget.ui",
                    "svx/uiconfig/ui/paralrspacing.ui", "svx/uiconfig/ui/paraulspacing.ui",
                    "sc/uiconfig/scalc/ui/tablestylesbox.ui"}
DIALOG_ROOTS = ("GtkDialog", "GtkMessageDialog", "GtkAssistant")


def dialog_surface(tree, rel):
    """A dialog or a page shown in one: every file with a dialog root; not the ribbon, sidebar panels, toolbar popups
    and the files above."""
    if rel in NOT_DIALOG_FILES:
        return False
    if not NOT_DIALOG.search(rel):
        return True
    with open(os.path.join(tree, rel), encoding="utf-8") as handle:
        head = handle.read()
    return any(f'class="{root}"' in head for root in DIALOG_ROOTS)


def ui_files(tree, dialogs_only=False):
    found = []
    for top in sorted(os.listdir(tree)):
        base = os.path.join(tree, top)
        if not os.path.isdir(base) or top in ("workdir", "instdir", "external", "translations"):
            continue
        for directory, _dirs, files in os.walk(base):
            if "/uiconfig" not in directory.replace(os.sep, "/") + "/":
                continue
            found += [os.path.relpath(os.path.join(directory, name), tree).replace(os.sep, "/")
                      for name in files if name.endswith(".ui")]
    return sorted(rel for rel in found if not dialogs_only or dialog_surface(tree, rel))


def listed_ui():
    """The .ui files of the ranked list, with the shared pages its dialogs show."""
    return {ui for case in cases.listed().values() for ui in case.ui + case.uses}


def lint_tree(tree):
    label_scope = listed_ui()
    out = []
    for rel in ui_files(tree, dialogs_only=True):
        with open(os.path.join(tree, rel), encoding="utf-8") as handle:
            out += lint(rel, handle.read(), label_rules=rel in label_scope)
    return out


def load_exceptions():
    with open(EXCEPTIONS, encoding="utf-8") as handle:
        data = json.load(handle)
    for entry in data["exceptions"]:
        if not entry.get("reason") or not entry.get("file") or not entry.get("rule"):
            raise ValueError(f"exception without file, rule or reason: {entry}")
    return data["exceptions"]


def excepted(item, exceptions):
    for entry in exceptions:
        if entry["file"] == item["file"] and entry["rule"] == item["rule"] and \
                entry.get("container", "*") in ("*", item["container"]) and \
                ("between" not in entry or entry["between"] == item["between"]):
            return entry
    return None


def patched_tree():
    """(tree, cleanup) from HST_LO_SRC or HST_LO_PRISTINE; (None, None) when neither is set."""
    if os.environ.get("HST_LO_SRC"):
        return os.environ["HST_LO_SRC"], None
    pristine = os.environ.get("HST_LO_PRISTINE")
    if not pristine:
        return None, None
    if not shutil.which("filterdiff") or not shutil.which("patch"):
        raise unittest.SkipTest("filterdiff (patchutils) and patch are needed to apply the series")
    tree = tempfile.mkdtemp(prefix="hst-ui-tree-")
    for rel in ui_files(pristine):
        os.makedirs(os.path.dirname(os.path.join(tree, rel)), exist_ok=True)
        shutil.copy2(os.path.join(pristine, rel), os.path.join(tree, rel))
    with open(SERIES, encoding="utf-8") as handle:
        names = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    for name in names:
        diff = subprocess.run(["filterdiff", "-p1", "-i", "*.ui", os.path.join(ROOT, "patches", "libreoffice", name)],
                              capture_output=True, check=True).stdout
        if diff.strip():
            result = subprocess.run(["patch", "-d", tree, "-p1", "-s", "-f", "--no-backup-if-mismatch"], input=diff,
                                    capture_output=True)
            if result.returncode:
                shutil.rmtree(tree, ignore_errors=True)
                raise RuntimeError(f"{name} does not apply to the .ui files: {result.stdout.decode()[-400:]}")
    return tree, lambda: shutil.rmtree(tree, ignore_errors=True)


def visible(text):
    """The fixture with every object marked visible, as the .ui files mark what they show."""
    shown = r'<property name="visible">True</property>'
    text = re.sub(r'(<object class="[^"]+" id="[^"]+")/>', r'\1>' + shown + '</object>', text)
    return re.sub(r'(<object class="[^"]+" id="[^"]+">)(?!<property name="visible">)', r'\1' + shown, text)


GOOD = """<interface>
  <object class="GtkDialog" id="dlg"><child internal-child="vbox"><object class="GtkBox" id="vbox">
    <property name="orientation">vertical</property><property name="spacing">12</property>
    <child><object class="GtkGrid" id="grid">
      <property name="row-spacing">6</property><property name="column-spacing">12</property>
      <child><object class="GtkLabel" id="l1"><property name="label">Lề trái:</property></object>
        <packing><property name="left-attach">0</property><property name="top-attach">0</property></packing></child>
      <child><object class="GtkSpinButton" id="s1"/>
        <packing><property name="left-attach">1</property><property name="top-attach">0</property></packing></child>
      <child><object class="GtkSpinButton" id="s2"/>
        <packing><property name="left-attach">1</property><property name="top-attach">1</property></packing></child>
    </object></child>
    <child><object class="GtkBox" id="checks"><property name="orientation">vertical</property>
      <property name="spacing">4</property>
      <child><object class="GtkCheckButton" id="c1"><property name="label">Ẩn Ỗ Ữ</property></object></child>
      <child><object class="GtkCheckButton" id="c2"><property name="label">Ặ ậ ỷ</property></object></child>
    </object></child>
    <child><object class="GtkGrid" id="swatches"><property name="row-spacing">0</property>
      <child><object class="GtkDrawingArea" id="d1"/>
        <packing><property name="left-attach">0</property><property name="top-attach">0</property></packing></child>
      <child><object class="GtkDrawingArea" id="d2"/>
        <packing><property name="left-attach">0</property><property name="top-attach">1</property></packing></child>
    </object></child>
  </object></child></object>
</interface>"""

BAD = """<interface>
  <object class="GtkDialog" id="dlg"><child internal-child="vbox"><object class="GtkBox" id="vbox">
    <property name="orientation">vertical</property>
    <child><object class="GtkGrid" id="margins">
      <property name="row_spacing">3</property><property name="column_spacing">2</property>
      <child><object class="GtkSpinButton" id="top"/>
        <packing><property name="left_attach">1</property><property name="top_attach">0</property></packing></child>
      <child><object class="GtkSpinButton" id="bottom"/>
        <packing><property name="left_attach">1</property><property name="top_attach">1</property></packing></child>
      <child><object class="GtkComboBoxText" id="unit"/>
        <packing><property name="left_attach">2</property><property name="top_attach">0</property></packing></child>
    </object></child>
    <child><object class="GtkGrid" id="spaced"><property name="row-spacing">5</property>
      <child><object class="GtkEntry" id="e1"/>
        <packing><property name="left-attach">0</property><property name="top-attach">0</property></packing></child>
      <child><object class="GtkEntry" id="e2"/>
        <packing><property name="left-attach">0</property><property name="top-attach">1</property></packing></child>
    </object></child>
    <child><object class="GtkGrid" id="checks"><property name="row-spacing">3</property>
      <child><object class="GtkCheckButton" id="k1"/>
        <packing><property name="left-attach">0</property><property name="top-attach">0</property></packing></child>
      <child><object class="GtkCheckButton" id="k2"/>
        <packing><property name="left-attach">0</property><property name="top-attach">1</property></packing></child>
    </object></child>
    <child><object class="GtkLabel" id="title"><property name="label">Ẩn Ỗ Ữ Ặ ậ ỷ</property>
      <property name="height_request">14</property><property name="ellipsize">end</property></object></child>
  </object></child></object>
</interface>"""


class RulebookSelfTest(unittest.TestCase):
    """The lint itself, on a .ui that keeps every rule and one that breaks each of them."""

    def test_good_dialog_is_clean(self):
        self.assertEqual(lint("good.ui", visible(GOOD)), [])

    def test_bad_dialog_breaks_every_rule(self):
        found = {(item["rule"], tuple(item["between"])) for item in lint("bad.ui", visible(BAD))}
        self.assertIn(("min-gap", ("top", "bottom")), found)  # spin buttons stacked 3 px apart
        self.assertIn(("min-gap", ("top", "unit")), found)  # 2 px across
        self.assertIn(("row-gap", ("e1", "e2")), found)  # 5 px: above MinGap, below RowGap
        self.assertIn(("list-gap", ("k1", "k2")), found)  # check buttons set 3 px apart
        self.assertIn(("label-height", ()), found)
        self.assertIn(("ellipsize", ()), found)

    def test_label_rules_only_where_asked(self):
        rules = {item["rule"] for item in lint("bad.ui", visible(BAD), label_rules=False)}
        self.assertNotIn("label-height", rules)
        self.assertNotIn("ellipsize", rules)

    def test_borderless_button_row_may_be_tight_but_not_below_min_gap(self):
        ui = """<interface><object class="GtkBox" id="b"><property name="orientation">vertical</property>
          <property name="spacing">4</property>
          <child><object class="GtkButton" id="x"><property name="relief">none</property></object></child>
          <child><object class="GtkButton" id="y"><property name="relief">none</property></object></child>
        </object></interface>"""
        self.assertEqual(lint("relief.ui", visible(ui)), [])

    def test_hidden_alternative_and_frame_label_are_no_neighbours(self):
        ui = visible("""<interface><object class="GtkBox" id="b"><property name="orientation">vertical</property>
          <child><object class="GtkSpinButton" id="percent"/></child>
          <child><object class="GtkFrame" id="f">
            <child><object class="GtkEntry" id="inside"/></child>
            <child type="label"><object class="GtkLabel" id="caption"><property name="label">Nhóm</property></object>
            </child></object></child>
        </object></interface>""")
        self.assertEqual(lint("frame.ui", ui), [])  # the frame's caption sits between the two boxes
        alternatives = """<interface><object class="GtkBox" id="b"><property name="visible">True</property>
          <property name="orientation">vertical</property>
          <child><object class="GtkSpinButton" id="percent"><property name="visible">True</property></object></child>
          <child><object class="GtkSpinButton" id="metric"/></child>
        </object></interface>"""
        self.assertEqual(lint("hidden.ui", alternatives), [])  # code shows one of the two: the runtime check sees it


    def test_row_filled_in_another_column_is_no_neighbour(self):
        ui = visible("""<interface><object class="GtkGrid" id="g"><property name="row-spacing">3</property>
          <child><object class="GtkEntry" id="a"/>
            <packing><property name="left-attach">0</property><property name="top-attach">0</property></packing></child>
          <child><object class="GtkLabel" id="note"/>
            <packing><property name="left-attach">1</property><property name="top-attach">1</property></packing></child>
          <child><object class="GtkEntry" id="b"/>
            <packing><property name="left-attach">0</property><property name="top-attach">2</property></packing></child>
        </object></interface>""")
        self.assertEqual(lint("rows.ui", ui), [])  # row 1 lies between a and b: the gap is a row plus two spacings

    def test_hidden_child_between_does_not_mask(self):
        ui = """<interface><object class="GtkBox" id="b"><property name="visible">True</property>
          <property name="orientation">vertical</property>
          <child><object class="GtkEntry" id="x"><property name="visible">True</property></object></child>
          <child><object class="GtkEntry" id="hidden"/></child>
          <child><object class="GtkEntry" id="y"><property name="visible">True</property></object></child>
        </object></interface>"""
        self.assertEqual([(i["rule"], i["between"]) for i in lint("mask.ui", ui)], [("min-gap", ["x", "y"])])

    def test_check_flush_against_entry(self):
        ui = visible("""<interface><object class="GtkBox" id="b"><property name="orientation">vertical</property>
          <child><object class="GtkCheckButton" id="c"/></child><child><object class="GtkEntry" id="e"/></child>
          <child><object class="GtkRadioButton" id="r1"/></child><child><object class="GtkRadioButton" id="r2"/></child>
        </object></interface>""")
        found = [(i["rule"], i["between"]) for i in lint("mixed.ui", ui)]
        self.assertEqual(found, [("list-gap", ["c", "e"]), ("list-gap", ["e", "r1"]), ("list-gap", ["r1", "r2"])])

    def test_dialog_named_like_a_toolbar_is_a_dialog(self):
        tree = tempfile.mkdtemp()
        try:
            for rel, root in (("cui/uiconfig/ui/newtoolbardialog.ui", "GtkDialog"),
                              ("svx/uiconfig/ui/sidebarline.ui", "GtkBox")):
                os.makedirs(os.path.join(tree, os.path.dirname(rel)), exist_ok=True)
                with open(os.path.join(tree, rel), "w", encoding="utf-8") as handle:
                    handle.write(f'<interface><object class="{root}" id="x"/></interface>')
            self.assertEqual(ui_files(tree, dialogs_only=True), ["cui/uiconfig/ui/newtoolbardialog.ui"])
        finally:
            shutil.rmtree(tree)


class DialogListBatches(unittest.TestCase):
    """The ranked list: 60-100 dialogs, every .ui in exactly one batch."""

    def test_list_size_and_known_ids(self):
        self.assertEqual(len(cases.LIST), 80)  # owner decision D12: 80 dialogs in four batches
        self.assertEqual(len(set(cases.LIST)), len(cases.LIST))
        self.assertEqual([key for key in cases.LIST if key not in cases.CANDIDATES], [])

    def test_every_ui_in_one_batch(self):
        owner = {}
        for key, case in cases.listed().items():
            self.assertIn(case.batch, "ABCD", key)
            for ui in case.ui:
                self.assertNotIn(ui, owner, f"{ui}: {owner.get(ui)} and {key}")
                owner[ui] = key

    def test_every_shared_page_owned(self):
        """A page a listed dialog shows but does not own belongs to another listed dialog (its batch edits it)."""
        owned = {ui for case in cases.listed().values() for ui in case.ui}
        unowned = sorted({(key, ui) for key, case in cases.listed().items() for ui in case.uses if ui not in owned})
        self.assertEqual(unowned, [])


class RuntimeAnalysisSelfTest(unittest.TestCase):
    """The runtime checker's geometry (gaps, clipped text, fit) on built-in windows; no office needed."""

    def test_geometry(self):
        import hst_dialog_layout_check
        hst_dialog_layout_check.selftest_geometry()


class RulebookOnTree(unittest.TestCase):
    """The rules on the .ui files of the patched tree (red until the spacing sweep and the batches land)."""

    @classmethod
    def setUpClass(cls):
        cls.tree, cls.cleanup = patched_tree()
        if not cls.tree:
            raise unittest.SkipTest("HST_LO_SRC (patched tree) or HST_LO_PRISTINE (pristine tree) not set")
        cls.findings = lint_tree(cls.tree)
        cls.exceptions = load_exceptions()

    @classmethod
    def tearDownClass(cls):
        if cls.cleanup:
            cls.cleanup()

    def open_findings(self, rules):
        return [f"{item['file']} {item['container']}: {item['rule']} {item['detail']} {item['between']}"
                for item in self.findings if item["rule"] in rules and not excepted(item, self.exceptions)]

    def test_spacing(self):
        self.assertEqual(self.open_findings({"min-gap", "row-gap", "list-gap", "parse"}), [])

    def test_labels_of_listed_dialogs(self):
        self.assertEqual(self.open_findings({"label-height", "ellipsize"}), [])

    def test_listed_ui_files_exist(self):
        files = set(ui_files(self.tree))
        missing = sorted(ui for case in cases.listed().values() for ui in case.ui + case.uses if ui not in files)
        self.assertEqual(missing, [])

    def test_no_stale_exception(self):
        stale = [entry for entry in self.exceptions
                 if not any(excepted(item, [entry]) for item in self.findings)]
        self.assertEqual(stale, [])


def report(args):
    findings = lint_tree(args.report)
    exceptions = load_exceptions()
    open_items = [item for item in findings if not excepted(item, exceptions)]
    by_rule = {}
    for item in open_items:
        by_rule.setdefault(item["rule"], set()).add(item["file"])
    for rule, files in sorted(by_rule.items()):
        print(f"{rule}: {sum(1 for i in open_items if i['rule'] == rule)} findings in {len(files)} files")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as out:
            json.dump({"findings": findings, "open": len(open_items)}, out, ensure_ascii=False, indent=1)
    if args.sweep_files:
        spacing = [item for item in open_items if item["rule"] in ("min-gap", "row-gap", "list-gap")]
        with open(args.sweep_files, "w", encoding="utf-8") as out:
            out.write("".join(name + "\n" for name in sorted({item["file"] for item in spacing})))
        # the detail next to it: what to change where (container, axis, the pair), so a sweep edits only these
        with open(os.path.splitext(args.sweep_files)[0] + ".tsv", "w", encoding="utf-8") as out:
            out.write("file\tcontainer\trule\tdetail\tbetween\n")
            for item in sorted(spacing, key=lambda i: (i["file"], i["container"], i["detail"])):
                out.write(f"{item['file']}\t{item['container']}\t{item['rule']}\t{item['detail']}\t"
                          f"{' / '.join(item['between'])}\n")
    return 1 if open_items else 0


if __name__ == "__main__":
    if "--report" in sys.argv:
        parser = argparse.ArgumentParser(description="HST dialog layout rulebook lint")
        parser.add_argument("--report", required=True, help="patched tree (or its .ui copy)")
        parser.add_argument("--json")
        parser.add_argument("--sweep-files", help="write the .ui files with open spacing findings")
        sys.exit(report(parser.parse_args()))
    unittest.main()
