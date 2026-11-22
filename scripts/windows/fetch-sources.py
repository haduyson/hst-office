#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Download the pinned LibreOffice tarballs and verify sha256 from upstream/libreoffice-lock.json.

Usage: python -I scripts/windows/fetch-sources.py --dest C:/hst/dl
Exits non-zero on any download error or checksum mismatch (the bad file is deleted).
"""
import argparse
import hashlib
import json
import re
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


TDF_REDIRECTOR = "https://download.documentfoundation.org/libreoffice/src/"
TDF_ARCHIVE = "https://downloadarchive.documentfoundation.org/libreoffice/old/"
FULL_VERSION = re.compile(r"-(\d+\.\d+\.\d+\.\d+)\.tar\.")


def candidate_urls(url):
    """The pinned URL first, then the TDF archive host for the same file.

    The download.documentfoundation.org redirector sends each request to a
    random mirror, and some mirrors serve a certificate chain the runner's
    Python cannot verify. The archive host serves every release directly.
    The sha256 from the lock file is checked afterwards either way.
    """
    urls = [url]
    name = url.rsplit("/", 1)[-1]
    match = FULL_VERSION.search(name)
    if url.startswith(TDF_REDIRECTOR) and match:
        urls.append(f"{TDF_ARCHIVE}{match.group(1)}/src/{name}")
    return urls


def download(url, target, attempts=4):
    urls = candidate_urls(url)
    for attempt in range(1, attempts + 1):
        source = urls[(attempt - 1) % len(urls)]
        try:
            with urllib.request.urlopen(source, timeout=120) as response, target.open("wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            return
        except OSError as error:
            print(f"download attempt {attempt} from {source} failed: {error}", file=sys.stderr)
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
