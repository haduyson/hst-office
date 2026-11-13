# SPDX-License-Identifier: AGPL-3.0-only
"""UNO component entry point registered in META-INF/manifest.xml (application/vnd.sun.star.uno-component;type=Python).

The office loads this file the first time it needs any HST service, and the first one is the crash job at OnStartApp,
while the splash screen is up. So this file imports no HST module itself: every service is registered by name with a
constructor that imports its module when the office first creates it. Importing every module here took 0.26 s
(Windows) and 0.42 s (Linux) of each start before the first window (scripts/perf/startup-timing.py on GitHub runners).
"""
import importlib
import os
import sys

# The office's Python loader does not add this extension's python/ directory to sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import unohelper  # noqa: E402

JOB = ("com.sun.star.task.Job",)
PROTOCOL_HANDLER = ("com.sun.star.frame.ProtocolHandler",)
# (module in hst_office, class, implementation name, service names); each name equals the module's own constant
# (tests/unit/test_component_lazy_registration.py)
SERVICES = (
    ("dispatch", "Handler", "org.hst.office.vi.DispatchProvider", PROTOCOL_HANDLER),
    ("welcome_job", "WelcomeJob", "org.hst.office.vi.WelcomeJob", JOB),
    ("update_job", "UpdateCheckJob", "org.hst.office.vi.UpdateCheckJob", JOB),
    ("update_handler", "UpdateHandler", "org.hst.office.vi.UpdateDispatchProvider", PROTOCOL_HANDLER),
    ("mail_merge_handler", "MailMergeHandler", "org.hst.office.vi.MailMergeDispatchProvider", PROTOCOL_HANDLER),
    ("mail_merge_menu", "MailMergeMenu", "org.hst.office.vi.MailMergeMenu", ("com.sun.star.frame.PopupMenuController",)),
    ("startup_prompts", "StartupPromptsJob", "org.hst.office.vi.StartupPromptsJob", JOB),
    ("options_page", "OptionsPageHandler", "org.hst.office.vi.OptionsPage", ("org.hst.office.vi.OptionsPage",)),
    ("appearance_options", "AppearanceOptionsHandler", "org.hst.office.vi.OptionsAppearance",
     ("org.hst.office.vi.OptionsAppearance",)),
    ("update_options", "UpdateOptionsHandler", "org.hst.office.vi.OptionsUpdate", ("org.hst.office.vi.OptionsUpdate",)),
    ("error_report_crash", "CrashReportJob", "org.hst.office.vi.CrashReportJob", JOB),
    ("vba_save_check", "VbaSaveCheckJob", "org.hst.office.vi.VbaSaveCheckJob", JOB),
    ("version_job", "PreviousVersionsJob", "org.hst.office.vi.PreviousVersionsJob", JOB),
    ("version_options", "PreviousVersionsOptionsHandler", "org.hst.office.vi.OptionsPreviousVersions",
     ("org.hst.office.vi.OptionsPreviousVersions",)),
    ("number_words_options", "NumberWordsOptionsHandler", "org.hst.office.vi.OptionsNumberWords",
     ("org.hst.office.vi.OptionsNumberWords",)),
    # asked by the core before an Excel file is written (hst-save-format-check.patch)
    ("save_format_check", "SaveFormatCheck", "org.hst.office.vi.SaveFormatCheck", ("org.hst.office.vi.SaveFormatCheck",)),
    ("banner_uno", "BannerService", "org.hst.office.BannerFeed", ("org.hst.office.BannerFeed",) + JOB),
    ("banner_uno", "BannerStartup", "org.hst.office.BannerStartup", ("org.hst.office.BannerStartup",) + JOB),
)


def lazy(module, name):
    """A constructor for unohelper's factory (called as ctor(ctx, *args)) that imports hst_office.<module> first."""
    def create(ctx, *args):
        return getattr(importlib.import_module("hst_office." + module), name)(ctx, *args)
    create.__qualname__ = "%s.%s" % (module, name)
    return create


g_ImplementationHelper = unohelper.ImplementationHelper()
for _module, _class, _implementation, _services in SERVICES:
    g_ImplementationHelper.addImplementation(lazy(_module, _class), _implementation, _services)

# Sheets functions: their interface type comes from types/hst-calc-functions.rdb. Should it be missing, only the
# functions are lost, never the other HST services of this component. Registered only when the type exists, as before.
try:
    from hst_office.calc_functions import SERVICES as CALC_SERVICES, implementation as _calc_functions  # noqa: E402
    g_ImplementationHelper.addImplementation(_calc_functions(), CALC_SERVICES[0], CALC_SERVICES)
except Exception:  # noqa: BLE001 - see above
    import traceback
    traceback.print_exc()
