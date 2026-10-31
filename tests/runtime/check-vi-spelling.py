# SPDX-License-Identifier: AGPL-3.0-only
"""Check Vietnamese spell checking on a real HST Office build (fresh profile, vi-VN).

Usage: python3 tests/runtime/check-vi-spelling.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/vi-spelling] [--display :97] [--port 23984]

Asks the linguistic SpellChecker service (the one Writer, Calc and Impress use) about every
word of a Vietnamese paragraph. None may be reported as misspelled, whether the text is
precomposed (NFC), decomposed (NFD) or mixed word by word, and in both tone placements
(hóa/hoá, khỏe/khoẻ, thủy/thuỷ, tùy/tuỳ). Non-words must still be reported. Also checks that
automatic spell checking is off on a fresh profile. Exit 1 when a check fails.
"""
import argparse
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
PARAGRAPH = (
    "Vai trò cốt lõi của chuỗi cung ứng thông minh đối với được thể hiện qua 3 trụ cột chiến lược. "
    "Tạo lập Lợi thế Cạnh tranh Bền vững. Tối ưu hóa Tổng chi phí sở hữu, rút ngắn thời gian đưa sản phẩm "
    "ra thị trường, và gia tăng năng lực tùy biến sản phẩm theo nhu cầu địa phương. "
    "Đảm bảo Tính Linh hoạt và Khả năng Chống chịu. Khả năng chủ động ứng phó, tự điều chỉnh trước các "
    "biến động tức thời của thị trường hoặc rủi ro đứt gãy địa chính trị mà không làm gián đoạn chuỗi giá trị "
    "toàn cầu. Động lực Tăng trưởng Doanh thu. Chuỗi cung ứng hiệu quả nâng cao chỉ số đáp ứng đơn hàng "
    "đúng hạn và đủ số lượng, tối ưu hóa trải nghiệm khách hàng, trực tiếp gia tăng phần thị trường."
)
# Both placements of the tone mark in open oa/oe/uy syllables (new style on the second vowel, old on the first).
TONE_STYLES = "hoá hóa hoà hòa hoả hỏa khoẻ khỏe khoá khóa thuỷ thủy thuý thúy tuỳ tùy tuỷ tủy toà tòa xoá xóa uỷ ủy huỷ hủy"
NON_WORDS = "xyzq hoaz khóaa tùyy"


def words(text):
    return [w.strip(".,;:") for w in text.split() if w.strip(".,;:") and not w.strip(".,;:").isdigit()]


def mixed(word_list):
    """Alternate NFC and NFD word by word, the way pasted text often arrives."""
    return [unicodedata.normalize("NFD" if i % 2 else "NFC", w) for i, w in enumerate(word_list)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/vi-spelling"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--port", type=int, default=23984)
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    import uno
    office = hst_gui.Office(args.instdir, os.path.abspath(args.out), args.port, display=args.display).start()
    results, failed = {}, 0

    def record(name, bad, expect_bad=False):
        nonlocal failed
        ok = (bool(bad) == expect_bad) if not expect_bad else (len(bad) == len(NON_WORDS.split()))
        failed += not ok
        results[name] = {"status": "PASS" if ok else "FAIL", "flagged": bad}
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  flagged: {bad}" if bad else ""))

    try:
        checker = office.service("com.sun.star.linguistic2.SpellChecker")
        loc = uno.createUnoStruct("com.sun.star.lang.Locale")
        loc.Language, loc.Country = "vi", "VN"

        def flagged(word_list):
            return [unicodedata.normalize("NFC", w) for w in word_list if not checker.isValid(w, loc, ())]

        base = words(PARAGRAPH)
        for form in ("NFC", "NFD"):
            record(f"paragraph {form}", flagged([unicodedata.normalize(form, w) for w in base]))
        record("paragraph mixed NFC/NFD", flagged(mixed(base)))
        styles = TONE_STYLES.split()
        for form in ("NFC", "NFD"):
            record(f"tone placements {form}", flagged([unicodedata.normalize(form, w) for w in styles]))
        record("non-words are still flagged", flagged(NON_WORDS.split()), expect_bad=True)
        props = office.service("com.sun.star.linguistic2.LinguProperties")
        auto = props.getPropertyValue("IsSpellAuto")
        failed += bool(auto)
        results["IsSpellAuto is off on a fresh profile"] = {"status": "FAIL" if auto else "PASS", "actual": auto}
        print(f"{'FAIL' if auto else 'PASS'}  IsSpellAuto is off on a fresh profile (actual {auto})")
    finally:
        office.stop()
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
