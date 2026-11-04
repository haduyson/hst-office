# SPDX-License-Identifier: AGPL-3.0-only
"""New-style Vietnamese tone placement on the oa, oe and uy rhymes, as the glossary requires.

At the end of a syllable the old style puts the tone on the second vowel (Xoá, hoà, khoẻ,
huỷ, Tuỳ); HST Office writes it on the first one (Xóa, hòa, khỏe, hủy, Tùy), like "Hủy".
A syllable that continues after the rhyme (toán, hoàn, khoảng) is the same in both styles,
and "qu" + y (quý) is not the uy rhyme. Access-key markers (_ ~) count as part of a word.
"""
import re
import unicodedata

TONES = "̣́̀̉̃"
LETTER = r"A-Za-zÀ-ɏḀ-ỿ_~"
_RHYME = re.compile(r"(?<![" + LETTER + r"])([" + LETTER + r"]*?)([oOuU])"
                    r"([áàảãạÁÀẢÃẠéèẻẽẹÉÈẺẼẸýỳỷỹỵÝỲỶỸỴ])(?![" + LETTER + r"])")
_VOWELS = "aeiouyăâêôơư"


def _move(match):
    head, vowel, toned = match.groups()
    decomposed = unicodedata.normalize("NFD", toned)
    base, tone = decomposed[0], "".join(c for c in decomposed[1:] if c in TONES)
    pair = vowel.lower() + base.lower()
    if (pair not in ("oa", "oe", "uy") or not tone
            or (pair == "uy" and head[-1:].lower() == "q")
            or (head and head[-1].lower() in _VOWELS)):
        return match.group(0)
    if head[-1:] in ("_", "~"):  # "X~oá": keep an ASCII access key, on the vowel after the tone
        return head[:-1] + unicodedata.normalize("NFC", vowel + tone) + head[-1] + base
    return head + unicodedata.normalize("NFC", vowel + tone) + base


def fix(text):
    """Text with old-style oa/oe/uy tones moved to the new style."""
    new = _RHYME.sub(_move, text)
    if new == text and unicodedata.normalize("NFC", text) != text:
        composed = unicodedata.normalize("NFC", text)  # e.g. "Uỷ" typed as U + y + combining hook
        fixed = _RHYME.sub(_move, composed)
        return fixed if fixed != composed else text
    return new


def normalize_po(path):
    """Apply fix() to every msgstr of a .po file in place; return the number of changed lines."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    changed, in_msgstr = 0, False
    start = lines.index("") if "" in lines else 0  # leave the header entry (translator names) alone
    for index, line in enumerate(lines[start:], start):
        if line.startswith("msgstr"):
            in_msgstr = True
        elif not line.startswith('"'):
            in_msgstr = False
        if in_msgstr:
            new = fix(line)
            if new != line:
                lines[index], changed = new, changed + 1
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    return changed
