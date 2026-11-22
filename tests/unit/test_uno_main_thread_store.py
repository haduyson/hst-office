# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Harness stores run on the office's main thread (uno_main_thread_load.store), not in the UNO bridge thread.

On Windows, storeToURL from the bridge thread right after a load of a document with MathType OLE objects spun
forever in the export's CalcLayout while the main thread's idle layout waited for the SolarMutex (an upstream
LibreOffice race, also in plain LibreOffice 26.2). The store is queued with AsyncCallback and made inside the
callback, which the office calls from its main thread."""
import os
import sys
import threading
import types
import unittest

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)


class PropertyValue:
    def __init__(self):
        self.Name, self.Value = None, None


STUBBED = ("com", "com.sun", "com.sun.star", "com.sun.star.beans", "com.sun.star.awt", "unohelper", "uno_main_thread_load",
           "headless_office")


def keep_modules(test):
    """Put back the modules the stub replaces (and the helper imported against it) after the test, so the other
    test modules of the same run see their own UNO stubs."""
    saved = {name: sys.modules.get(name) for name in STUBBED}

    def restore():
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    test.addCleanup(restore)


def install_uno_stub():
    beans = types.ModuleType("com.sun.star.beans")
    beans.PropertyValue = PropertyValue
    awt = types.ModuleType("com.sun.star.awt")
    awt.XCallback = type("XCallback", (), {})
    for name in ("com", "com.sun", "com.sun.star"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["com.sun.star.beans"] = beans
    sys.modules["com.sun.star.awt"] = awt
    helper = types.ModuleType("unohelper")
    helper.Base = type("Base", (), {})
    sys.modules["unohelper"] = helper


class FakeOffice:
    """AsyncCallback calls notify from another thread (the office's main thread), or never when stalled."""

    def __init__(self, stalled=False):
        self.stalled, self.created = stalled, []
        self.ServiceManager = self

    def createInstanceWithContext(self, name, _ctx):
        self.created.append(name)
        return self

    def addCallback(self, callback, data):
        if not self.stalled:
            threading.Thread(target=callback.notify, args=(data,), name="office-main").start()


class FakeDoc:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def _store(self, kind, url, args):
        self.calls.append((kind, url, {p.Name: p.Value for p in args}, threading.current_thread().name))
        if self.error:
            raise self.error

    def storeToURL(self, url, args):
        self._store("to", url, args)

    def storeAsURL(self, url, args):
        self._store("as", url, args)


class MainThreadStoreTests(unittest.TestCase):
    def setUp(self):
        keep_modules(self)
        install_uno_stub()
        import uno_main_thread_load
        self.module = uno_main_thread_load

    def test_store_runs_inside_the_main_thread_callback(self):
        office, doc = FakeOffice(), FakeDoc()
        self.module.store(office, doc, "file:///t/out.docx", timeout=5, FilterName="MS Word 2007 XML")
        self.assertEqual(office.created, ["com.sun.star.awt.AsyncCallback"])
        self.assertEqual(doc.calls, [("to", "file:///t/out.docx", {"FilterName": "MS Word 2007 XML"}, "office-main")])

    def test_store_as_url(self):
        doc = FakeDoc()
        self.module.store(FakeOffice(), doc, "file:///t/a.docx", as_url=True, timeout=5)
        self.assertEqual(doc.calls[0][0], "as")

    def test_store_error_reaches_the_caller(self):
        with self.assertRaises(OSError):
            self.module.store(FakeOffice(), FakeDoc(error=OSError("disk full")), "file:///t/x.docx", timeout=5)

    def test_timeout_when_the_main_thread_never_calls_back(self):
        with self.assertRaises(TimeoutError):
            self.module.store(FakeOffice(stalled=True), FakeDoc(), "file:///t/x.docx", timeout=0.2)

    def test_headless_office_store_uses_the_main_thread(self):
        import headless_office
        office = headless_office.Office.__new__(headless_office.Office)
        office.ctx, doc = FakeOffice(), FakeDoc()
        office.store(doc, "file:///t/y.pdf", FilterName="writer_pdf_Export")
        self.assertEqual(doc.calls[0][3], "office-main")

    def test_mathtype_harnesses_do_not_store_from_the_bridge_thread(self):
        for name in ("check-formula-ole-roundtrip.py", "check-formula-shown-size.py",
                     "check-formula-convert-pages.py", "check-formula-small-equations.py"):
            with open(os.path.join(RUNTIME, name), encoding="utf-8") as handle:
                self.assertNotIn("doc.storeToURL(", handle.read(), name)


if __name__ == "__main__":
    unittest.main()
