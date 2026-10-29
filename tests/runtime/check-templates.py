#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Real isolated LibreOffice QA. Exit 2 means BLOCKED; never substitute mocks."""
import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "scripts"))
from templates.catalog import load
from templates.odf import json_bytes, read_json
from templates.runtime import RuntimeBlocked, check_pdf, convert, socket_probe
from templates.runtime_checks import check_docx, check_pptx, check_xlsx, fixture_copy

FILTERS = {"writer": ("docx", "Office Open XML Text", "odt", "writer8"),
           "sheets": ("xlsx", "Calc MS Excel 2007 XML", "ods", "calc8"),
           "slides": ("pptx", "Impress MS PowerPoint 2007 XML", "odp", "impress8")}


def check_one(entry, source, args, run, rules, expected):
    ident, module = entry["id"], entry["module"]
    original = args.catalog.parent / entry["output"]
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    if before != entry["outputSha256"]:
        raise ValueError("Template hash differs from manifest")
    work = run / ident
    work.mkdir()
    extension, filter_name, native_ext, native_filter = FILTERS[module]
    pdf = convert(args.soffice, original, work / "pdf", "pdf")
    text = "Độc lập" if module == "writer" else source["title"] if module == "sheets" else source["slides"][0]["title"]
    pages = check_pdf(pdf, text)
    if pages != (len(source["slides"]) if module == "slides" else 1):
        raise ValueError(f"Unexpected PDF page count: {pages}")
    ooxml = convert(args.soffice, original, work / "ooxml", extension, filter_name)
    edited = work / (ident + "-edited" + original.suffix)
    marker = "[Đã chỉnh sửa trong kiểm thử]"
    if module == "sheets":
        fixture_copy(original, edited, inputs=expected["templates"][ident]["inputs"])
    else:
        fixture_copy(original, edited, edit_marker=marker)
    native = convert(args.soffice, edited, work / "native", native_ext, native_filter)
    reopened = convert(args.soffice, native, work / "reopened", "pdf")
    check_pdf(reopened, text)
    if module != "sheets":
        check_pdf(reopened, marker)
    back = convert(args.soffice, ooxml, work / "ooxml-reopened", "pdf")
    check_pdf(back, text)
    if module == "writer":
        check_docx(ooxml, rules)
    elif module == "sheets":
        fixture = expected["templates"][ident]
        check_xlsx(ooxml, fixture["blank"], source["sheetName"])
        copy = work / (ident + "-qa.ots")
        fixture_copy(original, copy, inputs=fixture["inputs"])
        calculated = convert(args.soffice, copy, work / "calculated", extension, filter_name)
        check_xlsx(calculated, fixture["calculated"], source["sheetName"])
    else:
        check_pptx(ooxml, source)
        copy = work / (ident + "-4x3.otp")
        fixture_copy(original, copy, aspect="4:3")
        adapted = convert(args.soffice, copy, work / "aspect", extension, filter_name)
        check_pptx(adapted, source, ratio=4 / 3)
    if hashlib.sha256(original.read_bytes()).hexdigest() != before:
        raise ValueError("Installed template was mutated")
    return {"id": ident, "status": "PASS", "pdfPages": pages, "sourceSha256": before}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", default="/usr/bin/soffice")
    parser.add_argument("--catalog", type=Path, default=BASE / "dist/templates/manifest.json")
    parser.add_argument("--expected", type=Path, default=BASE / "tests/fixtures/templates/expected.json")
    parser.add_argument("--output", type=Path, default=BASE / "tests/output/templates")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.relative_to(BASE / "tests/output")
    args.output.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=args.output))
    authored, sources = load()
    manifest = read_json(args.catalog)
    expected = read_json(args.expected)
    rules = read_json(BASE / "data/vietnamese/nd30.json")
    report = {"status": "UNVERIFIED", "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
              "platform": platform.platform(), "locale": os.environ.get("LANG", ""),
              "backend": "svp", "soffice": args.soffice, "results": []}
    code = 0
    try:
        if not shutil.which(args.soffice) or not shutil.which("pdftotext"):
            raise RuntimeBlocked("Missing soffice or pdftotext")
        version = subprocess.run([args.soffice, "--version"], capture_output=True, text=True, timeout=15)
        report["version"] = version.stdout.strip()
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE, capture_output=True, text=True, timeout=15)
        report["repositoryCommit"] = revision.stdout.strip()
        lock_path = BASE / "upstream/libreoffice-lock.json"
        report["targetSourceCommit"] = read_json(lock_path).get("gitCommit") if lock_path.exists() else "UNVERIFIED"
        font = subprocess.run(["fc-match", "Times New Roman"], capture_output=True, text=True, timeout=15)
        report["timesNewRomanResolved"] = font.stdout.strip()
        socket_probe(run)
        if [e["id"] for e in manifest["templates"]] != [e["id"] for e in authored["templates"]]:
            raise ValueError("Generated catalog IDs differ from sources")
        for entry in manifest["templates"]:
            try:
                result = check_one(entry, sources[entry["id"]], args, run, rules, expected)
            except Exception as error:
                result = {"id": entry["id"], "status": "FAIL", "reason": str(error)}
                code = 1
            report["results"].append(result)
            print(result["status"] + ": " + entry["id"], flush=True)
        report["status"] = "FAIL" if code else "PASS"
    except RuntimeBlocked as error:
        report.update(status="BLOCKED", reason=str(error))
        report["results"] = [{"id": e["id"], "status": "BLOCKED", "sourceSha256": e["outputSha256"]}
                             for e in manifest["templates"]]
        code = 2
    except Exception as error:
        report.update(status="FAIL", reason=str(error))
        code = 1
    (run / "runtime.json").write_bytes(json_bytes(report))
    print(report["status"] + ": " + str(run / "runtime.json"))
    if report.get("reason"):
        print(report["reason"])
    return code


if __name__ == "__main__":
    sys.exit(main())
