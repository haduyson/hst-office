# SPDX-License-Identifier: AGPL-3.0-only
"""Fetch the files of a sources list from their pinned commits into DEST/<sha256><ext>. Nothing runs here.

Usage: fetch_corpus.py SOURCES.json DEST [--max-bytes N]. Writes DEST/index.json. When a list entry carries
sha256 (corpus-manifest.json) a mismatch is rejected. Besides GitHub: govdocs1 threads and a local LibreOffice tree.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile

UA = {"User-Agent": "hst-office-vba-corpus"}


GOVDOCS = "https://downloads.digitalcorpora.org/corpora/files/govdocs1/zipfiles/{}.zip"


def store(entry, dest, data):
    digest = hashlib.sha256(data).hexdigest()
    if entry.get("sha256") and entry["sha256"] != digest:
        return dict(entry, error="sha256 mismatch")
    ext = os.path.splitext(entry["path"])[1].lower()
    with open(os.path.join(dest, digest + ext), "wb") as handle:
        handle.write(data)
    return dict(entry, sha256=digest, name=digest + ext, bytes=len(data))


def fetch_govdocs_thread(thread, entries, dest):
    """A thread of govdocs1 is one 500 MB zip: it goes to a temporary file, removed after its files are taken."""
    with tempfile.NamedTemporaryFile(dir=dest, suffix=".zip") as holder:
        with urllib.request.urlopen(urllib.request.Request(GOVDOCS.format(thread), headers=UA), timeout=900) as reply:
            shutil.copyfileobj(reply, holder)
        holder.flush()
        with zipfile.ZipFile(holder.name) as package:
            return [store(entry, dest, package.read(entry["path"])) for entry in entries]


def fetch_local(entry, dest, tree):
    """Files of libreoffice/core come from the source tree of the pinned version."""
    with open(os.path.join(tree, entry["path"]), "rb") as handle:
        return store(entry, dest, handle.read())


def fetch(entry, dest):
    url = f"https://raw.githubusercontent.com/{entry['repo']}/{entry['commit']}/{urllib.parse.quote(entry['path'])}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as reply:
            data = reply.read(13 * 1024 * 1024)
    except Exception as error:  # noqa: BLE001 - a missing file is only recorded
        return dict(entry, error=str(error)[:120])
    return store(entry, dest, data)


def save(path, done):
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(list(done.values()), handle, indent=0, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources")
    parser.add_argument("dest")
    parser.add_argument("--max-bytes", type=int, default=1500 * 1024 * 1024)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--lo-tree", help="LibreOffice 26.8.1.1 source tree, for the files of libreoffice/core")
    args = parser.parse_args()
    os.makedirs(args.dest, exist_ok=True)
    with open(args.sources, encoding="utf-8") as handle:
        entries = json.load(handle)
    index_path = os.path.join(args.dest, "index.json")
    done = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as handle:
            done = {(e["repo"], e["path"]): e for e in json.load(handle)}
    todo, total = [], 0
    for entry in entries:
        if (entry["repo"], entry["path"]) not in done and total + entry.get("size", 0) <= args.max_bytes:
            total += entry.get("size", 0)
            todo.append(entry)
    print(f"fetching {len(todo)} files, {total // 1048576} MB", flush=True)
    threads = {}
    for entry in [e for e in todo if e["repo"] == "digitalcorpora/govdocs1"]:
        threads.setdefault(entry["commit"].replace("thread-", ""), []).append(entry)
    for thread, wanted in threads.items():
        for result in fetch_govdocs_thread(thread, wanted, args.dest):
            done[(result["repo"], result["path"])] = result
    for entry in [e for e in todo if e["repo"] == "libreoffice/core" and args.lo_tree]:
        result = fetch_local(entry, args.dest, args.lo_tree)
        done[(result["repo"], result["path"])] = result
    todo = [e for e in todo if e["repo"] not in ("digitalcorpora/govdocs1", "libreoffice/core")]
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        for count, result in enumerate(pool.map(lambda e: fetch(e, args.dest), todo), 1):
            done[(result["repo"], result["path"])] = result
            if count % 100 == 0:
                print(count, flush=True)
                save(index_path, done)
    save(index_path, done)


if __name__ == "__main__":
    main()
