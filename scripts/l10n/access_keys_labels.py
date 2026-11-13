# SPDX-License-Identifier: AGPL-3.0-only
"""Labels and mnemonics of check-access-keys.py: PO escaping, the access key of a label, the label shown."""
import ast
import json
from pathlib import Path
import re

OOR = "{http://openoffice.org/2001/registry}"
MENU = "{http://openoffice.org/2001/menu}"
LANG = "{http://www.w3.org/XML/1998/namespace}lang"
UI_PO = "officecfg/registry/data/org/openoffice/Office/UI.po"


def unescape(value):
    return ast.literal_eval('"' + value + '"')


def escape(value):
    return json.dumps(value, ensure_ascii=False)[1:-1]


def mnemonic(label, markers="~"):
    index = 0
    while index + 1 < len(label):
        if label[index] in markers:
            if label[index + 1] != label[index]:
                return label[index + 1]
            index += 1
        index += 1
    return ""


def strip_mnemonics(label):
    # MnemonicGenerator::EraseAllMnemonicChars also removes CJK (~A) suffixes.
    return re.sub(r"\(~[A-Za-z]\)", "", label).replace("~", "")


def load_overrides(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[(row["file"], unescape(row["msgctxt"]),
                    row.get("msgid_new") or row["msgid"])] = row["msgstr"]
    return result


def label_text(source, overrides, english=False):
    if english:
        text = source["english"]
    else:
        key = (source["file"], source["msgctxt"], source["msgid"])
        vi = overrides.get(key, "" if source["fuzzy"] else source["vi"])
        text = unescape(vi) if vi else source["english"]
    text = text.replace("%PRODUCTNAME", "HST Office")
    return strip_mnemonics(text.rstrip(".")) if source.get("name") else text


def resolve(item, overrides, english=False):
    for source in item["labels"]:
        text = label_text(source, overrides, english)
        if text:
            return text, source["markers"]
    return "", "~"
