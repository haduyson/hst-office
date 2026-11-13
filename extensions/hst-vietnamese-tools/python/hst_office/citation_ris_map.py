# SPDX-License-Identifier: AGPL-3.0-only
"""RIS tag tables shared by the RIS importer and exporter (RIS as written by Scopus, Web of Science, Google
Scholar, Zotero, Mendeley, EndNote and doi.org)."""

TYPE_TO_CSL = {
    "JOUR": "article-journal", "JFULL": "article-journal", "EJOUR": "article-journal", "ABST": "article-journal",
    "INPR": "article-journal", "MGZN": "article-magazine", "NEWS": "article-newspaper", "BOOK": "book",
    "EBOOK": "book", "EDBOOK": "book", "WHOLE": "book", "CHAP": "chapter", "ECHAP": "chapter", "CONF": "paper-conference",
    "CPAPER": "paper-conference", "THES": "thesis", "RPRT": "report", "GOVDOC": "report", "STAND": "standard",
    "ELEC": "webpage", "WEB": "webpage", "BLOG": "post-weblog", "STAT": "legislation", "BILL": "bill",
    "LEGAL": "legislation", "CASE": "legal_case", "DATA": "dataset", "PAT": "patent", "MAP": "map",
    "COMP": "software", "DICT": "entry-dictionary", "ENCYC": "entry-encyclopedia", "UNPB": "manuscript",
    "MANSCPT": "manuscript", "PAMP": "pamphlet", "SER": "book", "GEN": "document", "CTLG": "document",
    "ICOMM": "personal_communication", "PCOMM": "personal_communication", "SLIDE": "speech", "VIDEO": "motion_picture",
}
CSL_TO_TYPE = {
    "article-journal": "JOUR", "article-magazine": "MGZN", "article-newspaper": "NEWS", "book": "BOOK",
    "chapter": "CHAP", "paper-conference": "CONF", "thesis": "THES", "report": "RPRT", "webpage": "ELEC",
    "post-weblog": "BLOG", "legislation": "STAT", "bill": "BILL", "legal_case": "CASE", "dataset": "DATA",
    "patent": "PAT", "map": "MAP", "software": "COMP", "entry-dictionary": "DICT", "entry-encyclopedia": "ENCYC",
    "manuscript": "UNPB", "pamphlet": "PAMP", "standard": "STAND", "personal_communication": "PCOMM",
    "motion_picture": "VIDEO", "speech": "SLIDE",
}
NAME_TAGS = {"AU": "author", "A1": "author", "A2": "editor", "ED": "editor", "A3": "collection-editor",
             "A4": "translator"}
TEXT_TAGS = {"TI": "title", "T1": "title", "CT": "title", "BT": "title", "T2": "container-title",
             "JO": "container-title", "JF": "container-title", "JA": "container-title-short",
             "J2": "container-title-short", "J1": "container-title-short", "T3": "collection-title",
             "VL": "volume", "IS": "issue", "CP": "issue", "PB": "publisher", "CY": "publisher-place",
             "PP": "publisher-place", "ET": "edition", "LA": "language", "AB": "abstract", "N2": "abstract",
             "M3": "genre", "ST": "title-short", "NV": "number-of-volumes", "SE": "section",
             "OP": "original-title", "UR": "URL", "L1": "URL", "L2": "URL", "LK": "URL", "DO": "DOI",
             "KW": "keyword", "M1": "number", "AN": "", "ID": "", "DB": "", "DP": "", "C1": "", "C2": "", "C3": "",
             "C4": "", "C5": "", "C6": "", "C7": "", "C8": "", "L3": "", "L4": "", "RN": "", "CN": "call-number",
             "CA": "", "U1": "", "U2": "", "U3": "", "U4": "", "U5": "", "M2": "", "AD": "", "RP": ""}
DATE_TAGS = ("PY", "Y1", "DA")
# tags written by the exporter, in order (TY first, ER last)
EXPORT_TEXT = (("title", "TI"), ("container-title", "T2"), ("container-title-short", "J2"),
               ("collection-title", "T3"), ("volume", "VL"), ("issue", "IS"), ("edition", "ET"),
               ("publisher", "PB"), ("publisher-place", "CY"), ("genre", "M3"), ("number", "M1"),
               ("language", "LA"), ("DOI", "DO"), ("URL", "UR"), ("abstract", "AB"), ("note", "N1"))
EXPORT_NAMES = (("author", "AU"), ("editor", "A2"), ("collection-editor", "A3"), ("translator", "A4"))
