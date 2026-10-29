#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Download the pinned LibreOffice tarballs and verify sha256 from upstream/libreoffice-lock.json.

Usage: python -I scripts/windows/fetch-sources.py --dest C:/hst/dl
Exits non-zero on any download error or checksum mismatch (the bad file is deleted).
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256_of(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, target, attempts=4):
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            return
        except OSError as error:
            print(f"download attempt {attempt} failed: {error}", file=sys.stderr)
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--lock", type=Path, default=ROOT / "upstream" / "libreoffice-lock.json")
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    tarballs = json.loads(args.lock.read_text(encoding="utf-8"))["tarballs"]
    for item in tarballs:
        target = args.dest / item["name"]
        started = time.time()
        download(item["url"], target)
        actual = sha256_of(target)
        if actual != item["sha256"]:
            target.unlink()
            print(f"SHA256 MISMATCH {item['name']}: expected {item['sha256']} got {actual}", file=sys.stderr)
            return 1
        print(f"verified {item['name']} sha256={actual} size={target.stat().st_size} seconds={time.time() - started:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
