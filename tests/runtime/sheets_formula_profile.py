# SPDX-License-Identifier: AGPL-3.0-only
"""Fresh soffice profile with a chosen UI language and locale, and the UNO connection to it.

Used by check-sheets-excel-formula-conventions.py: the profile stores UILocale and ooSetupSystemLocale before the
first start, and again after it in case the first start rewrote registrymodifications.xcu.
"""
import os
from pathlib import Path
import subprocess
import time

PROFILE_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Linguistic/General"><prop oor:name="UILocale" oor:op="fuse"><value>{ui}</value></prop></item>
<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooSetupSystemLocale" oor:op="fuse"><value>{loc}</value></prop></item>
</oor:items>
"""


def connect(uno, pipe, timeout=90):
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)  # calls made before startup settles get disposed
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:
            if time.time() > deadline:
                raise
            time.sleep(1)


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def start(program, profile, ui, loc, env):
    os.makedirs(os.path.join(profile, "user"))
    reg = os.path.join(profile, "user", "registrymodifications.xcu")
    with open(reg, "w", encoding="utf-8") as handle:
        handle.write(PROFILE_XCU.format(ui=ui, loc=loc))
    for _ in range(3):  # exit code 81 = restart requested while the profile is created
        warm = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore", "--terminate_after_init",
                               "-env:UserInstallation=" + Path(profile).absolute().as_uri()], env=env, timeout=180, check=False)
        if warm.returncode == 0:
            break
    with open(reg, encoding="utf-8") as handle:
        text = handle.read()
    if f"<value>{ui}</value>" not in text or f"<value>{loc}</value>" not in text:  # first start may rewrite the file
        items = PROFILE_XCU.format(ui=ui, loc=loc).split("\n", 2)[2].replace("</oor:items>\n", "")
        with open(reg, "w", encoding="utf-8") as handle:
            handle.write(text.replace("</oor:items>", items + "</oor:items>"))
    pipe = f"hstxlformula{os.getpid()}{ui}{loc}".replace("-", "")
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--norestore", "--nologo",
                             "-env:UserInstallation=" + Path(profile).absolute().as_uri(), f"--accept=pipe,name={pipe};urp;"], env=env)
    return proc, pipe
