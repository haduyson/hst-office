# SPDX-License-Identifier: AGPL-3.0-only
"""Run the six citation commands inside a real HST build (no window: dialogs are replaced by recorders).

Usage: python3 tests/runtime/check-citations-commands.py --instdir DIR [--out DIR] [--overlay-oxt FILE]

Checks: insert three citations and renumber (IEEE), insert the bibliography with its paragraph styles, "[2, tr. 7"
+ Chèn lại trích dẫn in one Undo step, edit the citation under the cursor, update after a deletion, switch to the
Chicago notes style and back (citations move into footnotes and out), the save job (writes only when stale),
.docx keeps the settings and the citations, importing a RIS file into the library.
--overlay-oxt unpacks a freshly built hst-vietnamese-tools.oxt over the build's bundled copy first, so the Python
code can be tried before the next full build (it modifies DIR: use a scratch copy of an installation).
"""
import argparse
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from citations_runtime_office import Recorder, run_office  # noqa: E402

EXTENSION = os.path.join("share", "extensions", "hst-vietnamese-tools")
RIS = os.path.join(ROOT, "tests", "fixtures", "citations", "scholar.ris")


def overlay(instdir, oxt):
    target = os.path.join(instdir, EXTENSION)
    if not os.path.isdir(target):
        raise SystemExit("no bundled extension in %s" % target)
    with zipfile.ZipFile(oxt) as archive:
        archive.extractall(target)


def run_checks(ctx, out, instdir):
    import uno
    rec = Recorder()
    scripts = os.path.join(out, "profile", "user", "Scripts", "python")
    os.makedirs(scripts, exist_ok=True)
    shutil.copy(os.path.join(HERE, "citations_commands_inprocess.py"), scripts)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    hidden.Name, hidden.Value = "Hidden", True
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (hidden,))
    try:
        factory = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.script.provider.MasterScriptProviderFactory", ctx)
        script = factory.createScriptProvider("").getScript(
            "vnd.sun.star.script:citations_commands_inprocess.py$run_checks?language=Python&location=user")
        python = os.path.join(os.path.abspath(instdir), EXTENSION, "python")
        found = rec.stage("commands", lambda: json.loads(script.invoke((doc, python, RIS), (), ())[0]))
        for result in found or []:
            if result["status"] == "PASS":
                rec.check(result["check"], True, result["detail"])
            else:
                rec.check(result["check"], False, result["detail"])
    finally:
        doc.close(True)
    return rec.results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/citations-commands"))
    parser.add_argument("--overlay-oxt", help="hst-vietnamese-tools.oxt to unpack over the build's copy first")
    args = parser.parse_args()
    if args.overlay_oxt:
        overlay(args.instdir, args.overlay_oxt)
    return run_office(args.instdir, args.out, lambda ctx, out: run_checks(ctx, out, args.instdir))


if __name__ == "__main__":
    sys.exit(main())
