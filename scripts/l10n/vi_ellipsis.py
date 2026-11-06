# SPDX-License-Identifier: AGPL-3.0-only
"""No trailing "..." / "…" on Vietnamese UI labels (owner rule 2026-11-06).

In the Vietnamese UI a label does not end with an ellipsis just to say that a dialog follows:
"Thuộc tính..." is shown as "Thuộc tính". Only a trailing ellipsis (ASCII "..." or "…", with an
optional space before it) is removed; access-key markers stay where they are. category() keeps it when it is not
such a marker (counted per category by the report):
  progress  in-progress status ("Đang tải…", "Đợi…", STR_STATSTR_*): the work is ongoing;
  text      help pages and tips of the day, sentences and messages (data/l10n/vi-ellipsis-keep.json);
  omitted   the ellipsis stands for omitted content ("1, 2, 3, ...", "Thay thế 1/2 ... bằng ½ ...");
  glyph     the ellipsis is the whole label (a "..." browse button).
Everything else is a label ("label"). Run-time truncation is drawn by VCL and is not in the .po files.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEEP = os.path.join(ROOT, "data", "l10n", "vi-ellipsis-keep.json")
TRAILING = re.compile(r"[  ]?(?:\.{3,}|…+)$")
PROGRESS_VI = re.compile(r"^(Đang|Đợi|Chờ|Vui lòng chờ|Xin chờ)\b")
PROGRESS_EN = re.compile(r"^(Loading|Saving|Solving|Searching|Inserting|Checking|Downloading|Connecting|Duplicating|"
                         r"Deleting|Optimizing|Creating|Removing|Gathering|Compiling|Importing|Exporting|Formatting|"
                         r"Updating|Installing|Waiting|Sending|Preparing|Processing|Converting|Signing)\b")
_KEEP = None


def strip(text):
    """Text without its trailing ellipsis (and the space before it)."""
    return TRAILING.sub("", text)


def keep_list(path=KEEP):
    global _KEEP
    if _KEEP is None or path != KEEP:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        _KEEP = {(e["file"], e["msgctxt"]): e["category"] for e in data["keep"]}
    return _KEEP


def category(file, msgctxt, msgid, msgstr, keep=None):
    """None when msgstr has no trailing ellipsis, "label" when it must go, else the reason to keep it."""
    body = strip(msgstr)
    if body == msgstr:
        return None
    plain = re.sub(r"[~_&]", "", body).strip()
    command = file.endswith("Office/UI.po") or "menu" in msgctxt.split("|")[0].lower()
    listed = (keep if keep is not None else keep_list()).get((file, msgctxt))
    if listed:
        return listed
    if not re.search(r"\w", plain):
        return "glyph"
    if file.startswith("helpcontent2/") or msgctxt.startswith("RID_CUI_TIPOFTHEDAY"):
        return "text"
    if re.search(r"\.\.|…", body) or plain.endswith(","):
        return "omitted"
    if (PROGRESS_VI.match(plain) or msgctxt.startswith("STR_STATSTR")
            or (not command and PROGRESS_EN.match(re.sub(r"[~_&]", "", msgid)))):
        return "progress"
    return "label"


def fix(file, msgctxt, msgid, msgstr, keep=None):
    """msgstr with the ellipsis removed when category() says it is a label."""
    return strip(msgstr) if category(file, msgctxt, msgid, msgstr, keep) == "label" else msgstr


_STRING = re.compile(r'^(msgstr(?:\[0\])? )?"(.*)"$')


def normalize_po(path, rel, keep_lines=frozenset(), counts=None):
    """Remove label ellipses from every msgstr of a .po in place. Lines that an HST patch adds or keeps as
    context are left alone. Return (changed, kept_for_patches); counts[category] += 1 for every ellipsis."""
    from po_io import parse_block, read_blocks
    blocks = read_blocks(path)
    changed = kept = 0
    keep = keep_list()
    for index, block in enumerate(blocks):
        entry = parse_block(block)
        if not entry or not entry["msgid"] or entry["fuzzy"]:
            continue
        kind = category(rel, entry["msgctxt"], entry["msgid_plural"] or entry["msgid"], entry["msgstr"], keep)
        if kind is None:
            continue
        if counts is not None:
            counts[kind] = counts.get(kind, 0) + 1
        if kind != "label":
            continue
        lines = block.split("\n")
        start = next(i for i, line in enumerate(lines) if line.startswith("msgstr"))
        last = start
        while last + 1 < len(lines) and lines[last + 1].startswith('"'):
            last += 1
        match = _STRING.match(lines[last])
        if not match or not TRAILING.search(match.group(2)):
            continue  # the ellipsis is split over two lines: leave it (none known)
        new = (match.group(1) or "") + '"' + strip(match.group(2)) + '"'
        if lines[last] in keep_lines:
            kept += 1
            continue
        lines[last] = new
        blocks[index] = "\n".join(lines)
        changed += 1
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n\n".join(blocks))
    return changed, kept


def normalize_ellipsis(tree, patches):
    """Label ellipses removed from every Vietnamese .po, after the overrides and the term replacements."""
    from vi_terms import normalize_tree
    counts = {}
    status = normalize_tree(tree, patches, "ellipsis",
                            lambda path, rel, keep: normalize_po(path, rel, keep, counts))
    print("ellipsis kept: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()) if k != "label"))
    return status
