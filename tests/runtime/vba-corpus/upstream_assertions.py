# SPDX-License-Identifier: AGPL-3.0-only
"""Jobs for the macros whose expected result LibreOffice's own tests assert ("OK" returned). Usage: upstream_assertions.py TREE INDEX.json OUT.json"""
import json
import re
import sys

SUITES = [("sc/qa/extras/vba-macro-test.cxx", "sc/qa/extras/testdocuments/"), ("sw/qa/core/macros-test.cxx", "sw/qa/core/data/")]
CALL = re.compile(r'testMacro\(\s*u"([^"]+)"\s*,\s*u"vnd\.sun\.[Ss]tar\.script:(\w+)\.(\w+)\.(\w+)\?', re.S)


def main():
    tree, index_path, out_path = sys.argv[1:4]
    with open(index_path, encoding="utf-8") as handle:
        by_path = {e["path"]: e["name"] for e in json.load(handle)}
    jobs = {}
    for source, folder in SUITES:
        with open(f"{tree}/{source}", encoding="utf-8") as handle:
            text = handle.read()
        for path, library, module, proc in CALL.findall(text):
            name = by_path.get(folder + path)
            if not name:
                print("not in index:", folder + path)
                continue
            job = jobs.setdefault(name, dict(file=name, path=folder + path, kind="calc" if "sc/qa" in folder else "writer", only=[]))
            # the C++ test gives Workbooks.xls a folder and a file name
            args = {"args": '"/tmp/work/", "My Test WorkBook.xls"'} if path == "Workbooks.xls" else {}
            job["only"].append(dict(library=library, module=module, proc=proc, kind="Function", want="OK", **args))
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(list(jobs.values()), handle, ensure_ascii=False)
    print(len(jobs), "files", sum(len(j["only"]) for j in jobs.values()), "assertions")


if __name__ == "__main__":
    main()
