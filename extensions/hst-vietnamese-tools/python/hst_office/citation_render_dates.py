# SPDX-License-Identifier: AGPL-3.0-only
"""Dates in citations. Vietnamese full dates follow the administrative convention (day below 10 and months 1–2
get a leading zero): "07 tháng 5 năm 2009", "05 tháng 02 năm 2024".

Forms: year (2010, 2010a, 2009–2010), full (vi: 07 tháng 5 năm 2009; en: May 7, 2009), dmy (7 May 2009),
dmy-abbr (20 Mar. 2024, MLA), mdy-abbr (Mar. 20, 2024, IEEE), ymd (2009 May 7, Vancouver/NLM),
y-md (2009, May 7, APA), my (May 2009 / tháng 5 năm 2009), my-abbr (Jan. 2009).
"""
from . import citation_dates as dates
from .citation_terms import MONTHS_EN, MONTHS_EN_ABBR, MONTHS_EN_SHORT, term_language

FORMS = ("year", "full", "dmy", "dmy-abbr", "mdy-abbr", "ymd", "y-md", "my", "my-abbr")


def _vi_two(number, month=False):
    return "%02d" % number if (number < 10 and not month) or (month and number <= 2) else str(number)


def _vi(year, month, day, form):
    if not month:
        return str(year)
    if form in ("my", "my-abbr"):
        return "tháng %s năm %d" % (_vi_two(month, True), year)
    if form == "ymd" and day:
        return "%d/%d/%d" % (day, month, year)
    if form == "y-md":
        return "%d, ngày %d tháng %d" % (year, day, month) if day else "%d, tháng %d" % (year, month)
    if not day:
        return "tháng %s năm %d" % (_vi_two(month, True), year)
    return "%s tháng %s năm %d" % (_vi_two(day), _vi_two(month, True), year)


def _en(year, month, day, form):
    if not month:
        return str(year)
    full, abbr, short = MONTHS_EN[month - 1], MONTHS_EN_ABBR[month - 1], MONTHS_EN_SHORT[month - 1]
    if form == "ymd":
        return " ".join(str(p) for p in (year, short, day or "") if p)
    if form == "y-md":
        return "%d, %s" % (year, full + (" %d" % day if day else ""))
    if form in ("my", "my-abbr"):
        return "%s %d" % (abbr if form == "my-abbr" else full, year)
    if form in ("dmy", "dmy-abbr"):
        name = abbr if form == "dmy-abbr" and month not in (6, 7) else full  # MLA spells out May, June, July
        return ("%d %s %d" % (day, name, year)) if day else "%s %d" % (name, year)
    name = abbr if form == "mdy-abbr" else full
    return ("%s %d, %d" % (name, day, year)) if day else "%s %d" % (name, year)


def year_text(date, suffix=""):
    """"2010", "2010a", "2009–2010"; "" when the date has no year (literal dates are returned as written)."""
    if not date:
        return ""
    if "date-parts" not in date:
        return date.get("literal", "")
    years = [str(p[0]) for p in date["date-parts"] if p]
    text = "–".join(dict.fromkeys(years))
    return text + suffix


def format_date(date, form, lang, suffix=""):
    """The date in the given form and language (the item's or the document's); year suffix after the year."""
    if not date:
        return ""
    if "date-parts" not in date:
        return date.get("literal", "")
    if form not in FORMS or form == "year" or len(date["date-parts"]) > 1:
        return year_text(date, suffix)
    year, month, day = dates.parts(date)
    text = _vi(year, month, day, form) if term_language(lang) == "vi" else _en(year, month, day, form)
    return text.replace(str(year), str(year) + suffix, 1) if suffix else text
