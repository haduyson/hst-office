# SPDX-License-Identifier: AGPL-3.0-only
"""Line widths and word wrap from Times New Roman advance widths (pure logic, no `uno`).

The table comes from Liberation Serif, whose advances equal Times New Roman's, so rule lengths are computed from the
real line instead of a guess. See scripts/templates/build-font-metrics.py.
"""
import unicodedata

from .data_files import load_data

MM_PER_PT = 25.4 / 72
ASCENT_EM = 0.891  # Times New Roman ascent
_TABLE = {}


def _styles():
    if not _TABLE:
        data = load_data("font-metrics-times.json")
        _TABLE.update(data, units=float(data["unitsPerEm"]))
    return _TABLE


def _advance(char, table):
    if char in table:
        return table[char]
    base = next((c for c in unicodedata.normalize("NFD", char) if not unicodedata.combining(c)), "")
    return table.get(base, table["n"])


def text_width_mm(text, size_pt, bold=False, italic=False):
    styles = _styles()
    table = styles[{(False, False): "regular", (True, False): "bold", (False, True): "italic", (True, True): "boldItalic"}[(bool(bold), bool(italic))]]
    units = sum(_advance(c, table) for c in unicodedata.normalize("NFC", text))
    return units / styles["units"] * size_pt * MM_PER_PT


def wrap_lines(text, size_pt, bold, width_mm):
    """Greedy word wrap, as the text engine does it: the lines of `text` in a cell `width_mm` wide."""
    lines, current = [], ""
    for word in text.split():
        trial = current + " " + word if current else word
        if current and text_width_mm(trial, size_pt, bold) > width_mm:
            lines.append(current)
            current = word
        else:
            current = trial
    return lines + [current] if current else [""]


def widest_line_mm(text, size_pt, bold, width_mm):
    """Width of the longest line of `text` wrapped at `width_mm`; explicit line breaks are honoured."""
    return max(text_width_mm(line, size_pt, bold)
               for part in text.split("\n") for line in wrap_lines(part, size_pt, bold, width_mm))


def rule_for(text, size_pt, bold, width_mm, fraction):
    """Rule length: `fraction` of the longest wrapped line, inside the cell (ND30 II.2b, II.5b: 1/3-1/2 of the line)."""
    return round(min(widest_line_mm(text, size_pt, bold, width_mm) * fraction, width_mm), 2)
