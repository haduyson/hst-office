# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime checks of the welcome dialog on a brand-new profile: shown once at first start, not at the second,
reopened by the HST menu command, correct UTM links. The browser launcher is replaced by a recorder in the
probe, so no browser is started. Needs an X display (modal dialogs)."""
import json
import os
import shutil
import threading
import time
import subprocess

import uno

from lo_session import Session, props
from scenarios_registration import config

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
TAIL = "utm_source=hst-office&utm_medium=%s&utm_campaign=hst-office-1-0"


def _fresh(base, workdir, port):
    """A second isolated profile that has the extension and the probe (bundled mode reuses the unpacked dirs)."""
    s = Session(base.soffice, base.extension, workdir, port, base.display, base.mode)
    if base.mode == "bundled":
        shutil.rmtree(s.workdir, ignore_errors=True)
        os.makedirs(s.workdir)
    else:
        ok, text, _ = s.install()
        ok2, text2 = s.install_probe()
        if not (ok and ok2):
            raise RuntimeError("install failed: %s %s" % (text, text2))
    return s


def _set_ui_language(s, code):
    """The dialog reads the UI language from the configuration at show time; the profile's default is en-US."""
    node = config_update(s, "/org.openoffice.Setup/L10N")
    node.setPropertyValue("ooLocale", code)
    node.commitChanges()


def config_update(s, path):
    provider = s.ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", s.ctx)
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", props(nodepath=path))


def _state(s, py):
    return json.loads(s.macro("welcome_state", py))


def _wait(fn, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.5)
    return None


def _open_visible_doc(s):
    """Load a visible Writer window from a thread: the first-start job may keep the call busy behind its modal dialog."""
    box = {}
    thread = threading.Thread(target=lambda: box.update(doc=s.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())))
    thread.start()
    return thread, box


def _shot(s, path):
    subprocess.run(["import", "-display", s.display, "-window", "root", path], check=False, capture_output=True, timeout=60)
    return os.path.exists(path)


def _dispatch_menu(s, doc):
    transformer = s.ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", s.ctx)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = "org.hst.office.vi:ShowSolutions"
    _, url = transformer.parseStrict(url)
    dispatch = doc.getCurrentController().getFrame().queryDispatch(url, "_self", 0)
    return url, dispatch


def run(rec, base, oxt_path, out):
    if not base.display:
        return rec.blocked("welcome dialog", "needs --display (modal dialogs)")
    s = _fresh(base, os.path.join(os.path.dirname(base.workdir), "welcome-profile"), base.port + 1)
    data = json.load(open(os.path.join(REPO, "data", "hst", "solutions.json"), encoding="utf-8"))
    sols = data["solutions"]
    try:
        s.start()
        py = s.installed_python_dir()
        flag = lambda: config(s, "/org.hasontech.hstoffice.Welcome").getPropertyValue("Shown")  # noqa: E731
        rec.check("welcome flag schema registered, default false", flag() is False, flag())
        s.macro("welcome_hook", py)
        _set_ui_language(s, "vi")
        thread, box = _open_visible_doc(s)
        st = _wait(lambda: (lambda x: x if x["open"] else None)(_state(s, py)))
        rec.check("first start: welcome dialog shown", bool(st), st)
        if not st:
            return
        labels = st["labels"]
        vi = json.load(open(os.path.join(REPO, "extensions", "hst-vietnamese-tools", "locales", "vi.json"), encoding="utf-8"))["welcome"]
        rec.check("title, greeting and free-forever badge", st["title"] == "HST Office chào đón bạn" and labels["heading"] == vi["heading"] and labels["freeBadge"] == "MIỄN PHÍ VĨNH VIỄN", (st["title"], labels.get("heading")))
        rec.check("three applications and four key features", [labels[k] for k in ("appWriter", "appSheets", "appSlides")] == [vi[k] for k in ("appWriter", "appSheets", "appSlides")] and
                  [labels["feature%d" % i] for i in range(4)] == ["\u2022  " + f for f in vi["features"]], [labels.get("feature%d" % i) for i in range(4)])
        rec.check("six solutions in the given order", [labels["link%d" % i] for i in range(6)] == [x["name"] for x in sols])
        rec.check("contact line and F1 tip", all(data["company"][k] in labels["contactLine"] for k in ("phone", "email")) and "F1" in labels["helpTip"], labels["contactLine"])
        rec.check("flag set once displayed", flag() is True)
        rec.check("no link opened before a click", st["opened"] == [])
        rec.check("shot", _shot(s, os.path.join(out, "welcome-dialog.png")), os.path.join(out, "welcome-dialog.png"))
        for i in range(len(st["links"])):
            s.macro("welcome_click", py, i)
        opened = _state(s, py)["opened"]
        expect = [x["url"] + "?" + TAIL % "welcome" for x in sols] + [data["company"]["website"] + "?" + TAIL % "welcome"]
        rec.check("each click opens its URL with welcome UTM", opened == expect, opened)
        s.macro("welcome_close", py, True)
        thread.join(30)
        rec.check("dialog closed", not _state(s, py)["open"] and flag() is True)
        doc = box.get("doc")
        if doc:
            doc.close(True)
        s.stop()
        s.start()
        s.macro("welcome_hook", py)
        thread, box = _open_visible_doc(s)
        thread.join(40)
        time.sleep(6)
        rec.check("second start: dialog not shown", not _state(s, py)["open"] and flag() is True)
        doc = box.get("doc")
        _set_ui_language(s, "en-US")
        url, dispatch = _dispatch_menu(s, doc)
        rec.check("menu command ShowSolutions handled", dispatch is not None)
        threading.Thread(target=lambda: dispatch.dispatch(url, ())).start()
        st = _wait(lambda: (lambda x: x if x["open"] else None)(_state(s, py)))
        rec.check("menu command opens the dialog, Vietnamese under an English UI", bool(st) and st["title"] == "HST Office chào đón bạn", st and st["title"])
        if st:
            _shot(s, os.path.join(out, "welcome-dialog-en.png"))
            s.macro("welcome_click", py, 0)
            s.macro("welcome_click", py, len(st["links"]) - 1)
            opened = _state(s, py)["opened"]
            rec.check("menu links carry utm_medium=menu", opened == [sols[0]["url"] + "?" + TAIL % "menu", data["company"]["website"] + "?" + TAIL % "menu"], opened)
            s.macro("welcome_close", py, False)  # untick "do not show again"
            time.sleep(1)
            rec.check("unticking 'do not show again' re-arms the first-start dialog", flag() is False)
        addons = config(s, "/org.openoffice.Office.Addons/AddonUI/OfficeMenuBar").getByName("org.hst.office.vi")
        item = addons.getByName("Submenu").getByName("m7")
        ctx = set(item.getPropertyValue("Context").split(","))
        need = {"com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument", "com.sun.star.presentation.PresentationDocument", "com.sun.star.frame.StartModule"}
        rec.check("menu entry registered for Writer, Calc, Impress, Start Center", need <= ctx, ctx)
        if doc:
            doc.close(True)
    finally:
        s.stop()
        s.cleanup()
