# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: the characters and names of a formula's MathML and their LaTeX (mathml_to_tex)."""
import html.entities
import re

SYMBOLS = {
    "α": "\\alpha", "β": "\\beta", "γ": "\\gamma", "δ": "\\delta", "ε": "\\varepsilon", "ϵ": "\\epsilon",
    "ζ": "\\zeta", "η": "\\eta", "θ": "\\theta", "ϑ": "\\vartheta", "ι": "\\iota", "κ": "\\kappa", "λ": "\\lambda",
    "μ": "\\mu", "ν": "\\nu", "ξ": "\\xi", "π": "\\pi", "ϖ": "\\varpi", "ρ": "\\rho", "ϱ": "\\varrho", "σ": "\\sigma",
    "ς": "\\varsigma", "τ": "\\tau", "υ": "\\upsilon", "φ": "\\varphi", "ϕ": "\\phi", "χ": "\\chi", "ψ": "\\psi",
    "ω": "\\omega", "Γ": "\\Gamma", "Δ": "\\Delta", "Θ": "\\Theta", "Λ": "\\Lambda", "Ξ": "\\Xi", "Π": "\\Pi",
    "Σ": "\\Sigma", "Υ": "\\Upsilon", "Φ": "\\Phi", "Ψ": "\\Psi", "Ω": "\\Omega",
    "∞": "\\infty", "∅": "\\emptyset", "∇": "\\nabla", "∂": "\\partial", "∀": "\\forall", "∃": "\\exists",
    "∄": "\\nexists", "ℏ": "\\hbar", "ℓ": "\\ell", "ℵ": "\\aleph", "ℜ": "\\Re", "ℑ": "\\Im", "∠": "\\angle",
    "△": "\\triangle", "∘": "\\circ", "′": "'", "…": "\\ldots", "⋯": "\\cdots", "⋮": "\\vdots", "⋱": "\\ddots",
    "ℕ": "\\mathbb{N}", "ℤ": "\\mathbb{Z}", "ℚ": "\\mathbb{Q}", "ℝ": "\\mathbb{R}", "ℂ": "\\mathbb{C}",
    "≤": "\\le", "≥": "\\ge", "⩽": "\\leqslant", "⩾": "\\geqslant", "≠": "\\ne", "≈": "\\approx",
    "≡": "\\equiv", "∼": "\\sim", "≃": "\\simeq", "≅": "\\cong", "∝": "\\propto", "≪": "\\ll", "≫": "\\gg",
    "∈": "\\in", "∉": "\\notin", "∋": "\\ni", "⊂": "\\subset", "⊆": "\\subseteq", "⊃": "\\supset",
    "⊇": "\\supseteq", "⊄": "\\not\\subset", "∪": "\\cup", "∩": "\\cap", "∖": "\\setminus", "±": "\\pm",
    "∓": "\\mp", "⋅": "\\cdot", "·": "\\cdot", "×": "\\times", "÷": "\\div", "∗": "*", "−": "-", "⇒": "\\Rightarrow",
    "⇐": "\\Leftarrow", "⇔": "\\Leftrightarrow", "→": "\\to", "←": "\\leftarrow", "↔": "\\leftrightarrow",
    "↑": "\\uparrow", "↓": "\\downarrow", "⇌": "\\rightleftharpoons", "⊥": "\\perp", "∥": "\\parallel",
    "∣": "\\mid", "∤": "\\nmid", "¬": "\\neg", "∧": "\\wedge", "∨": "\\vee", "⊕": "\\oplus", "⊗": "\\otimes",
    "⊙": "\\odot", "⊖": "\\ominus", "∑": "\\sum", "∏": "\\prod", "∐": "\\coprod", "∫": "\\int", "∬": "\\iint",
    "∭": "\\iiint", "∮": "\\oint", "⋃": "\\bigcup", "⋂": "\\bigcap", "⟨": "\\langle", "⟩": "\\rangle",
    "⌊": "\\lfloor", "⌋": "\\rfloor", "⌈": "\\lceil", "⌉": "\\rceil", "{": "\\{", "}": "\\}", "‖": "\\|",
    "%": "\\%", "$": "\\$", "&": "\\&", "#": "\\#", "_": "\\_", "∴": "\\therefore", "∵": "\\because",
}
FUNCTIONS = frozenset(("sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth log ln lg exp det gcd "
                       "deg dim ker arg hom max min sup inf lim").split())
LIMITS = {"lim inf": "\\liminf", "lim sup": "\\limsup"}
BIG = frozenset(("∑", "∏", "∐", "∫", "∬", "∭", "∮", "⋃", "⋂"))
ACCENTS = {("⃗", True): "\\overrightarrow", ("⃗", False): "\\vec", ("→", True): "\\overrightarrow",
           ("^", True): "\\widehat", ("^", False): "\\hat", ("ˆ", False): "\\hat", ("ˆ", True): "\\widehat",
           ("¯", True): "\\overline", ("¯", False): "\\overline", ("˜", False): "\\tilde", ("~", True): "\\widetilde",
           ("˜", True): "\\widetilde", ("˙", False): "\\dot", ("¨", False): "\\ddot", ("ˇ", False): "\\check",
           ("˘", False): "\\breve", ("´", False): "\\acute", ("`", False): "\\grave", ("⌢", True): "\\overarc"}
FENCES = {"(": "(", ")": ")", "[": "[", "]": "]", "{": "\\{", "}": "\\}", "|": "|", "‖": "\\|", "⟨": "\\langle",
          "⟩": "\\rangle", "⌊": "\\lfloor", "⌋": "\\rfloor", "⌈": "\\lceil", "⌉": "\\rceil"}
NS = "{http://www.w3.org/1998/Math/MathML}"
SIMPLE_BASE = re.compile(r"[A-Za-z]|[0-9]+|\\[A-Za-z]+|\\mathbb\{[A-Z]\}")  # a script base that needs no braces
ALIGN = {"left": "l", "right": "r", "center": "c"}
TEXT_ESCAPES = str.maketrans({"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "%": "\\%", "$": "\\$", "&": "\\&",
                              "#": "\\#", "_": "\\_"})
ENTITY = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")
XML_ENTITIES = frozenset(("amp", "lt", "gt", "quot", "apos"))


def decode_entities(mathml):
    """The formula writes HTML names such as &infin; without declaring them: the characters, for an XML parser."""
    def character(match):
        name = match.group(1)
        if name in XML_ENTITIES or name not in html.entities.name2codepoint:
            return match.group(0)
        return chr(html.entities.name2codepoint[name])
    return ENTITY.sub(character, mathml)
