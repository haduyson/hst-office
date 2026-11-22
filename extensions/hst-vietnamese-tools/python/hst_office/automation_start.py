# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Was this office started by other software (a script, a converter, an automation client) rather than by a person?

Such a start drives the office through the API: headless or invisible, a UNO connection (--accept, as the Python
officehelper and every UNO client use), a conversion or print run, or the Windows COM automation server (registered as
"soffice.exe --nodefault --nologo"). The welcome dialog and the default-apps question are for a person: shown there they
sit unseen over the client's work, and a modal one blocks the API call that made the first window visible. They keep
their state (welcome: Shown, default apps: Asked) and wait for the next start by a person.

The switches are the ones the office itself parsed: osl_getCommandArg of the sal library already loaded in this
process (the same list desktop/CommandLineArgs reads). --norestore alone is no automation
(a person may use it); with --accept it is. When the arguments cannot be read the start counts as a person's, so the
dialogs keep their usual behaviour.

HST_OFFICE_INTERACTIVE_START=1 in the environment makes an automated start count as a person's: the runtime checks
drive the office through --accept and still have to meet the start-up questions as a person does.
"""
import os
import sys

from . import diag_log

INTERACTIVE_ENV = "HST_OFFICE_INTERACTIVE_START"
SWITCHES = frozenset(("headless", "invisible", "nodefault", "terminate_after_init", "convert-to", "print-to-file", "pt",
                      "p", "cat", "script-cat"))
PREFIXES = ("accept=",)


def _switch(arg):
    """'--headless' / '-headless' -> 'headless'; None for a document path or another non-switch argument."""
    if arg.startswith("--"):
        return arg[2:]
    if arg.startswith("-") and len(arg) > 1:
        return arg[1:]
    return None


def automated(args):
    """True when one of the command-line arguments `args` is a switch only other software uses."""
    for arg in args:
        name = _switch(arg)
        if name is not None and (name in SWITCHES or name.startswith(PREFIXES)):
            return True
    return False


SAL_NAMES = {"win32": "sal3.dll", "darwin": "libuno_sal.dylib.3"}


def _sal():
    """The sal library of this office. Windows: by module name (loaded already). Elsewhere the soffice process has it in
    its global scope; failing that, it is loaded from the folder of pyuno (program/ on Linux, Frameworks/ on macOS)."""
    import ctypes
    if sys.platform == "win32":
        return ctypes.CDLL(SAL_NAMES["win32"])
    own = ctypes.CDLL(None)
    if hasattr(own, "osl_getCommandArgCount"):
        return own
    import pyuno
    name = SAL_NAMES.get(sys.platform, "libuno_sal.so.3")
    return ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(pyuno.__file__)), name))


def command_args(sal=None):
    """The office's command-line arguments as the office parsed them (osl_getCommandArg), without argv[0]."""
    import ctypes
    sal = sal or _sal()
    ustr = ctypes.c_void_p
    sal.osl_getCommandArgCount.restype = ctypes.c_uint32
    sal.osl_getCommandArgCount.argtypes = ()
    sal.osl_getCommandArg.restype = ctypes.c_int
    sal.osl_getCommandArg.argtypes = (ctypes.c_uint32, ctypes.POINTER(ustr))
    sal.rtl_uString_new.argtypes = (ctypes.POINTER(ustr),)
    sal.rtl_uString_new.restype = None
    sal.rtl_uString_release.argtypes = (ustr,)
    sal.rtl_uString_release.restype = None
    sal.rtl_uString_getLength.argtypes = (ustr,)
    sal.rtl_uString_getLength.restype = ctypes.c_int32
    sal.rtl_uString_getStr.argtypes = (ustr,)
    sal.rtl_uString_getStr.restype = ctypes.c_void_p
    args = []
    for index in range(sal.osl_getCommandArgCount()):
        value = ustr()
        sal.rtl_uString_new(ctypes.byref(value))  # osl assigns into it, releasing what it held
        try:
            if sal.osl_getCommandArg(index, ctypes.byref(value)) == 0:
                length = sal.rtl_uString_getLength(value)
                args.append(ctypes.string_at(sal.rtl_uString_getStr(value), 2 * length).decode("utf-16-le", "replace"))
        finally:
            sal.rtl_uString_release(value)
    return args


def started_by_automation(env=None, read_args=command_args):
    """True when other software started this office (see the module docstring); False when unsure. Never raises."""
    env = os.environ if env is None else env
    if env.get(INTERACTIVE_ENV) == "1":
        return False
    try:
        return automated(read_args())
    except Exception:  # noqa: BLE001 - unreadable arguments: behave as for a person's start
        diag_log.exception("automation_start")
        return False
