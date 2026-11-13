# SPDX-License-Identifier: AGPL-3.0-only
"""Length of the rule under the agency name, as chosen in the ND30 wizard (pure logic, no `uno`).

ND30 Phụ lục I, II.2b: a solid rule, centred under the agency name, 1/3 to 1/2 as long as the line of text. The wizard
offers 1/3, 2/5 (the profile's agencyFraction, the default), 1/2, "as long as the line above" (the parent agency's
line, else the agency name's own) and a length typed in mm; the last two may leave the ND30 range, which the wizard
points out without refusing. The choice travels in the layout fields as "_agencyRule" and is remembered per user as
the same string (nd30_prefs): "1/3", "2/5", "1/2", "parent" or "mm:<length>".
"""
from .nd30_metrics import widest_line_mm

FRACTIONS = {"1/3": 1.0 / 3, "2/5": 0.4, "1/2": 0.5}
CHOICES = ("1/3", "2/5", "1/2", "parent", "mm")  # the order of the wizard's list
DEFAULT = "2/5"
MIN_MM = 5.0  # shorter than this is no rule under a heading any more
RANGE = (1.0 / 3, 0.5)
FIELD = "_agencyRule"


def parse_mm(text):
    """A length typed by the user ("30", "32,5", "32.5 mm") as a float, or None."""
    text = str(text or "").strip().lower().replace("mm", "").replace(",", ".").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 and value < 1000 else None


def parse(value):
    """(choice, mm): one of CHOICES and, for "mm", the typed length; anything unknown is the default."""
    value = str(value or "").strip()
    if value in FRACTIONS or value == "parent":
        return value, None
    if value.startswith("mm:") and parse_mm(value[3:]) is not None:
        return "mm", parse_mm(value[3:])
    return DEFAULT, None


def encode(choice, mm=None):
    """The stored/field form of a choice; None for "mm" without a valid length."""
    if choice == "mm":
        return None if mm is None else "mm:%g" % round(mm, 1)
    return choice if choice in CHOICES else DEFAULT


def agency_rule_mm(value, agency, parent, typography, cell_mm, profile_fraction):
    """Rule length in mm under `agency` (upper-case, may span several lines) in a cell `cell_mm` wide. Profiles without
    an agency rule (profile_fraction 0, the Party forms) keep none whatever was chosen."""
    if not profile_fraction:
        return 0
    choice, mm = parse(value)
    line = widest_line_mm(agency, typography["agency"], True, cell_mm)
    if choice == "mm":
        length = max(MIN_MM, mm)
    elif choice == "parent":
        length = widest_line_mm(parent, typography["parentAgency"], False, cell_mm) if parent else line
    else:
        length = line * FRACTIONS[choice]
    return round(min(length, cell_mm), 2)


def _agency_paragraph(layout):
    for block in layout.get("blocks", []):
        if block.get("type") == "grid" and block.get("name") == "Header":
            for paragraph in block["rows"][0]["cells"][0]:
                if paragraph.get("role") == "Agency":
                    return paragraph, layout["textWidthMm"] * block["widthsPct"][0] / 100.0
    return None, None


def out_of_range(layout):
    """True when the agency rule of `layout` is shorter than 1/3 or longer than 1/2 of the agency's longest line."""
    paragraph, cell_mm = _agency_paragraph(layout)
    if paragraph is None or not paragraph.get("rule_mm"):
        return False
    run = paragraph["runs"][0]
    line = widest_line_mm(run["text"], run["size"], True, cell_mm)
    ratio = paragraph["rule_mm"] / line if line else 0
    return not (RANGE[0] - 0.005 <= ratio <= RANGE[1] + 0.005)
