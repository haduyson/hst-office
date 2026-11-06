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
from templates.runtime_checks import check_docx, check_pptx, check_register_xlsx, check_xlsx, fixture_copy
from templates.runtime_requirements import PATH as REQUIREMENTS, load_requirements, resolve

FILTERS = {"writer": ("docx", "Office Open XML Text", "odt", "writer8"),
           "sheets": ("xlsx", "Calc MS Excel 2007 XML", "ods", "calc8"),
           "slides": ("pptx", "Impress MS PowerPoint 2007 XML", "odp", "impress8")}


def probe_text(source, module):
    """A text that must reach the PDF."""
    if module == "slides":
        return source["slides"][0]["title"]
    if module == "writer":
        return "["  # every Writer template holds placeholders; the heading differs by profile
    return source.get("coverTitle") or source["title"]


def check_pages(pages, spec, source):
    if "slides" in source:
        spec = {**spec, "pdfPages": [len(source["slides"])] * 2}
    low, high = spec.get("pdfPages", [1, None])
    if pages < low or (high is not None and pages > high):
        raise ValueError(f"Unexpected PDF page count: {pages}")


def edited_copy(original, edited, source, spec, expected):
    """A copy changed the way a user would: the type's placeholder paragraph or register cell, or the QA inputs of a sheet."""
    if spec.get("fixture") == "expected":
        fixture_copy(original, edited, inputs=expected["templates"][source["id"]]["inputs"])
        return None
    if "editCell" in spec:
        fixture_copy(original, edited, inputs={spec["editCell"]: spec["marker"]}, sheet=spec["sheet"])
    else:
        fixture_copy(original, edited, edit=spec["edit"], marker=spec["marker"])
    return spec["marker"]


def check_writer(ooxml, original, source, spec, work, args, expected):
    check_docx(ooxml, spec)


def check_sheets(ooxml, original, source, spec, work, args, expected):
    if spec.get("fixture") != "expected":
        check_register_xlsx(ooxml, spec, source)
        return
    extension, filter_name = FILTERS["sheets"][:2]
    fixture = expected["templates"][source["id"]]
    check_xlsx(ooxml, fixture["blank"], source["sheetName"], spec["frozenRows"])
    copy = work / (source["id"] + "-qa.ots")
    fixture_copy(original, copy, inputs=fixture["inputs"])
    calculated = convert(args.soffice, copy, work / "calculated", extension, filter_name)
    check_xlsx(calculated, fixture["calculated"], source["sheetName"], spec["frozenRows"])


def check_slides(ooxml, original, source, spec, work, args, expected):
    extension, filter_name = FILTERS["slides"][:2]
    check_pptx(ooxml, source)
    copy = work / (source["id"] + "-4x3.otp")
    fixture_copy(original, copy, aspect="4:3")
    adapted = convert(args.soffice, copy, work / "aspect", extension, filter_name)
    check_pptx(adapted, source, ratio=4 / 3)


MODULE_CHECKS = {"writer": check_writer, "sheets": check_sheets, "slides": check_slides}


def check_one(entry, source, args, run, spec, expected):
    ident, module = entry["id"], entry["module"]
    original = args.catalog.parent / entry["output"]
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    if before != entry["outputSha256"]:
        raise ValueError("Template hash differs from manifest")
    work = run / ident
    work.mkdir()
    extension, filter_name, native_ext, native_filter = FILTERS[module]
    pdf = convert(args.soffice, original, work / "pdf", "pdf")
    text = probe_text(source, module)
    pages = check_pdf(pdf, text)
    check_pages(pages, spec, source)
    ooxml = convert(args.soffice, original, work / "ooxml", extension, filter_name)
    edited = work / (ident + "-edited" + original.suffix)
    marker = edited_copy(original, edited, source, spec, expected)
    native = convert(args.soffice, edited, work / "native", native_ext, native_filter)
    reopened = convert(args.soffice, native, work / "reopened", "pdf")
    check_pdf(reopened, text)
    if marker:
        check_pdf(reopened, marker)
    back = convert(args.soffice, ooxml, work / "ooxml-reopened", "pdf")
    check_pdf(back, text)
    MODULE_CHECKS[module](ooxml, original, source, spec, work, args, expected)
    if hashlib.sha256(original.read_bytes()).hexdigest() != before:
        raise ValueError("Installed template was mutated")
    return {"id": ident, "kind": args.requirements["templates"][ident]["kind"], "status": "PASS", "pdfPages": pages, "sourceSha256": before}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", default="/usr/bin/soffice")
    parser.add_argument("--catalog", type=Path, default=BASE / "dist/templates/manifest.json")
    parser.add_argument("--expected", type=Path, default=BASE / "tests/fixtures/templates/expected.json")
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS)
    parser.add_argument("--output", type=Path, default=BASE / "tests/output/templates")
    parser.add_argument("--only", nargs="+", metavar="ID", help="check these template IDs only (a rerun)")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.relative_to(BASE / "tests/output")
    args.output.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=args.output))
    authored, sources = load()
    manifest = read_json(args.catalog)
    expected = read_json(args.expected)
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
        socket_probe()
        if [e["id"] for e in manifest["templates"]] != [e["id"] for e in authored["templates"]]:
            raise ValueError("Generated catalog IDs differ from sources")
        args.requirements = load_requirements([e["id"] for e in manifest["templates"]], args.requirements)
        for entry in manifest["templates"]:
            if args.only and entry["id"] not in args.only:
                continue
            try:
                result = check_one(entry, sources[entry["id"]], args, run, resolve(args.requirements, entry["id"]), expected)
            except Exception as error:
                result = {"id": entry["id"], "status": "FAIL", "reason": str(error) or type(error).__name__}
                code = 1
            report["results"].append(result)
            print(result["status"] + ": " + entry["id"] + (": " + result["reason"] if "reason" in result else ""), flush=True)
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
