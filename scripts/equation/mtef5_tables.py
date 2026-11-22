# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Character, operator and keyword tables used by the StarMath writer."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SYMBOLS = {
    '+': '+', '-': '-', '−': '-', '=': '=', '<': '<', '>': '>', '±': '+-', '∓': '-+',
    '×': 'times', '÷': 'div', '⋅': 'cdot', '∙': 'cdot', '·': 'cdot', '•': 'cdot',
    '≤': '<=', '≥': '>=', '≠': '<>', '≈': 'approx', '≡': 'equiv', '≅': 'simeq',
    '∼': 'sim', '∝': 'prop', '→': 'toward', '⇒': 'drarrow', '⇔': 'dlrarrow',
    '⇐': 'dlarrow', '↔': '"↔"', '←': '"←"', '∈': 'in', '∉': 'notin',
    '⊂': 'subset', '⊃': 'supset', '⊆': 'subseteq', '⊇': 'supseteq', '∩': 'intersection',
    '∪': 'union', '∅': 'emptyset', '∀': 'forall', '∃': 'exists', '∞': 'infinity',
    '∂': 'partial', '∇': 'nabla', '′': "'", '″': "''", '‴': "'''", '°': '"°"',
    '∠': '"∠"', '⊥': 'ortho', '∥': 'parallel', '‖': 'parallel', '…': 'dotsaxis',
    '⋯': 'dotsaxis', '⋮': 'dotsvert', '∧': 'and', '∨': 'or', '¬': 'neg',
    '∕': '/', '/': '/', '(': '(', ')': ')', '[': '[', ']': ']', '{': 'lbrace', '}': 'rbrace',
    '|': 'divides', '!': '!', ',': ',', ';': ';', ':': ':', '.': '.', '%': '%%', "'": "'", '*': '*',
    '∗': '*', '…': 'dotslow', '∘': 'circ', '⊕': 'oplus', '⊗': 'otimes',
    '⇌': '"⇌"', '⇄': '"⇄"', '⇆': '"⇆"', '⇀': '"⇀"', '⟶': 'toward',
    '↑': '"↑"', '↓': '"↓"', '∑': 'sum', '∏': 'prod', '∫': 'int',
    'ℵ': 'aleph', 'ℝ': 'setR', 'ℕ': 'setN', 'ℤ': 'setZ', 'ℚ': 'setQ', 'ℂ': 'setC',
    '∴': '"∴"', '∵': '"∵"', '△': '"△"', '∆': '%DELTA', 'Δ': '%DELTA',
    '∓': '-+', '≪': '<<', '≫': '>>', '≃': 'simeq', '≙': '"≙"', '≒': '"≒"',
    '≦': '<=', '≧': '>=', '⩽': 'leslant', '⩾': 'geslant', '≮': '"≮"',
    '⊄': 'nsubset', '⊅': 'nsupset', '⊈': 'nsubseteq', '⊉': 'nsupseteq', '∋': 'owns',
    '∖': 'setminus', '∣': 'divides', '∤': 'ndivides', '⋂': 'Intersection', '⋃': 'Union',
    '#': '"#"', '&': '"&"', '@': '"@"', '~': '"~"', '^': '"^"', '_': '"_"', '\\': 'setminus', '"': '"\\""',
    '⌒': '"⌒"', '⌢': '"⌢"', '○': '"○"', '≡': 'equiv', '≅': 'simeq',
}
# MathType private-use code points (MT Extra and spacing) and what they mean
MT_PUA = {
    0xEF00: '', 0xEF01: '`', 0xEF02: '`', 0xEF03: '`', 0xEF04: '~', 0xEF05: '~', 0xEF06: '~~', 0xEF07: '',
    0xEF08: '~', 0xEB00: '', 0xEB01: '', 0xEB02: '', 0xEC00: '"→"',
    0xE98F: 'toward', 0xE990: '"←"', 0xE991: '"↔"', 0xE998: '"⇌"', 0xE999: '"⇌"',
    0xE99A: '"⇄"', 0xE99B: '"⇄"', 0xEB05: "'", 0xE934: '"⌒"', 0xE95C: '"⌒"',
    0xEE04: '', 0xEE05: '', 0xEE06: '', 0xEE07: '', 0xEE08: '', 0xEE09: '', 0xEE0A: '', 0xEE0B: '',
    0xEE0C: '', 0xEE0D: '', 0xEE0E: '', 0xEE0F: '', 0xEE10: '', 0xEE11: '', 0xEE18: '',
}
BINARY = {'=', '<', '>', '<=', '>=', '<>', 'approx', 'equiv', 'simeq', 'sim', 'prop', 'toward', 'drarrow',
          'dlrarrow', 'dlarrow', 'in', 'notin', 'subset', 'supset', 'subseteq', 'supseteq', 'nsubset', 'nsupset',
          'nsubseteq', 'nsupseteq', 'owns', 'times', 'cdot', 'div', 'divides', 'ndivides', 'intersection', 'union',
          'and', 'or', 'ortho', 'parallel', '/', 'setminus', 'circ', 'oplus', 'otimes', '<<', '>>', 'leslant',
          'geslant', '*'}
KEYWORDS = set(open(os.path.join(HERE, 'starmath-keywords.txt')).read().lower().split())
UNARY = {'+', '-', '+-', '-+', 'neg'}
FUNCS = {'sin', 'cos', 'tan', 'cot', 'sinh', 'cosh', 'tanh', 'coth', 'arcsin', 'arccos', 'arctan', 'arccot',
         'ln', 'log', 'exp', 'lim', 'max', 'min', 'det', 'deg', 'dim', 'ker', 'gcd', 'sup', 'inf'}
SM_FUNCS = {'sin', 'cos', 'tan', 'cot', 'sinh', 'cosh', 'tanh', 'coth', 'arcsin', 'arccos', 'arctan', 'arccot',
            'ln', 'log', 'exp'}
GREEK_UC = {'Γ': 'GAMMA', 'Δ': 'DELTA', 'Θ': 'THETA', 'Λ': 'LAMBDA', 'Ξ': 'XI',
            'Π': 'PI', 'Σ': 'SIGMA', 'Υ': 'UPSILON', 'Φ': 'PHI', 'Ψ': 'PSI', 'Ω': 'OMEGA'}
EMBELL = {2: 'dot', 3: 'ddot', 4: 'dddot', 8: 'tilde', 9: 'hat', 11: 'vec', 14: 'harpoon', 16: 'overstrike',
          17: 'bar', 20: 'breve', 29: 'underline'}
PRIMES = {5: "'", 6: "''", 18: "'''"}
_VN = None


def legacy_maps():
    global _VN
    if _VN is None:
        p = os.environ.get('HST_VN_MAPS', os.path.join(HERE, '..', '..', 'data', 'vietnamese', 'encoding-maps.json'))
        _VN = json.load(open(p))['encodings']
    return _VN


def is_viet(ch):
    o = ord(ch)
    return (0xC0 <= o <= 0x1B0 and ch.isalpha()) or 0x1EA0 <= o <= 0x1EF9


def quote(s):
    # StarMath strings only escape the double quote; a backslash cannot be written safely,
    # so it becomes the set-minus glyph that looks the same
    return '"' + s.replace('\\', '∖').replace('"', '\\"') + '"'
