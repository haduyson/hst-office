# SPDX-License-Identifier: AGPL-3.0-only
"""Chuyển TeX ⇄ công thức: the LaTeX commands exam papers use and the formula language words they become.

Each table maps a LaTeX command name (without its backslash) to the formula text. The kinds tell the converter how
the piece joins its neighbours: an ordinary piece (letters, numbers, symbols), a binary operator, a relation, a
function name, or a big operator whose limits go below and above. tex_to_starmath builds the formula from them;
starmath_tex reads the same tables backwards."""

GREEK = ("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi omicron pi "
         "varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega").split()
GREEK_UPPER = "Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega".split()

ORDINARY = {name: "%" + name for name in GREEK}
ORDINARY.update({name: "%" + name.upper() for name in GREEK_UPPER})
ORDINARY.update({
    "infty": "infinity", "emptyset": "emptyset", "varnothing": "emptyset", "nabla": "nabla", "partial": "partial",
    "forall": "forall", "exists": "exists", "nexists": "notexists", "hbar": "hbar", "ell": "\"ℓ\"",
    "aleph": "aleph", "Re": "Re", "Im": "Im", "wp": "wp",
    "angle": "∠", "triangle": "\"△\"", "square": "\"□\"", "degree": "\"°\"", "circ": "circ", "prime": "′",
    "dots": "dotslow", "ldots": "dotslow", "cdots": "dotsaxis", "vdots": "dotsvert", "ddots": "dotsdown",
    "%": "\"%\"", "$": "\"$\"", "&": "\"&\"", "#": "\"#\"", "_": "\"_\"",
    "backslash": "\"∖\"", "lbrace": "\\lbrace", "rbrace": "\\rbrace", "{": "\\lbrace", "}": "\\rbrace",
    "langle": "\\langle", "rangle": "\\rangle", "lfloor": "\\lfloor", "rfloor": "\\rfloor",
    "lceil": "\\lceil", "rceil": "\\rceil", "|": "\\ldline", "vert": "\\lline", "Vert": "\\ldline",
    "therefore": "\"∴\"", "because": "\"∵\"", "star": "\"⋆\"", "ast": "\"*\"", "frown": "\"⌢\"",
})

BINARY = {
    "pm": "+-", "mp": "-+", "cdot": "cdot", "times": "times", "div": "div", "cup": "union",
    "cap": "intersection", "setminus": "setminus", "wedge": "and", "land": "and", "vee": "or", "lor": "or",
    "oplus": "oplus", "ominus": "ominus", "otimes": "otimes", "odot": "odot", "bullet": "\"•\"",
}

RELATION = {
    "le": "<=", "leq": "<=", "leqslant": "leslant", "ge": ">=", "geq": ">=", "geqslant": "geslant",
    "ne": "<>", "neq": "<>", "approx": "approx", "equiv": "equiv", "sim": "sim", "simeq": "simeq", "cong": "\"≅\"",
    "propto": "prop", "ll": "ll", "gg": "gg", "lt": "<", "gt": ">",
    "in": "in", "notin": "notin", "ni": "owns", "subset": "subset", "subseteq": "subseteq", "supset": "supset",
    "supseteq": "supseteq", "not\\subset": "nsubset", "nsubseteq": "nsubseteq",
    "Rightarrow": "drarrow", "implies": "drarrow", "Leftarrow": "dlarrow", "Leftrightarrow": "dlrarrow",
    "iff": "dlrarrow", "to": "toward", "rightarrow": "toward", "longrightarrow": "toward", "leftarrow": "leftarrow",
    "gets": "leftarrow", "leftrightarrow": "\"↔\"", "mapsto": "\"↦\"", "uparrow": "uparrow",
    "downarrow": "downarrow", "parallel": "parallel", "perp": "ortho", "mid": "divides", "nmid": "ndivides",
    "rightleftharpoons": "\"⇌\"", "longleftrightarrow": "dlrarrow", "Longrightarrow": "drarrow",
    "Longleftrightarrow": "dlrarrow",
}

NEGATED = {"=": "<>", "in": "notin", "subset": "nsubset", "subseteq": "nsubseteq", "mid": "ndivides",
           "equiv": "\"≢\"", "parallel": "\"∦\""}

FUNCTION = ("sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth log ln lg exp det gcd deg dim ker arg "
            "hom").split()
OWN_FUNCTION = {"sin", "cos", "tan", "cot", "sinh", "cosh", "tanh", "coth", "arcsin", "arccos", "arctan", "log",
                "ln", "exp"}  # formula words; the others are written func name
LIMIT_FUNCTION = ("max", "min", "sup", "inf", "lim", "liminf", "limsup")  # limits go below in display
BIG_OPERATOR = {"sum": "sum", "prod": "prod", "coprod": "coprod", "int": "int", "iint": "iint", "iiint": "iiint",
                "oint": "lint", "bigcup": "oper ⋃", "bigcap": "oper ⋂", "lim": "lim", "liminf": "liminf",
                "limsup": "limsup"}

