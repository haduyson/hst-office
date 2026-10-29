# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime checks that the installed extension registers its handler, menus and Python code inside the office."""
import hashlib
import os
import sys
import zipfile

import uno

from lo_session import props


def config(session, path):
    provider = session.ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", session.ctx)
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", props(nodepath=path))


def run(rec, session, oxt_path):
    py = session.installed_python_dir()
    rec.check("installed python dir exists", bool(py), py)
    with zipfile.ZipFile(oxt_path) as z:
        packed = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith("python/hst_office/")}
    same = all(hashlib.sha256(open(os.path.join(py, "..", n), "rb").read()).hexdigest() == h for n, h in packed.items())
    rec.check("installed code equals built oxt", same)
    handler = session.ctx.ServiceManager.createInstanceWithContext("org.hst.office.vi.DispatchProvider", session.ctx)
    rec.check("python component instantiates in office", handler is not None and handler.getImplementationName() == "org.hst.office.vi.DispatchProvider")
    doc = session.new_doc("swriter")
    try:
        transformer = session.ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", session.ctx)
        for command in ("Nd30Wizard", "ConvertEncoding", "FormatDate", "FormatVnd", "FormatPercent", "ImportCsv"):
            url = uno.createUnoStruct("com.sun.star.util.URL")
            url.Complete = "org.hst.office.vi:" + command
            _, url = transformer.parseStrict(url)
            dispatch = doc.getCurrentController().getFrame().queryDispatch(url, "_self", 0)
            rec.check("frame dispatches org.hst.office.vi:" + command, dispatch is not None)
        url = uno.createUnoStruct("com.sun.star.util.URL")
        url.Complete = "org.hst.office.vi:Unknown"
        _, url = transformer.parseStrict(url)
        rec.check("unknown command is not handled", doc.getCurrentController().getFrame().queryDispatch(url, "_self", 0) is None)
    finally:
        doc.close(True)
    menu = config(session, "/org.openoffice.Office.Addons/AddonUI/OfficeMenuBar")
    rec.check("HST menu registered", menu.hasByName("org.hst.office.vi"), list(menu.getElementNames())[:5])
    sub = menu.getByName("org.hst.office.vi").getByName("Submenu")
    rec.check("HST submenu has 7 commands (6 tools + solutions)", len(sub.getElementNames()) == 7, sub.getElementNames())
    rec.check("HST toolbar registered", config(session, "/org.openoffice.Office.Addons/AddonUI/OfficeToolBar").hasByName("org.hst.office.vi.toolbar"))
    sys.path.insert(0, py)
