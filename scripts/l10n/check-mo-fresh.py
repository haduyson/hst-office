#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when a built LibreOffice tree ships message catalogues (.mo) that do not match its translations (.po).

  check-mo-fresh.py --tree <lo> [--lang vi] [--msgfmt msgfmt] [--msguniq msguniq]

LibreOffice's make does not rebuild a module's .mo when its messages.po changes (docs/SHARED_BUILD_SLOTS.md), so an
incremental build can ship the catalogue of an older ref. For every <lang> catalogue in instdir this compiles the
module's messages.po the way gbuild does (`msguniq --force-po messages.po | msgfmt -`) and compares the entries
(msgctxt + msgid -> msgstr) with the shipped .mo. Exit 1 lists the stale catalogues with a few differing msgids.
The module -> .po mapping comes from the gb_AllLangMoTarget_set_polocation calls in the tree's makefiles.
"""
import argparse
import glob
import os
import re
import struct
import subprocess
import sys
import tempfile

POLOCATION_RE = re.compile(r"gb_AllLangMoTarget_set_polocation\s*,\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_/.-]+)\s*\)")


def read_mo(path):
    """{key: translation} of a GNU .mo file (key = msgctxt EOT msgid, plural forms joined by NUL)."""
    with open(path, "rb") as f:
        data = f.read()
    magic = struct.unpack("<I", data[:4])[0]
    order = "<" if magic == 0x950412DE else ">" if magic == 0xDE120495 else None
    if order is None:
        raise ValueError(f"{path}: not a .mo file")
    count, orig, trans = struct.unpack(order + "III", data[8:20])
    entries = {}
    for i in range(count):
        olen, ooff = struct.unpack(order + "II", data[orig + 8 * i:orig + 8 * i + 8])
        tlen, toff = struct.unpack(order + "II", data[trans + 8 * i:trans + 8 * i + 8])
        entries[data[ooff:ooff + olen]] = data[toff:toff + tlen]
    return entries


def polocations(tree):
    """MoTarget name (sw, sc, ...) -> its .po directory below translations/source/<lang>/."""
    mapping = {}
    for mk in glob.glob(os.path.join(tree, "*", "AllLangMoTarget_*.mk")):
        with open(mk, encoding="utf-8", errors="replace") as f:
            for name, location in POLOCATION_RE.findall(f.read()):
                mapping[name] = location
    return mapping


def compile_po(po, msguniq, msgfmt, workdir):
    out = os.path.join(workdir, "check.mo")
    uniq = subprocess.run([msguniq, "--force-po", po], capture_output=True, check=True)
    subprocess.run([msgfmt, "-", "-o", out], input=uniq.stdout, capture_output=True, check=True)
    return read_mo(out)


def describe(key):
    text = key.decode("utf-8", "replace")
    return text.replace("\x04", " | ")[:70]


def check(tree, lang, msguniq="msguniq", msgfmt="msgfmt", out=sys.stdout):
    """Number of stale catalogues; prints one line per catalogue checked with a difference."""
    mos = sorted(glob.glob(os.path.join(tree, "instdir", "program", "resource", lang, "LC_MESSAGES", "*.mo")))
    if not mos:
        print(f"check-mo-fresh: no {lang} catalogues in {tree}/instdir", file=out)
        return 1
    locations = polocations(tree)
    stale = checked = 0
    with tempfile.TemporaryDirectory() as workdir:
        for mo in mos:
            name = os.path.basename(mo)[:-3]
            location = locations.get(name, name)   # without set_polocation the .po directory is the module name
            po = os.path.join(tree, "translations", "source", lang, location or "", "messages.po")
            if not os.path.isfile(po):
                continue   # catalogue without a translated .po (e.g. en-US only): nothing to compare
            checked += 1
            want = compile_po(po, msguniq, msgfmt, workdir)
            have = read_mo(mo)
            if want == have:
                continue
            stale += 1
            missing = [k for k in want if k not in have]
            changed = [k for k in want if k in have and want[k] != have[k]]
            extra = [k for k in have if k not in want]
            sample = ", ".join(repr(describe(k)) for k in (missing + changed)[:3])
            print(f"STALE {lang}/{name}.mo: .po has {len(want)} entries, .mo {len(have)} "
                  f"({len(missing)} missing, {len(changed)} changed, {len(extra)} extra){': ' + sample if sample else ''}",
                  file=out)
    print(f"check-mo-fresh: {checked} {lang} catalogues checked, {stale} stale", file=out)
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tree", required=True, help="LibreOffice tree (with instdir/ and translations/)")
    parser.add_argument("--lang", default="vi")
    parser.add_argument("--msguniq", default="msguniq")
    parser.add_argument("--msgfmt", default="msgfmt")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]+)?", args.lang):
        parser.error("bad --lang")
    try:
        return 1 if check(args.tree, args.lang, args.msguniq, args.msgfmt) else 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"check-mo-fresh: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
