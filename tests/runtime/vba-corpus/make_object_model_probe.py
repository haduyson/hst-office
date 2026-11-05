# SPDX-License-Identifier: AGPL-3.0-only
"""One module per object-model probe in one .xlsm and one .docm, so a syntax gap stays in its module. Usage: make_object_model_probe.py OUTDIR JOBS.json"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import object_model_excel  # noqa: E402
import object_model_word  # noqa: E402
import vba_package  # noqa: E402


def module(setup, statement):
    return f'Function P()\n{setup}{statement}\nP = "OK"\nEnd Function\n'


def main():
    out, jobs_path = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    jobs = []
    for name, kind, library, source, writer in (("om-excel.xlsm", "calc", "VBAProject", object_model_excel, vba_package.xlsm), ("om-word.docm", "writer", "Project", object_model_word, vba_package.docm)):
        cases = source.cases()
        modules = [(f"P{index}", module(source.SETUP, statement)) for index, (_label, statement) in enumerate(cases)]
        for start in range(0, len(modules), 60):
            part = modules[start:start + 60]
            file_name = f"{name[:-5]}-{start // 60}{name[-5:]}"
            with open(os.path.join(out, file_name), "wb") as handle:
                handle.write(writer(part, 1252))
            only = [dict(library=library, module=f"P{start + i}", proc="P", kind="Function", want="OK", label=cases[start + i][1]) for i in range(len(part))]
            jobs.append(dict(file=file_name, kind=kind, only=only, max_procs=100, timeout=20, budget=900))
    with open(jobs_path, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, ensure_ascii=False)
    print(sum(len(j["only"]) for j in jobs), "probes in", len(jobs), "files")


if __name__ == "__main__":
    main()
