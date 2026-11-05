# SPDX-License-Identifier: AGPL-3.0-only
"""Write the regression fixtures and their sandbox jobs. Usage: make_regression_fixtures.py OUTDIR JOBS.json"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import language_cases  # noqa: E402
import regression_cases  # noqa: E402
import vba_package  # noqa: E402

FUNCTION = re.compile(r"(?m)^Function (\w+)\(\)")
RESULT = re.compile(r"(?<![\w.])r = (?=[\"(])")


def main():
    out, jobs_path = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    jobs = []
    for name, kind, modules, expected in regression_cases.FILES:
        writer = vba_package.xlsm if kind == "calc" else (lambda m, c: vba_package.docm(m, c, regression_cases.PARAGRAPHS))
        with open(os.path.join(out, name), "wb") as handle:
            handle.write(writer(modules, 1258 if any(ord(c) > 127 for _m, source in modules for c in source) else 1252))
        library = "VBAProject" if kind == "calc" else "Project"
        if expected is None:
            expected = [(module, function, "OK") for module, source in modules for function in FUNCTION.findall(source)]
        only = [dict(library=library, module=m, proc=f, kind="Function", **({"want": w} if w else {})) for m, f, w in expected]
        jobs.append(dict(file=name, kind=kind, only=only, timeout=30))
    for name, module_code, body in language_cases.CASES:
        body = RESULT.sub("Lang = ", body)
        source = f"{module_code}\nFunction Lang()\n{body}\nEnd Function\n"
        with open(os.path.join(out, f"lang-{name}.xlsm"), "wb") as handle:
            handle.write(vba_package.xlsm([("Cases", source)], 1258))
        jobs.append(dict(file=f"lang-{name}.xlsm", kind="calc", timeout=20,
                         only=[dict(library="VBAProject", module="Cases", proc="Lang", kind="Function", want="OK")]))
    with open(jobs_path, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, ensure_ascii=False)
    print(len(jobs), "files", sum(len(j["only"]) for j in jobs), "cases")


if __name__ == "__main__":
    main()
