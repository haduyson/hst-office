# SPDX-License-Identifier: AGPL-3.0-only
"""Prepare private gettext and build-time inputs for the HST language packs."""
import collections
import json
from pathlib import Path
import re
import shutil

from po_io import parse_block, read_blocks

CATALOG = Path(__file__).resolve().parents[2] / "l10n/hst"
DOMAIN = re.compile(rb'(<interface\s+[^>]*?\bdomain=["\x27])([\w-]+)(["\x27])')
LOCATION = re.compile(r'gb_AllLangMoTarget_set_polocation\s*,\s*(\w+)\s*,\s*(\w+)\)')
TARGET = re.compile(r'gb_AllLangMoTarget_AllLangMoTarget\s*,\s*(\w+)\)')


def domains(tree):
    result = {}
    for makefile in tree.glob("*/AllLangMoTarget_*.mk"):
        source = makefile.read_text(encoding="utf-8")
        for name in TARGET.findall(source):
            result[name] = name
        result.update(LOCATION.findall(source))
    if not result:
        raise ValueError(f"{tree}: missing AllLangMoTarget definitions")
    return result


def gettext_key(block):
    entry = parse_block(block)
    return (entry["msgctxt"], entry["msgid"]) if entry else None


def source_file(block):
    # l10ntools' XCU/ULF reader consumes contiguous runs for each source file.
    match = re.search(r"^#: (\S+)", block, re.M)
    return match[1] if match else ""


def combine(original, overlay, retired):
    blocks = [b.strip("\n") for b in read_blocks(original) if b.strip("\n")]
    incoming = collections.OrderedDict()
    for b in read_blocks(overlay):
        key = gettext_key(b)
        if key and key[1]:
            incoming[key] = b.strip("\n")
    kept = []
    for block in blocks:
        key = gettext_key(block)
        if key not in retired:
            kept.append(incoming.pop(key, block))

    additions = collections.defaultdict(list)
    for block in incoming.values():
        additions[source_file(block)].append(block)
    output = []
    for index, block in enumerate(kept):
        output.append(block)
        source = source_file(block)
        if index + 1 == len(kept) or source_file(kept[index + 1]) != source:
            output.extend(additions.pop(source, ()))
    for group in additions.values():
        output.extend(group)
    original.write_text("\n\n".join(output) + "\n", encoding="utf-8")


def prepare(tree):
    """Always start from upstream, so a removed override cannot survive a retry."""
    tree = Path(tree)
    stage = tree / "hst/l10n"
    source = stage / "translations/source"
    upstream = tree / "translations/source/vi"
    mapping = domains(tree)
    if not (upstream / "sfx2/messages.po").is_file():
        raise ValueError(f"{upstream}: upstream Vietnamese catalogs missing")

    for generated in (source / "vi", source / "en-US", stage / "ui"):
        if generated.is_dir():
            shutil.rmtree(generated)
    shutil.copytree(upstream, source / "vi", copy_function=shutil.copyfile)
    retired = collections.defaultdict(set)
    for line in (CATALOG / "retired.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        retired[row["file"]].add((row["msgctxt"], row["msgid"]))
    for overlay in sorted((CATALOG / "vi").rglob("*.po")):
        rel = overlay.relative_to(CATALOG / "vi")
        combine(source / "vi" / rel, overlay, retired[rel.as_posix()])

    english_header = ('msgid ""\nmsgstr ""\n"Language: en-US\\n"\n'
                      '"Content-Type: text/plain; charset=UTF-8\\n"\n')
    for location in mapping.values():
        rel = Path(location) / "messages.po"
        dest = source / "en-US" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if (CATALOG / "en-US" / rel).is_file():
            shutil.copyfile(CATALOG / "en-US" / rel, dest)
        else:
            dest.write_text(english_header, encoding="utf-8")

    (stage / "domains.hxx").write_text(
        "".join(f"HST_CATALOG({name},{loc})\n" for name, loc in sorted(mapping.items())),
        encoding="ascii")
    # Only scan module source, keeping workdir, instdir and the stage out of the walk.
    for module in tree.iterdir():
        config = module / "uiconfig"
        if not config.is_dir():
            continue
        for path in config.rglob("*.ui"):
            data = path.read_bytes()
            match = DOMAIN.search(data)
            if match and match[2].decode("ascii") in mapping:
                position = match.start(2)
                dest = stage / "ui" / path.relative_to(tree)
                dest.parent.mkdir(exist_ok=True, parents=True)
                dest.write_bytes(data[:position] + b"hst-" + data[position:])
    return stage
