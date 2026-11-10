# SPDX-License-Identifier: AGPL-3.0-only
"""HST document commands without a document (the Start Center) and the test-only failure hook of the dispatcher.

UNO modules are stubbed; frames, controllers and models are plain fakes."""
import importlib.abc
import importlib.machinery
import sys
import types
import unittest
from unittest import mock

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    """Any attribute is a fresh class (or, for upper-case names, a constant), so imports build without the office."""
    __path__ = []  # a package: `from com.sun.star.awt.Key import TAB` resolves through _UnoStubs too

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


class _UnoStubs(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        if name in ("uno", "unohelper") or name == "com" or name.startswith("com."):
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        pass


_FINDER = _UnoStubs()
sys.meta_path.insert(0, _FINDER)
for _name, _module in list(sys.modules.items()):  # stubs other tests registered first become packages as well
    if (_name == "com" or _name.startswith("com.")) and not hasattr(_module, "__path__"):
        _module.__path__ = []
from hst_office import dispatch  # noqa: E402
from hst_office.data_files import load_locale  # noqa: E402

sys.meta_path.remove(_FINDER)  # only this import needed the office's modules; other tests see the real absence

URL = type("URL", (), {"Protocol": dispatch.PROTOCOL, "Path": "ToggleDuplex"})


class Frame:
    def __init__(self, model):
        self.controller = type("Controller", (), {"getModel": lambda _self: model})()

    def getController(self):
        return self.controller

    def getContainerWindow(self):
        return None


def handler(frame):
    h = dispatch.Handler(None)
    h.initialize((frame,))
    return h


class NoDocumentTests(unittest.TestCase):
    def test_has_document(self):
        self.assertFalse(dispatch.has_document(None))
        self.assertFalse(dispatch.has_document(Frame(None)))  # Start Center: a controller, no model
        self.assertTrue(dispatch.has_document(Frame(object())))

    def test_start_center_gets_the_friendly_message_and_no_command_runs(self):
        h, command = handler(Frame(None)), mock.Mock()
        with mock.patch.dict(dispatch.COMMANDS, {"ToggleDuplex": command}), \
                mock.patch.object(h, "_say") as say, mock.patch.object(dispatch, "log_error") as log:
            h.dispatch(URL, ())
        command.assert_not_called()
        log.assert_not_called()  # an expected situation, not an error
        say.assert_called_once()
        self.assertEqual(say.call_args[0][1], "Hãy mở hoặc tạo một tài liệu trước khi dùng lệnh này.")
        self.assertEqual(load_locale("en")["common"].keys(), load_locale("vi")["common"].keys())

    def test_a_document_runs_the_command(self):
        h, command = handler(Frame(object())), mock.Mock()
        with mock.patch.dict(dispatch.COMMANDS, {"ToggleDuplex": command}), \
                mock.patch.object(dispatch, "Host"), mock.patch.object(h, "_send_duplex_state"):
            h.dispatch(URL, ())
        command.assert_called_once()


class TestHookTests(unittest.TestCase):
    def test_inert_without_the_variable_or_in_a_release_package(self):
        with mock.patch("hst_office.update_fetch.release_info", return_value={"test_mode": True}):
            dispatch.raise_for_test("ToggleDuplex", {})
            dispatch.raise_for_test("ToggleDuplex", {dispatch.TEST_RAISE_ENV: "Other"})
        with mock.patch("hst_office.update_fetch.release_info", return_value={"test_mode": False}):
            dispatch.raise_for_test("ToggleDuplex", {dispatch.TEST_RAISE_ENV: "ToggleDuplex"})

    def test_test_package_raises_inside_the_entry_point_and_the_error_is_logged(self):
        env = {dispatch.TEST_RAISE_ENV: "ToggleDuplex"}
        with mock.patch("hst_office.update_fetch.release_info", return_value={"test_mode": True}):
            with self.assertRaisesRegex(RuntimeError, "diagnostics test hook: ToggleDuplex"):
                dispatch.raise_for_test("ToggleDuplex", env)
            h = handler(Frame(None))
            with mock.patch.dict("os.environ", env), mock.patch.object(dispatch, "log_error") as log, \
                    mock.patch.object(dispatch, "Host") as host:
                h.dispatch(URL, ())
        log.assert_called_once_with("ToggleDuplex")
        host.return_value.say.assert_called_once()
        self.assertTrue(host.return_value.say.call_args[1]["error"])


if __name__ == "__main__":
    unittest.main()
