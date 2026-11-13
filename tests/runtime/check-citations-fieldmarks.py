# SPDX-License-Identifier: AGPL-3.0-only
"""Prove the in-document representation of HST citations on a real build.

Usage: python3 tests/runtime/check-citations-fieldmarks.py [--instdir DIR] [--out DIR] [--skip-perf]

A citation is a text fieldmark (type UNHANDLED) with the code "ADDIN HST_CITATION {json}" and
the formatted citation as its result; the bibliography is one fieldmark "ADDIN HST_BIBLIOGRAPHY"
over several paragraphs. Builds a sample document with the real commands (.uno:TextFormField,
.uno:TextFormFields), checks formatting, order, bulk update with one Undo step, tracked changes,
editing and Undo behaviour, saves .docx and .odt, reloads both, reads the .docx with the standard
library as another word processor would, and times a thesis-sized document. Writes
evidence.json (and the saved files) to --out; exit 1 on any failure.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from citations_runtime_office import Recorder, run_office  # noqa: E402


def run_checks(ctx, out, skip_perf):
    import uno
    import citations_fieldmark_checks as checks
    import citations_fieldmark_edits as edits
    import citations_fieldmark_sample as sample
    from citations_fieldmark_uno import Session, prop
    rec = Recorder()
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = (prop("Hidden", True),)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    saved, reference = {}, {}
    try:
        session = Session(ctx, doc)
        sample.build(session)
        rec.stage("format", checks.check_formatting, rec, doc)
        rec.stage("bibliography", checks.check_bibliography, rec, doc, True)
        rec.stage("order", checks.check_order, rec, doc)
        rec.stage("update", checks.check_bulk_update, rec, session)
        rec.stage("single-update", checks.check_single_update, rec, session)
        rec.stage("tracked-changes", checks.check_tracked_changes, rec, session)
        reference = checks.snapshot(doc)
        rec.check("saved-codes-are-the-inserted-ones", {c: v[0] for c, v in reference.items()}
                  == sample.expected_codes(), sorted(reference))
        for ext, filt in (("docx", "MS Word 2007 XML"), ("odt", "writer8")):
            saved[ext] = os.path.join(out, f"citations.{ext}")
            doc.storeToURL(uno.systemPathToFileUrl(saved[ext]), (prop("FilterName", filt),))
    finally:
        doc.close(True)
    for ext, path in saved.items():
        reopened = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, hidden)
        try:
            rec.stage(f"reload-{ext}", checks.check_reloaded, rec, reopened, f"reload-{ext}", reference)
            rec.stage(f"reload-{ext}-order", checks.check_order, rec.prefixed(f"reload-{ext}"), reopened)
        finally:
            reopened.close(True)
    rec.stage("docx-xml", checks.check_docx_reader, rec, saved["docx"], reference)
    edit_doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    try:
        rec.stage("edit", edits.run, rec, Session(ctx, edit_doc))
    finally:
        edit_doc.close(True)
    if not skip_perf:
        import citations_fieldmark_perf as perf
        rec.stage("perf", perf.run, rec, ctx, desktop, out)
    return rec.results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/citations-fieldmarks"))
    parser.add_argument("--skip-perf", action="store_true", help="skip the 200-page timing document")
    args = parser.parse_args()
    return run_office(args.instdir, args.out, lambda ctx, out: run_checks(ctx, out, args.skip_perf))


if __name__ == "__main__":
    sys.exit(main())
