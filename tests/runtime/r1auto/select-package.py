#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Select exactly one package; optional checksum must match if provided."""
import hashlib
from pathlib import Path
import sys

root, suffix = Path(sys.argv[1]), sys.argv[2]
packages = list(root.rglob("*" + suffix))
if len(packages) != 1:
    raise SystemExit("Hiện vật phải chứa đúng một bộ cài")
package = packages[0].resolve()
checksums = list(root.rglob("SHA256SUMS"))
if checksums:
    lines = [line for path in checksums for line in path.read_text().splitlines()
             if line.split() and line.split()[-1].lstrip("*") == package.name]
    actual = hashlib.sha256(package.read_bytes()).hexdigest()
    if len(lines) != 1 or lines[0].split()[0] != actual:
        raise SystemExit("Mã kiểm tra bộ cài không khớp")
print("R1_PACKAGE=" + str(package))
