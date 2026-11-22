# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Accuracy metrics of the OCR benchmark: character error rate, formula token error, table cell scores."""
import difflib
import re
import unicodedata


def edit_distance(a, b):
    """Levenshtein distance between two sequences (strings or token lists)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm_text(text):
    """NFC, unify dashes/quotes/minus, collapse whitespace: layout differences are not recognition errors."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("−", "-").replace("–", "-").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def cer(truth, hyp):
    truth, hyp = norm_text(truth), norm_text(hyp)
    return edit_distance(truth, hyp) / max(1, len(truth))


def wer(truth, hyp):
    t, h = norm_text(truth).split(), norm_text(hyp).split()
    return edit_distance(t, h) / max(1, len(t))


def diacritic_errors(truth, hyp):
    """Share of words, among aligned word pairs that are equal once Vietnamese marks are removed, whose marks are
    wrong (e.g. "thẳng" read as "thằng"). Measures tone/vowel-mark mistakes apart from other errors."""
    t, h = norm_text(truth).split(), norm_text(hyp).split()
    wrong = total = 0
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, t, h, autojunk=False).get_opcodes():
        pairs = zip(t[a1:a2], h[b1:b2]) if op in ("equal", "replace") and a2 - a1 == b2 - b1 else ()
        for wt, wh in pairs:
            if "".join(map(strip_marks, wt)) == "".join(map(strip_marks, wh)):
                total += 1
                wrong += wt != wh
    return wrong / max(1, total)


def strip_marks(ch):
    base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
    return "d" if base == "đ" else ("D" if base == "Đ" else base)


TOKEN = re.compile(r"\\[A-Za-z]+|\\.|[A-Za-z0-9]|[^\sA-Za-z0-9]")
NOISE = {r"\,", r"\;", r"\!", r"\:", r"\ ", r"\quad", r"\qquad", r"\left", r"\right", r"\displaystyle",
         r"\mathrm", r"\operatorname", r"\textstyle", r"\scriptstyle", r"\big", r"\Big", r"\bigl", r"\bigr"}
SAME = {r"\le": r"\leq", r"\ge": r"\geq", r"\to": r"\rightarrow", r"\ne": r"\neq", r"\lvert": "|", r"\rvert": "|",
        r"\vert": "|", r"\dots": r"\ldots", r"\cdots": r"\ldots"}


REWRITES = ((re.compile(r"\\operatorname\*?\{(lim|sin|cos|tan|log|ln|max|min)\}"), r"\\\1"),
            (re.compile(r"\^\{?\\prime\}?"), "'"),
            (re.compile(r"[\s,.;]*(\\[,;! ]\s*)*[.,]?\s*$"), ""))  # trailing punctuation/spacing after the formula


def latex_tokens(latex):
    """Tokens with presentation-only commands dropped and synonyms unified (\\operatorname*{lim} = \\lim,
    ^{\\prime} = ', a trailing "\\,." dropped)."""
    for pattern, repl in REWRITES:
        latex = pattern.sub(repl, latex)
    out = []
    for tok in TOKEN.findall(latex):
        if tok in NOISE:
            continue
        out.append(SAME.get(tok, tok))
    return out


def formula_scores(truth, hyp):
    """(token error rate, exact match), both on normalised tokens without grouping braces: x^{2} and x^2 are the
    same formula, and HST's TeX converter reads both."""
    t = [x for x in latex_tokens(truth) if x not in "{}"]
    h = [x for x in latex_tokens(hyp) if x not in "{}"]
    return edit_distance(t, h) / max(1, len(t)), t == h


def table_scores(truth_rows, hyp_rows):
    """(shape matches, cell text CER over aligned cells, share of cells exactly right)."""
    shape = len(truth_rows) == len(hyp_rows) and all(len(a) == len(b) for a, b in zip(truth_rows, hyp_rows))
    t_cells = [c for r in truth_rows for c in r]
    h_cells = [c for r in hyp_rows for c in r] if shape else []
    if not shape:
        joined_t = " ".join(t_cells)
        joined_h = " ".join(c for r in hyp_rows for c in r)
        return False, cer(joined_t, joined_h), 0.0
    errs = sum(edit_distance(norm_text(a), norm_text(b)) for a, b in zip(t_cells, h_cells))
    exact = sum(norm_text(a) == norm_text(b) for a, b in zip(t_cells, h_cells))
    return True, errs / max(1, sum(len(norm_text(c)) for c in t_cells)), exact / len(t_cells)
