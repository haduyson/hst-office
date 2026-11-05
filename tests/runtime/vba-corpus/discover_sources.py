# SPDX-License-Identifier: AGPL-3.0-only
"""List real macro-capable Office files on public GitHub repositories, pinned to a commit. Downloads nothing.

Usage: discover_sources.py OUT.json. Needs `gh` logged in. Records repo, commit, path, size and the licence GitHub
detected; fetch_corpus.py fetches the listed files, static_scan.py decides whether they may run.
"""
import json
import subprocess
import sys
import time
import urllib.parse

MACRO_EXT = (".xlsm", ".xltm", ".xlam", ".xlsb", ".docm", ".dotm")
OLD_EXT = (".xls", ".xla", ".xlt", ".doc", ".dot")  # macros or not is only known after the static scan
MAX_SIZE = 12 * 1024 * 1024
# Test corpora with no per-repo cap: their files are the point. Old binary formats are taken from these too.
CORPORA = ["apache/poi", "decalage2/oletools", "SheetJS/test_files", "nissl-lab/npoi", "apache/tika", "jmcnamara/XlsxWriter",
           "dotnet/Open-XML-SDK", "qax-os/excelize", "plutext/docx4j", "ClosedXML/ClosedXML", "JanKallman/EPPlus",
           "EPPlusSoftware/EPPlus", "openpreserve/format-corpus", "xlwings/xlwings", "unoconv/unoconv", "SheetJS/sheetjs"]
QUERIES = ["language:VBA", "language:VBA stars:>3", "xlsm in:name,description,readme", "excel macro vba in:name,description",
           "excel vba template in:description", "docm in:name,description,readme", "word macro vba in:name,description",
           "word vba in:name,description", "ms word macros", "excel vba invoice", "excel vba accounting", "excel vba payroll",
           "excel vba inventory", "excel vba report", "excel userform", "vba userform in:description", "word document automation vba",
           "word template macro", "dotm in:name,description,readme", "excel vba bang luong", "excel vba quan ly", "vba tieng viet",
           "excel vba ke toan", "vba excel vietnam", "macro excel hoa don"]
PER_REPO = 6


def gh(path):
    for attempt in range(4):
        run = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=120, check=False)
        if run.returncode == 0:
            return json.loads(run.stdout)
        if "rate limit" in run.stderr.lower() or "secondary" in run.stderr.lower():
            time.sleep(30 * (attempt + 1))
            continue
        return None
    return None


def repos_for_query(query, pages=3):
    for page in range(1, pages + 1):
        data = gh(f"search/repositories?q={urllib.parse.quote(query)}&sort=stars&per_page=100&page={page}")
        time.sleep(2.2)  # search API: 30 requests a minute
        if not data or not data.get("items"):
            return
        yield from data["items"]


def files_of(meta, corpus):
    branch = meta["default_branch"]
    commit = gh(f"repos/{meta['full_name']}/commits/{urllib.parse.quote(branch)}")
    if not commit:
        return []
    tree = gh(f"repos/{meta['full_name']}/git/trees/{commit['sha']}?recursive=1")
    if not tree:
        return []
    out = []
    for item in tree.get("tree", []):
        path = item["path"]
        low = path.lower()
        if item["type"] != "blob" or item.get("size", 0) > MAX_SIZE or "~$" in low:
            continue
        if low.endswith(MACRO_EXT) or (low.endswith(OLD_EXT) and (corpus or meta.get("language") == "VBA")):
            out.append(dict(repo=meta["full_name"], commit=commit["sha"], path=path, size=item["size"],
                            licence=(meta.get("license") or {}).get("spdx_id") or "none", stars=meta.get("stargazers_count", 0),
                            pushed=meta.get("pushed_at", ""), corpus=corpus))
    if not corpus:
        out.sort(key=lambda f: (not f["path"].lower().endswith(MACRO_EXT), f["size"]))
        out = out[:PER_REPO]
    return out


def main():
    seen, files = set(), []
    for name in CORPORA:
        meta = gh(f"repos/{name}")
        if meta:
            seen.add(meta["full_name"])
            got = files_of(meta, True)
            files += got
            print(name, len(got), flush=True)
    for query in QUERIES:
        before = len(files)
        for meta in repos_for_query(query):
            if meta["full_name"] in seen or meta.get("fork") or meta.get("size", 0) > 800000:
                continue
            seen.add(meta["full_name"])
            files += files_of(meta, False)
        print(query, len(files) - before, "repos", len(seen), flush=True)
        with open(sys.argv[1], "w", encoding="utf-8") as handle:
            json.dump(files, handle, indent=0, ensure_ascii=False)


if __name__ == "__main__":
    main()