ACCENT = {"vec": "vec", "overrightarrow": "widevec", "overline": "overline", "bar": "bar", "underline": "underline",
          "hat": "hat", "widehat": "widehat", "tilde": "tilde", "widetilde": "widetilde", "dot": "dot",
          "ddot": "ddot", "check": "check", "breve": "breve", "acute": "acute", "grave": "grave",
          "overarc": "widearc", "wideparen": "widearc", "overparen": "widearc", "arc": "widearc"}

FONT = {"mathrm": "nitalic", "mathit": "ital", "mathbf": "bold", "boldsymbol": "bold", "bm": "bold",
        "mathsf": "font sans", "mathtt": "font fixed", "operatorname": "func"}
TEXT = {"text": "", "textrm": "", "mbox": "", "textnormal": "", "textup": "", "textbf": "bold ", "textit": "ital "}
DOUBLE_STRUCK = {chr(ord("A") + i): chr(0x1D538 + i) for i in range(26)}
DOUBLE_STRUCK.update({"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"})

SPACE = {",": "`", ":": "`", ";": "`", ">": "`", " ": "~", "quad": "~", "qquad": "~~", "enspace": "`",
         "thinspace": "`", "!": "", "negthinspace": "", "nobreakspace": "~"}
IGNORED = ("displaystyle textstyle scriptstyle limits nolimits nonumber notag hline middle big Big bigg Bigg "
           "bigl Bigl biggl Biggl bigr Bigr biggr Biggr").split()

# \left X and \right X
OPEN_FENCE = {"(": "(", "[": "[", "\\{": "lbrace", "\\lbrace": "lbrace", "|": "lline", "\\|": "ldline",
              "\\vert": "lline", "\\Vert": "ldline", "\\langle": "langle", "\\lfloor": "lfloor",
              "\\lceil": "lceil", ".": "none", "]": "]", ")": ")", "\\}": "rbrace"}
CLOSE_FENCE = {")": ")", "]": "]", "\\}": "rbrace", "\\rbrace": "rbrace", "|": "rline", "\\|": "rdline",
               "\\vert": "rline", "\\Vert": "rdline", "\\rangle": "rangle", "\\rfloor": "rfloor",
               "\\rceil": "rceil", ".": "none", "[": "[", "(": "(", "\\{": "lbrace"}

# environments: (left fence, right fence) around the rows
MATRIX_FENCES = {"matrix": None, "smallmatrix": None, "pmatrix": ("(", ")"), "bmatrix": ("[", "]"),
                 "Bmatrix": ("lbrace", "rbrace"), "vmatrix": ("lline", "rline"), "Vmatrix": ("ldline", "rdline"),
                 "cases": ("lbrace", "none"), "array": None, "aligned": None, "align": None, "align*": None,
                 "alignedat": None, "split": None, "gathered": None, "gather": None, "gather*": None,
                 "eqnarray": None, "eqnarray*": None}

# letter runs that are formula words: written letter by letter so that "in" stays i n and not ∈
KEYWORDS = frozenset((
    "abs and approx arccos arccosh arccot arccoth arcsin arcsinh arctan arctanh acute aleph alignb alignc alignl "
    "alignm alignr alignt alignx bar binom black blue bold boper breve bslash cdot check circ circle color coprod "
    "cos cosh cot coth csub csup cyan dddot ddot def det div divides dlarrow dlrarrow dot dotsaxis dotsdiag dotsdown "
    "dotslow dotsup dotsvert downarrow drarrow emptyset equiv evaluate exists exp fact fixed font forall from func "
    "ge geslant gg grave green gt hat hbar iiint iint im in infinity infty int intersection ital italic lambdabar "
    "langle lbrace lceil ldbracket ldline le left leftarrow leslant lfloor lim liminf limsup lint ll lline llint "
    "lllint ln log lsub lsup lt magenta matrix minusplus mline nabla nbold ndivides neg neq newline ni nitalic none "
    "nospace notexists notin nroot nsubset nsubseteq nsupset nsupseteq odivide odot ominus oper oplus or ortho "
    "otimes over overbrace overline overstrike owns parallel partial phantom plusminus prec preccurlyeq precsim "
    "prod prop rangle rbrace rceil rdbracket rdline red Re rfloor right rightarrow rline rsub rsup sans serif "
    "setC setminus setN setQ setquotient setR setZ sim simeq sin sinh size slash sqrt stack sub subset subseteq "
    "succ sup supset supseteq tan tanh tilde times to toward transl transr underbrace underline union uoper "
    "uparrow vec white widebslash widehat widetilde wideslash widevec wp yellow widearc xrightarrow xleftarrow"
).split())
