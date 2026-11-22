# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Compare two saved office files part by part (the same document saved by two office builds).

    python3 large_file_compare_saved.py A.xlsx B.xlsx

Every zip part must be byte-identical, except the parts that carry the save time or the generator:
docProps/core.xml, docProps/app.xml, meta.xml (ODF). Prints one JSON line {"equal": bool, "differ": [...],
"only_a": [...], "only_b": [...], "parts": n} and exits 1 when they differ.
"""
import hashlib
import json
import sys
import zipfile

IGNORED = {"docProps/core.xml", "docProps/app.xml", "meta.xml"}


def digests(path):
    with zipfile.ZipFile(path) as z:
        return {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n not in IGNORED}


def main():
    a, b = digests(sys.argv[1]), digests(sys.argv[2])
    res = {"differ": sorted(n for n in a.keys() & b.keys() if a[n] != b[n]),
           "only_a": sorted(a.keys() - b.keys()), "only_b": sorted(b.keys() - a.keys()), "parts": len(a)}
    res["equal"] = not (res["differ"] or res["only_a"] or res["only_b"])
    print(json.dumps(res))
    return 0 if res["equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
