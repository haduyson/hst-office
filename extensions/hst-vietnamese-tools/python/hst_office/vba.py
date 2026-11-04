# SPDX-License-Identifier: AGPL-3.0-only
""""Macro VBA" (HST menu, Tools ribbon tab, Alt+F11): open the Basic IDE on the VBA module of the current Writer/Sheets document.

The document's VBA module is the first normal module that runs in VBA mode (an Excel/Word file's
own modules, or one HST created earlier). Without one, HST creates Module<n> from vba_template
and opens the editor on its example Sub. A document without any Basic code yet is switched to VBA
mode (project "VBAProject"/"Project", Vietnamese code page) so that saving as .xlsm/.docm writes
the VBA project; a document that already holds LibreOffice Basic code keeps its mode, and only
the new module gets VBA support (its "Option VBASupport 1" line), so existing macros run as before.
UNO is only touched through the objects passed in, so tests/runtime/check-vba.py uses the same code.
"""
from . import vba_template

# com.sun.star.script.ModuleType
NORMAL_MODULE = 1


def app_of(doc):
    if doc is None:
        return None
    if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
        return "calc"
    if doc.supportsService("com.sun.star.text.TextDocument"):
        return "writer"
    return None


def _modules(libs, name):
    libs.loadLibrary(name)
    library = libs.getByName(name)
    return library, list(library.ElementNames)


def has_basic_code(libs):
    """True when any library of the document holds a module with code (LibreOffice Basic or VBA)."""
    for name in libs.ElementNames:
        library, modules = _modules(libs, name)
        if any(str(library.getByName(m) or "").strip() for m in modules):
            return True
    return False


def _module_type(library, name):
    if hasattr(library, "hasModuleInfo") and library.hasModuleInfo(name):
        return library.getModuleInfo(name).ModuleType
    return NORMAL_MODULE


def add_module(library, name, code):
    """Insert a normal module (with the module info VBA export needs in VBA-mode libraries)."""
    if hasattr(library, "insertModuleInfo") and not library.hasModuleInfo(name):
        import uno
        info = uno.createUnoStruct("com.sun.star.script.ModuleInfo")
        info.ModuleType = NORMAL_MODULE
        library.insertModuleInfo(name, info)
    library.insertByName(name, code)


def prepare_document(doc, app):
    """Make sure the document has a VBA module; return (library, module, code, created)."""
    libs = doc.BasicLibraries
    vba_mode = bool(libs.VBACompatibilityMode)
    project = libs.ProjectName if vba_mode and libs.ProjectName and libs.hasByName(libs.ProjectName) else None
    if project is None:
        project = vba_template.project_name(app)
        if not vba_mode and not has_basic_code(libs):
            if not libs.hasByName(project):
                libs.createLibrary(project)
            libs.VBACompatibilityMode = True
            libs.ProjectName = project
            libs.setPropertyValue("VBATextEncoding", vba_template.VBA_TEXT_ENCODING_VI)
            vba_mode = True
        elif not libs.hasByName(project):
            libs.createLibrary(project)
    library, modules = _modules(libs, project)
    for name in modules:
        code = str(library.getByName(name) or "")
        if _module_type(library, name) == NORMAL_MODULE and (vba_mode or vba_template.has_vba_option(code)):
            return project, name, code, False
    name = vba_template.next_module_name(modules)
    code = vba_template.module_text(app)
    add_module(library, name, code)
    return project, name, code, True


def open_editor(ctx, frame, doc, library, module, line):
    """Show the Basic IDE with library/module of doc, cursor on line (same as Tools ▸ Macros ▸ Edit)."""
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item
    target = doc.getURL() or doc.getTitle()
    args = (prop("Document", target), prop("LibName", library), prop("Name", module), prop("Type", "Module"),
            prop("Line", line))
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    helper.executeDispatch(frame, ".uno:BasicIDEAppear", "", 0, args)


def run(host):
    """HST command EditVba. Menu, ribbon and Alt+F11 offer it only in Writer and Sheets."""
    app = app_of(host.doc)
    if app is None:
        return
    library, module, code, _created = prepare_document(host.doc, app)
    open_editor(host.ctx, host.frame, host.doc, library, module, vba_template.first_line_of(code, "XinChao"))
