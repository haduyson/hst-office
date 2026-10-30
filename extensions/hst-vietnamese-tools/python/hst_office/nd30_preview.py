# SPDX-License-Identifier: AGPL-3.0-only
"""Monospace text preview of an ND30 layout (pure logic, no `uno`), shown live in the wizard.

It mirrors what nd30_writer puts on the page: the two-column header (agency | national title and motto) and the
signature block (recipients | signer) side by side, centred lines centred, rules drawn as box-drawing lines whose
length follows the rule width of the layout, the body justified with a first-line indent. Bold and font sizes
cannot be shown in plain text; the inserted document carries them.
"""
import textwrap
import unicodedata

RULE = "─"  # ─
GAP = 2          # spaces between the two columns


def _width(text):
    return len(unicodedata.normalize("NFC", text))


def _text(paragraph):
    return unicodedata.normalize("NFC", "".join(run["text"] for run in paragraph["runs"]))


def _wrap(text, width, indent=0):
    if not text:
        return [""]
    return textwrap.wrap(text, width, initial_indent=" " * indent, break_long_words=True, break_on_hyphens=False) or [""]


def _align(line, width, align):
    if align == "center":
        pad = max(0, width - _width(line))
        return " " * (pad // 2) + line + " " * (pad - pad // 2)
    return line + " " * max(0, width - _width(line))


def _paragraph_lines(paragraph, width, cell_mm, top_level):
    """Lines of one paragraph (and its rule) at `width` characters."""
    out = []
    before = paragraph.get("spacing_before_pt", 0)
    if before >= (12 if top_level else 6):
        out.append("")
    align = paragraph.get("align", "center")
    indent = 4 if paragraph.get("indent_first_mm") else 0
    left = min(width // 2, int(round(paragraph.get("indent_left_mm", 0) / cell_mm * width)))
    out += [" " * left + _align(line, width - left, align) for line in _wrap(_text(paragraph), width - left, indent)]
    if paragraph.get("rule_mm"):
        length = max(3, min(width, int(round(paragraph["rule_mm"] / cell_mm * width))))
        out.append(_align(RULE * length, width, "center"))
    if paragraph.get("spacing_after_pt", 0) >= 24:  # room for the signature
        out += ["", ""]
    return out


def _column(paragraphs, width, cell_mm):
    lines = []
    for paragraph in paragraphs:
        lines += _paragraph_lines(paragraph, width, cell_mm, False)
    return lines


def layout_to_preview(layout, width=62):
    """Plain-text page preview of `layout` (nd30_layout.build_layout) at `width` characters per line."""
    text_mm = layout["textWidthMm"]
    out = []
    for block in layout["blocks"]:
        if block["type"] == "paragraph":
            out += _paragraph_lines(block, width, text_mm, True)
            continue
        if block.get("spacing_before_pt", 0) >= 12:
            out.append("")
        left_w = int(round((width - GAP) * block["widthsPct"][0] / 100.0))
        right_w = width - GAP - left_w
        left = _column(block["left"], left_w, text_mm * block["widthsPct"][0] / 100.0)
        right = _column(block["right"], right_w, text_mm * block["widthsPct"][1] / 100.0)
        for i in range(max(len(left), len(right))):
            a = left[i] if i < len(left) else ""
            b = right[i] if i < len(right) else ""
            out.append((_align(a, left_w, "left") + " " * GAP + b).rstrip())
    return "\n".join(line.rstrip() for line in out)
