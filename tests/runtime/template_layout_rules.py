# SPDX-License-Identifier: AGPL-3.0-only
"""Validate rendered header and title rules against their template layout cases."""
import template_layout_measure as measure


def _ruled(lines, rules, text, after=-1.0):
    """(rule, lines of its paragraph) for the first paragraph starting with `text` below `after` mm, or an error."""
    words = " ".join(text.split())
    own = [ln for ln in lines if ln["y0"] > after and len(ln["text"]) >= 4
           and (words.startswith(ln["text"][:12]) or ln["text"].startswith(words[:12]))]
    if not own:
        return None, "ruled line %r not found" % words[:40]
    first = min(own, key=lambda ln: ln["y0"])
    centre = (first["x0"] + first["x1"]) / 2
    below = [r for r in rules if r[2] > first["y1"] - 0.5 and abs((r[0] + r[1]) / 2 - centre) < 15]
    if not below:
        return None, "no rule under %r" % words[:40]
    rule = min(below, key=lambda r: r[2])
    return (rule, [ln for ln in lines if first["y0"] - 0.5 <= ln["y0"] and ln["y1"] <= rule[2] + 0.5
                   and abs((ln["x0"] + ln["x1"]) / 2 - centre) < 15]), None


def _centred(rule, line, label):
    if abs((rule[0] + rule[1]) / 2 - (line["x0"] + line["x1"]) / 2) > 0.5:
        return ["rule under %r not centred: %s against line %.2f-%.2f" % (label, rule[:2], line["x0"], line["x1"])]
    return []


def check_rules(case, pdf):
    """Every rule, measured in the PDF and centred (±0.5 mm) under its paragraph; a rule or line that is expected and
    not found fails (Decree 30, Annex I).
    - Page-1 header: under the motto and the Party name as long as the line; under the agency 1/3 to 1/2 of its longest
      line (measured against the text, not computed).
    - Title, summary and subtitle rules on any page, in document order: the length the generator computed (±0.5 mm)."""
    fails = []
    rules, lines = measure.horizontal_lines(pdf, 1), measure.text_lines(pdf, 1)
    for text, column in case["rules"]:
        found, error = _ruled(lines, rules, text)
        if error:
            fails.append(error + " on page 1")
            continue
        rule, block = found
        line = max(block, key=lambda ln: ln["x1"] - ln["x0"])
        width, length, label = line["x1"] - line["x0"], rule[1] - rule[0], " ".join(text.split())[:30]
        fails += _centred(rule, line, label)
        if column == 1 and abs(length - width) > 0.5:
            fails.append("rule under %r is %.2f mm, its line %.2f mm" % (label, length, width))
        if column == 0 and not width / 3 - 0.5 <= length <= width / 2 + 0.5:
            fails.append("rule under %r is %.2f mm, not 1/3-1/2 of its line %.2f mm" % (label, length, width))
    if not case["titleRules"]:
        return fails
    page, after, pages = 1, -1.0, measure.page_count(pdf)
    cache = {}
    for text, expected in case["titleRules"]:
        label, found = " ".join(text.split())[:30], None
        while page <= pages:
            if page not in cache:
                cache[page] = (measure.horizontal_lines(pdf, page), measure.text_lines(pdf, page))
            found, _error = _ruled(cache[page][1], cache[page][0], text, after)
            if found:
                break
            page, after = page + 1, -1.0
        if not found:
            fails.append("ruled title %r or its rule not found" % label)
            break
        rule, block = found
        after = rule[2]
        fails += _centred(rule, max(block, key=lambda ln: ln["x1"] - ln["x0"]), label)
        if abs((rule[1] - rule[0]) - expected) > 0.5:
            fails.append("rule under %r on page %d is %.2f mm, the generator's %.2f mm" % (label, page, rule[1] - rule[0], expected))
    return fails
