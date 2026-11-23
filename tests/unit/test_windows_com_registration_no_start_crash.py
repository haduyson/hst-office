# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""hst-windows-com-registration-no-start-crash.patch: a COM component Windows does not load ends no start.

Desktop::OpenClients_Impl creates OleApplicationRegistration (oleautobridgelo.dll) and EmbedServer at every
Windows start with nothing catching a failure; a user's 1.0.3 crashed seconds after every start with an unhandled
CannotActivateFactoryException ("loading component library <...> failed"). The start-up path is Windows-only and
needs a broken install to fail, so the check here is the patch hunk."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/libreoffice/hst-windows-com-registration-no-start-crash.patch"
SERIES = ROOT / "patches/libreoffice/series"
SERVICES = ("com.sun.star.bridge.OleApplicationRegistration", "com.sun.star.comp.ole.EmbedServer")


def added_and_removed():
    lines = PATCH.read_text(encoding="utf-8").split("\n--- a/desktop/source/app/app.cxx\n", 1)[1].splitlines()
    added = [line[1:].strip() for line in lines if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:].strip() for line in lines if line.startswith("-")]
    return added, removed


class WindowsComRegistrationNoStartCrash(unittest.TestCase):
    def test_patch_in_series(self):
        self.assertIn(PATCH.name, SERIES.read_text(encoding="utf-8").split())

    def test_each_registration_is_tried_and_caught(self):
        added, removed = added_and_removed()
        for service in SERVICES:
            self.assertIn(f'xSMgr->createInstance("{service}");', removed)
            self.assertTrue(any(f'"{service}"' in line for line in added), service)
        code = [line for line in added if line and not line.startswith("//")]
        start = code.index("try")
        self.assertIn("xSMgr->createInstance(OUString::createFromAscii(pService));", code[start:start + 3])
        self.assertIn("catch (const css::uno::Exception&)", code[start:])
        self.assertTrue(code[0].startswith("for (const char* pService"), "one try per service")
        self.assertFalse([line for line in added if "createInstance" in line and "pService" not in line])


if __name__ == "__main__":
    unittest.main()
