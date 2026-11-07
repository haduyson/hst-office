# SPDX-License-Identifier: AGPL-3.0-only
""""In hai mặt" (two-sided printing) for every administrative document type: the rule per profile and its application.

Rule table, with the clause each row follows (also in help/nd30.html and the S4 report):
  * dang (Party documents, 22 types): Hướng dẫn 05-HD/VPTW ngày 27/5/2026, Phần II, IV.4.2: "Trường hợp văn bản in hai
    mặt, mặt sau vùng trình bày như sau: lề trên 20 mm, lề dưới 20 mm, lề trái 15 mm, lề phải 30 mm" (front, IV.4.1:
    20/20/30/15). Two-sided ON = mirrored page style: inner (binding) margin 30 mm, outer 15 mm, so odd pages are
    left 30 / right 15 and even pages left 15 / right 30. OFF keeps IV.4.1 on every page.
  * nd30 (state administrative documents and forms, 49 types): Nghị định 30/2020/NĐ-CP, Phụ lục I, Phần I, Mục I,
    khoản 3 "Định lề trang: Cách mép trên và mép dưới 20 - 25 mm, cách mép trái 30 - 35 mm, cách mép phải 15 - 20 mm"
    and khoản 7 (page number centred in the top margin, not on page 1). Phụ lục I says nothing about two-sided
    printing or back-page margins (checked: the whole Phụ lục I and the decree text). So margins are NOT mirrored;
    two-sided ON only records the choice, keeps one page layout for left and right pages and the centred number
    (the same on both sides), and leaves the automatically inserted blank pages at the office default.
  * qppl (Thông tư, 2 types): Nghị định 78/2025/NĐ-CP, Phụ lục I, Mục 1, I.3 (margins: top, bottom and right
    15 - 20 mm, left 30 - 35 mm) and I.7 (page number centred in the top margin, not on page 1); also silent on
    two-sided printing, so the same as nd30: no mirroring.
The printer's own two-sided mode cannot be stored in ODF or DOCX (it lives in the printer job setup, tied to a printer
name and driver), so it is chosen in the Print dialog; the choice here is a document property that drives the page style.
"""
from .nd30 import profile_rules
from .undo import undo_locked

MM = 100
PROPERTY = "HST In hai mặt"
PROFILE_PROPERTY = "HST Loại thể thức"
ALL, MIRRORED = 0, 3  # com.sun.star.style.PageStyleLayout
PARTY_MARK = "ĐẢNG CỘNG SẢN VIỆT NAM"

RULES = {
    "dang": {"mirrored": True, "clause": "Hướng dẫn 05-HD/VPTW (27/5/2026), Phần II, IV.4.2"},
    "nd30": {"mirrored": False, "clause": "Nghị định 30/2020/NĐ-CP, Phụ lục I, Phần I, Mục I, khoản 3 và 7 (không quy định in hai mặt)"},
    "qppl": {"mirrored": False, "clause": "Nghị định 78/2025/NĐ-CP, Phụ lục I, Mục 1, I.3 và I.7 (không quy định in hai mặt)"},
}


def rule(profile):
    return RULES.get(profile, RULES["nd30"])


def page_plan(profile, duplex, margins_mm=None):
    """Page-style values for the choice (pure). Margins in mm on the front page; mirrored keeps them as inner/outer."""
    margins = margins_mm or profile_rules(profile if profile in RULES else "nd30")["defaultMarginsMm"]
    mirrored = bool(duplex) and rule(profile)["mirrored"]
    return {"PageStyleLayout": MIRRORED if mirrored else ALL,
            "LeftMargin": int(round(float(margins["left"]) * MM)), "RightMargin": int(round(float(margins["right"]) * MM))}


def back_page_margins(plan):
    """(left, right) in mm of an even page for a plan (pure): what a reader measures on the back of the sheet."""
    left, right = plan["LeftMargin"] / MM, plan["RightMargin"] / MM
    return (right, left) if plan["PageStyleLayout"] == MIRRORED else (left, right)


def _user_props(doc):
    return doc.getDocumentProperties().getUserDefinedProperties()


def _set_property(doc, name, value):
    props = _user_props(doc)
    if props.getPropertySetInfo().hasPropertyByName(name):
        props.setPropertyValue(name, value)
    else:
        props.addProperty(name, 128, value)  # PropertyAttribute.REMOVABLE


def read_choice(doc):
    """(duplex, profile) stored in the document; (False, None) when it never had the choice."""
    props = _user_props(doc)
    info = props.getPropertySetInfo()
    duplex = bool(props.getPropertyValue(PROPERTY)) if info.hasPropertyByName(PROPERTY) else False
    profile = props.getPropertyValue(PROFILE_PROPERTY) if info.hasPropertyByName(PROFILE_PROPERTY) else None
    return duplex, (profile if profile in RULES else None)


def guess_profile(doc):
    """Profile of a document the wizard did not mark: a Party heading near the top means dang, else nd30."""
    try:
        enum = doc.getText().createEnumeration()
        for _ in range(12):
            if not enum.hasMoreElements():
                break
            part = enum.nextElement()
            texts = [part.getString()] if part.supportsService("com.sun.star.text.Paragraph") else \
                [part.getCellByName(n).getString() for n in part.getCellNames()]
            if any(PARTY_MARK in t.upper() for t in texts):
                return "dang"
    except Exception:  # noqa: BLE001 - unreadable text: the state rule (no mirroring) is the safe default
        pass
    return "nd30"


def _styles_of(doc, cursor):
    """The cursor's page style and its "kèm theo" copy (attached documents number their own pages)."""
    styles = doc.getStyleFamilies().getByName("PageStyles")
    name = cursor.PageStyleName
    names = [name] + ([n for n in ("HST " + name + " kèm theo",) if styles.hasByName(n)])
    return [styles.getByName(n) for n in names]


def apply(doc, cursor, duplex, profile):
    """Store the choice and set the page style(s). Margins of the front page are kept as they are. Not undoable."""
    profile = profile if profile in RULES else "nd30"
    with undo_locked(doc):
        for style in _styles_of(doc, cursor):  # LeftMargin/RightMargin stay: mirrored reads them as inner/outer
            plan = page_plan(profile, duplex, {"left": style.LeftMargin / MM, "right": style.RightMargin / MM})
            style.PageStyleLayout = plan["PageStyleLayout"]
        _set_property(doc, PROPERTY, bool(duplex))
        _set_property(doc, PROFILE_PROPERTY, profile)
    doc.setModified(True)
    return {"duplex": bool(duplex), "profile": profile, "mirrored": plan["PageStyleLayout"] == MIRRORED,
            "clause": rule(profile)["clause"]}


def toggle(doc, cursor):
    """HST menu "In hai mặt" on an existing document: flips the stored choice for the current page style."""
    duplex, profile = read_choice(doc)
    return apply(doc, cursor, not duplex, profile or guess_profile(doc))
