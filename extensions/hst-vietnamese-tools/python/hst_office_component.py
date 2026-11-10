# SPDX-License-Identifier: AGPL-3.0-only
"""UNO component entry point registered in META-INF/manifest.xml (application/vnd.sun.star.uno-component;type=Python)."""
import os
import sys

# The office's Python loader does not add this extension's python/ directory to sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import unohelper  # noqa: E402

from hst_office.dispatch import IMPLEMENTATION_NAME, Handler  # noqa: E402
from hst_office.welcome_job import JOB_NAME, WelcomeJob  # noqa: E402
from hst_office.update_job import HANDLER_NAME, JOB_NAME as UPDATE_JOB_NAME, UpdateCheckJob, UpdateHandler  # noqa: E402
from hst_office.startup_prompts import JOB_NAME as STARTUP_JOB_NAME, StartupPromptsJob  # noqa: E402
from hst_office.options_page import HANDLER_NAME as OPTIONS_NAME, OptionsPageHandler  # noqa: E402
from hst_office.appearance_options import HANDLER_NAME as APPEARANCE_NAME, AppearanceOptionsHandler  # noqa: E402
from hst_office.update_options import HANDLER_NAME as UPDATE_OPTIONS_NAME, UpdateOptionsHandler  # noqa: E402
from hst_office.error_report_crash import JOB_NAME as CRASH_JOB_NAME, CrashReportJob  # noqa: E402
from hst_office.vba_save_check import JOB_NAME as VBA_SAVE_JOB_NAME, VbaSaveCheckJob  # noqa: E402
from hst_office.save_format_check import SERVICE_NAME as SAVE_CHECK_NAME, SaveFormatCheck  # noqa: E402

from hst_office.banner_uno import BannerService, BannerStartup, SERVICE_NAME, _START_NAME  # noqa: E402

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Handler, IMPLEMENTATION_NAME, ("com.sun.star.frame.ProtocolHandler",))
g_ImplementationHelper.addImplementation(WelcomeJob, JOB_NAME, ("com.sun.star.task.Job",))
g_ImplementationHelper.addImplementation(UpdateCheckJob, UPDATE_JOB_NAME, ("com.sun.star.task.Job",))
g_ImplementationHelper.addImplementation(UpdateHandler, HANDLER_NAME, ("com.sun.star.frame.ProtocolHandler",))
g_ImplementationHelper.addImplementation(StartupPromptsJob, STARTUP_JOB_NAME, ("com.sun.star.task.Job",))
g_ImplementationHelper.addImplementation(OptionsPageHandler, OPTIONS_NAME, (OPTIONS_NAME,))
g_ImplementationHelper.addImplementation(AppearanceOptionsHandler, APPEARANCE_NAME, (APPEARANCE_NAME,))
g_ImplementationHelper.addImplementation(UpdateOptionsHandler, UPDATE_OPTIONS_NAME, (UPDATE_OPTIONS_NAME,))
g_ImplementationHelper.addImplementation(CrashReportJob, CRASH_JOB_NAME, ("com.sun.star.task.Job",))
g_ImplementationHelper.addImplementation(VbaSaveCheckJob, VBA_SAVE_JOB_NAME, ("com.sun.star.task.Job",))
# asked by the core before an Excel file is written (hst-save-format-check.patch)
g_ImplementationHelper.addImplementation(SaveFormatCheck, SAVE_CHECK_NAME, (SAVE_CHECK_NAME,))
g_ImplementationHelper.addImplementation(BannerService, SERVICE_NAME, (SERVICE_NAME, "com.sun.star.task.Job"))
g_ImplementationHelper.addImplementation(BannerStartup, _START_NAME, (_START_NAME, "com.sun.star.task.Job"))

# Sheets functions: their interface type comes from types/hst-calc-functions.rdb. Should it be missing, only the
# functions are lost, never the other HST services of this component.
try:
    from hst_office.calc_functions import SERVICES as CALC_SERVICES, implementation as _calc_functions  # noqa: E402
    g_ImplementationHelper.addImplementation(_calc_functions(), CALC_SERVICES[0], CALC_SERVICES)
except Exception:  # noqa: BLE001 - see above
    import traceback
    traceback.print_exc()
