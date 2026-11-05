# SPDX-License-Identifier: AGPL-3.0-only
"""A new .docm names its macros in word/vbaData.xml, which is what Word's Macros dialog lists."""
import os
import re
import zipfile

from hst_office import vba
import vba_form_structure
from vba_form_fixture import BODY, add_form


def check_word_macro_list(office, out, check, pv, filter_name):
    """Word's Macros dialog names what word/vbaData.xml names: exactly the macros it can run."""
    import uno
    path = os.path.join(out, "macro-list.docm")
    doc = office.new("swriter")
    add_form(office.ctx, doc, "writer", BODY)
    project = vba.prepare_document(doc, "writer")[0]
    library = doc.BasicLibraries.getByName(project)
    modules = {"HstListed": "Public Sub PublicOne()\nEnd Sub\nSub PlainTwo( )\nEnd Sub\nPrivate Sub Hidden()\n"
                            "End Sub\nSub WithArgument(x)\nEnd Sub\nFunction Answer()\nEnd Function\n",
               "HstPrivate": "Option Private Module\nSub InPrivateModule()\nEnd Sub\n"}
    for name, source in modules.items():  # with module info, as the VBA editor creates a module
        info = uno.createUnoStruct("com.sun.star.script.ModuleInfo")
        info.ModuleType = 1
        library.insertModuleInfo(name, info)
        library.insertByName(name, source)
    doc.storeToURL(uno.systemPathToFileUrl(path), (pv("FilterName", filter_name),))
    doc.close(True)
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        data = package.read("word/vbaData.xml").decode("utf-8") if "word/vbaData.xml" in names else ""
        rels = package.read("word/_rels/vbaProject.bin.rels").decode("utf-8") if "word/_rels/vbaProject.bin.rels" in names else ""
        types = package.read("[Content_Types].xml").decode("utf-8")
    listed = {name for name in re.findall(r'wne:name="([^"]+)"', data) if ".HstListed." in name or ".HstPrivate." in name}
    check("new .docm: the list names public Subs without parameters only",
          listed == {f"{project}.HstListed.PublicOne", f"{project}.HstListed.PlainTwo"}, listed)
    check("new .docm: no form module in the list", ".UserForm1." not in data, data)
    check("new .docm: macroName is the name in capitals", f'wne:macroName="{project.upper()}.HSTLISTED.PUBLICONE"' in data, data)
    check("new .docm: the project points to the list", 'relationships/wordVbaData" Target="vbaData.xml"' in rels, rels)
    check("new .docm: content type of the list", "application/vnd.ms-word.vbaData+xml" in types)
    problems, _forms = vba_form_structure.check_file(path)
    check("new .docm: file structure", not problems, problems)
