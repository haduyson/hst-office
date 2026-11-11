# SPDX-License-Identifier: AGPL-3.0-only
"""The extension's UNO component registers every HST service without importing its module.

The office loads python/hst_office_component.py at OnStartApp, while the splash screen is up: whatever that file
imports delays the first window of every start (scripts/perf/startup-timing.py). Each check runs in a fresh Python
with the UNO modules stubbed, so the modules other tests imported do not hide an eager import."""
import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import unittest

import _paths

PYTHON_DIR = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "python")
COMPONENT = os.path.join(PYTHON_DIR, "hst_office_component.py")

# UNO stubs (any attribute is a class) and a unohelper whose ImplementationHelper records the registrations.
PRELUDE = textwrap.dedent('''
    import importlib.abc, importlib.machinery, importlib.util, json, sys, types

    class Stub(types.ModuleType):
        __path__ = []
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            value = type(name, (), {})
            setattr(self, name, value)
            return value

    class Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, name, path=None, target=None):
            if name in ("uno", "com", "org") or name.startswith(("com.", "org.")):
                return importlib.machinery.ModuleSpec(name, self, is_package=True)
            return None
        def create_module(self, spec):
            return Stub(spec.name)
        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, Finder())
    unohelper = Stub("unohelper")
    class ImplementationHelper:
        def __init__(self):
            self.impls = {}
        def addImplementation(self, ctor, name, services):
            self.impls[name] = (ctor, tuple(services))
    unohelper.ImplementationHelper = ImplementationHelper
    unohelper.Base = type("Base", (), {})
    sys.modules["unohelper"] = unohelper
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("hst_office_component", sys.argv[1])
    component = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(component)
    loaded = sorted(m for m in set(sys.modules) - before if m.startswith("hst_office"))
    helper = component.g_ImplementationHelper
''')


def run(body):
    """JSON printed by `body` (after PRELUDE) in a fresh interpreter."""
    done = subprocess.run([sys.executable, "-I", "-c", PRELUDE + textwrap.dedent(body), COMPONENT],
                          capture_output=True, text=True, check=False, cwd=PYTHON_DIR, timeout=120)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    return json.loads(done.stdout.strip().splitlines()[-1])


class LazyRegistration(unittest.TestCase):
    def test_loading_the_component_imports_no_service_module(self):
        result = run('print(json.dumps({"loaded": loaded, "names": sorted(helper.impls)}))')
        # only the Sheets functions stay eager: they are registered only when their UNO type exists
        calc = {"hst_office", "hst_office.calc_functions", "hst_office.number_words", "hst_office.number_words_en",
                "hst_office.vietnamese_text", "hst_office.vietnamese_calc_logic"}
        self.assertEqual(set(result["loaded"]) - calc, set(), result["loaded"])
        self.assertIn("org.hst.office.vi.CrashReportJob", result["names"])
        self.assertIn("org.hst.office.vi.CalcFunctions", result["names"])

    def test_every_service_matches_its_module_and_is_created_on_demand(self):
        result = run('''
            out = []
            for module, cls, name, services in component.SERVICES:
                ctor, registered = helper.impls[name]
                mod = "hst_office." + module
                was_loaded = mod in sys.modules
                instance = ctor(None)
                constants = {v for k, v in vars(sys.modules[mod]).items() if k.isupper() and isinstance(v, str)}
                out.append({"name": name, "services": list(registered), "class": type(instance).__name__,
                            "expected_class": cls, "implementation": instance.getImplementationName(),
                            "module_constant": name in constants, "was_loaded": was_loaded,
                            "supported": list(instance.getSupportedServiceNames())})
            print(json.dumps(out))
        ''')
        self.assertEqual(len(result), len({row["name"] for row in result}), "an implementation name is registered twice")
        self.assertFalse(result[0]["was_loaded"], "the first service's module was imported before it was created")
        for row in result:
            with self.subTest(row["name"]):
                self.assertEqual(row["class"], row["expected_class"])
                self.assertEqual(row["implementation"], row["name"])
                self.assertTrue(row["module_constant"], "the name is not the module's own constant")
                self.assertEqual(sorted(row["services"]), sorted(row["supported"]))

    def test_the_services_created_before_the_first_window_stay_light(self):
        """Created while the splash screen is up or as the Start Center appears: the crash job (OnStartApp), both
        command handlers (the Start Center's menus ask them about every item) and the onFirstVisibleTask jobs. None
        may pull in the command code or the network stack; those load when a command or a background check runs."""
        result = run('''
            for name in ("org.hst.office.vi.CrashReportJob", "org.hst.office.vi.DispatchProvider",
                         "org.hst.office.vi.UpdateDispatchProvider", "org.hst.office.BannerStartup",
                         "org.hst.office.vi.StartupPromptsJob"):
                helper.impls[name][0](None)
            print(json.dumps(sorted(sys.modules)))
        ''')
        heavy = {"hst_office.actions", "hst_office.update_fetch", "hst_office.update_ui", "hst_office.update_job",
                 "hst_office.nd30", "hst_office.usb_token", "ssl", "http.client", "urllib.request", "email"}
        self.assertEqual(heavy & set(result), set())
        package = pathlib.Path(PYTHON_DIR, "hst_office")
        update_ui = (package / "update_ui.py").read_text(encoding="utf-8")
        handler = (package / "update_handler.py").read_text(encoding="utf-8")
        protocol = 'PROTOCOL = "org.hst.office.update:"'
        self.assertIn(protocol, update_ui)
        self.assertIn(protocol, handler)

    def test_the_jobs_and_handlers_the_configuration_names_are_registered(self):
        names = set(run('print(json.dumps(sorted(helper.impls)))'))
        ext = os.path.dirname(PYTHON_DIR)
        configured = set()
        for xcu in ("Jobs.xcu", "ProtocolHandler.xcu", "OptionsDialog.xcu", "CalcAddIns.xcu"):
            with open(os.path.join(ext, xcu), encoding="utf-8") as handle:
                configured |= set(re.findall(r"org\.hst\.office(?:\.vi)?\.[A-Za-z]+", handle.read()))
        # names in the configuration that are services of this component (not command URL prefixes or nodes)
        services = {n for n in configured if n.rsplit(".", 1)[1][0].isupper()}
        self.assertEqual(services - names, set())


if __name__ == "__main__":
    unittest.main()
