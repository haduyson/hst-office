# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Integration check in a real office (run by hand; needs LibreOffice/HST Office and the OCR core):

  python3 integration_writer_insert.py SOFFICE PROFILE_DIR OXT IMAGE [HST_TOOLS_OXT]

Installs OXT (and optionally HST Vietnamese tools, for Chuyển TeX ⇄ công thức) into a private profile, starts a
headless office on a private pipe, checks that the Writer command is registered, recognises IMAGE through the
engine process (HST_OCR_ENGINE) and inserts the result into a new Writer document with the extension's own code,
then prints what the document holds. The office is terminated at the end, whatever happens.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "extension", "python"))


def add_extension(ctx, oxt):
    """Install into the private profile through the office's ExtensionManager (unopkg refuses to run as root)."""
    import uno
    manager = ctx.getValueByName("/singletons/com.sun.star.deployment.ExtensionManager")
    try:
        manager.addExtension(uno.systemPathToFileUrl(os.path.abspath(oxt)), (), "user", None, _Env())
    except Exception as exc:  # noqa: BLE001 - show the office's underlying cause, not just "Error while adding"
        raise SystemExit("cannot add %s: %s / cause: %s" % (oxt, exc, getattr(exc, "Cause", None))) from exc


def _env_class():
    import unohelper
    from com.sun.star.task import XInteractionHandler
    from com.sun.star.ucb import XCommandEnvironment, XProgressHandler

    class Env(unohelper.Base, XCommandEnvironment, XInteractionHandler, XProgressHandler):
        """Accepts licence prompts, ignores progress: a non-interactive install."""
        def getInteractionHandler(self):
            return self

        def getProgressHandler(self):
            return self

        def handle(self, request):
            for cont in request.getContinuations():
                if cont.queryInterface(uno.getTypeByName("com.sun.star.task.XInteractionApprove")) is not None:
                    cont.select()
                    return

        def push(self, status):
            pass

        def update(self, status):
            pass

        def pop(self):
            pass

    import uno
    return Env


def _Env():
    return _env_class()()


def connect(pipe, tries=60):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(tries):
        try:
            return resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipe)
        except Exception:  # noqa: BLE001 - office not up yet
            time.sleep(1)
    raise SystemExit("office did not start")


def main(soffice, profile, oxt, image, tools_oxt=None):
    import uno
    from hst_ocr_uno import blocks, engine_client, writer_insert
    from hst_ocr_uno.handler import COMMAND
    os.makedirs(profile, exist_ok=True)
    pipe = "hst_ocr_test_%d" % os.getpid()
    office = subprocess.Popen([soffice, "--headless", "--invisible", "--norestore", "--nologo",
                               "-env:UserInstallation=file://" + profile, "--accept=pipe,name=%s;urp;" % pipe])
    try:
        ctx = connect(pipe)
        for package in filter(None, (oxt, tools_oxt)):
            add_extension(ctx, package)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        frame = doc.getCurrentController().getFrame()
        url = uno.createUnoStruct("com.sun.star.util.URL")
        url.Complete = COMMAND
        transformer = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)
        _, url = transformer.parseStrict(url)
        registered = frame.queryDispatch(url, "", 0) is not None
        start = time.perf_counter()
        response = engine_client.recognize(image, mode="page", threads=2)
        seconds = time.perf_counter() - start
        items = blocks.to_items(response["blocks"])
        converted = writer_insert.insert_items(ctx, doc, items, "Nhận dạng chữ từ ảnh")
        formulas = doc.getEmbeddedObjects().getCount()
        print(json.dumps({"command_registered": registered, "engine_seconds": round(seconds, 2),
                          "items": len(items), "tex_toggle_dispatched": converted, "formula_objects": formulas,
                          "tables": doc.getTextTables().getCount(),
                          "text_head": doc.getText().getString()[:300]}, ensure_ascii=False, indent=1))
        doc.close(True)
    finally:
        office.terminate()
        try:
            office.wait(30)
        except subprocess.TimeoutExpired:
            office.kill()


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6):
        sys.exit(__doc__)
    main(*sys.argv[1:])
