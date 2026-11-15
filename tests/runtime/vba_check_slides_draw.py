# SPDX-License-Identifier: AGPL-3.0-only
"""Part of check-vba.py: "Macro VBA" in HST Slides and HST Draw (headless).

The command prepares the document as in Writer/Sheets, but a new presentation or drawing keeps its
Basic mode: Module1 of the library VBAProject gets VBA support from its "Option VBASupport 1" line
(the presentation export cannot write a new VBA project, so only .odp/.odg keep the code). Checked:
the module and template, the reuse on a second call, VBA syntax with ThisComponent, and the module
surviving a save and reload as .odp/.odg.
"""
import os

from hst_office import vba, vba_template
from vba_check_support import module_code, record, run

APPS = (  # (factory, app, extension, ODF filter)
    ("simpress", "impress", ".odp", "impress8"),
    ("sdraw", "draw", ".odg", "draw8"),
)
PROBE = (f"{vba_template.OPTION_LINE}\nFunction T()\n  Dim n As Integer\n  n = ThisComponent.DrawPages.Count\n"
         "  T = \"trang=\" & CStr(n) & \";\" & UCase(Left(\"vba\", 3))\nEnd Function\n")


def _store(doc, path, filter_name):
    import uno
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = "FilterName", filter_name
    doc.storeToURL(uno.systemPathToFileUrl(path), (prop,))


def check_slides_draw(office, out):
    for kind, app, extension, filter_name in APPS:
        doc = office.new(kind)
        try:
            project, module, code, created = vba.prepare_document(doc, app)
            libs = doc.BasicLibraries
            record(app, "Macro VBA creates VBAProject.Module1 from the template",
                   created and (project, module) == ("VBAProject", "Module1")
                   and vba_template.same_text(code, vba_template.module_text(app)), f"{project}.{module} created={created}")
            record(app, "the document keeps its Basic mode (no VBA project export)", not libs.VBACompatibilityMode,
                   f"mode={libs.VBACompatibilityMode}")
            again = vba.prepare_document(doc, app)
            record(app, "a second call reuses Module1", again[:2] == (project, module) and not again[3], str(again[:2]))
            vba.add_module(libs.getByName(project), "HstCase", PROBE)
            got = run(doc, project, "HstCase", "T")
            record(app, "VBA syntax and ThisComponent run in the module", got == "trang=1;VBA", f"got {got!r}")
            path = os.path.join(out, f"macro-vba-{app}{extension}")
            _store(doc, path, filter_name)
        except Exception as error:  # noqa: BLE001 - one row instead of ending the whole run
            record(app, "Macro VBA prepares the document", False, repr(error))
            continue
        finally:
            doc.close(True)
        again = office.load(path)
        try:
            kept = module_code(again, "VBAProject", "Module1") or ""
            record(app, f"{extension} keeps Module1 after save and reload",
                   vba_template.same_text(kept, vba_template.module_text(app)), kept[:80])
            try:
                got = run(again, "VBAProject", "HstCase", "T")
            except Exception as error:  # noqa: BLE001
                got = repr(error)
            record(app, f"the module still runs after reloading the {extension}", got == "trang=1;VBA", f"got {got!r}")
        finally:
            again.close(True)
