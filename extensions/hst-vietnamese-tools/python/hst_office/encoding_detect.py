# SPDX-License-Identifier: AGPL-3.0-only
"""Suggest a legacy encoding by testing whether converted words look like Vietnamese syllables (pure logic).

The result is advice only: the wizard shows it, the user must still choose the encoding explicitly. Both TCVN3
and VNI reuse the same high bytes, so a wrong choice yields garbage syllables; syllable plausibility (known vowel
clusters, finals, and the rule that c/ch/p/t finals only carry the sac or nang tone) separates them.
"""
import re
import unicodedata

from .data_files import load_data
from .encoding import Converter, has_vietnamese_unicode

_ONSET = r"(?:ngh|gh|gi|ch|kh|ng|nh|ph|qu|th|tr|[bcdđghklmnpqrstvx])?"
_NUCLEI = ("a ă â e ê i o ô ơ u ư y ai ao au ay âu ây eo êu ia iê iu oa oă oe oi ôi ơi ua uâ uê ui uô uơ uy ưa ưi ưu ươ yê "
           "iêu oai oay uây uôi ươi ươu uyê uya ya yêu oeo").split()
_SYLLABLE = re.compile("^%s(%s)(ch|ng|nh|[cmnpt])?$" % (_ONSET, "|".join(sorted(_NUCLEI, key=len, reverse=True))))
_TONES = {"̀": "huyen", "́": "sac", "̃": "nga", "̉": "hoi", "̣": "nang"}


def _split_tone(word):
    tone, base = None, []
    for ch in unicodedata.normalize("NFD", word.lower()):
        if ch in _TONES:
            tone = _TONES[ch]
        else:
            base.append(ch)
    return unicodedata.normalize("NFC", "".join(base)), tone


def is_plausible_syllable(word):
    base, tone = _split_tone(word)
    m = _SYLLABLE.match(base)
    if not m:
        return False
    return not (m.group(2) in ("c", "ch", "p", "t") and tone not in (None, "sac", "nang"))


def _score(text, key, data):
    converted, _ = Converter(key, data).convert(text)
    words = [w for w in re.findall(r"[^\W\d_]+", converted) if len(w) > 0]
    return (sum(is_plausible_syllable(w) for w in words) / len(words)) if words else 0.0, len(words)


def suggest(text, data=None):
    """Return {'candidates': [{'encoding','score','words','confidence'}], 'ambiguous': bool, 'looks_unicode': bool,
    'best': key or None}. 'best' is only a suggestion; callers must not convert without explicit user choice."""
    data = data or load_data("encoding-maps.json")
    looks_unicode = has_vietnamese_unicode(text)
    rows = []
    for key in data["encodings"]:
        score, words = _score(text, key, data)
        rows.append({"encoding": key, "score": round(score, 3), "words": words, "confidence": "none"})
    rows.sort(key=lambda r: -r["score"])
    top, second = rows[0], rows[1] if len(rows) > 1 else {"score": 0.0}
    changed = any(Converter(k, data).convert(text)[0] != text for k in data["encodings"])
    ambiguous = looks_unicode or not changed or top["score"] < 0.8 or second["score"] >= 0.8
    if not ambiguous:
        top["confidence"] = "high" if top["words"] >= 5 and second["score"] <= 0.5 else "medium"
    elif changed and not looks_unicode and top["score"] >= 0.5:
        top["confidence"] = "low"
    return {"candidates": rows, "ambiguous": ambiguous, "looks_unicode": looks_unicode,
            "best": top["encoding"] if top["confidence"] != "none" else None}
