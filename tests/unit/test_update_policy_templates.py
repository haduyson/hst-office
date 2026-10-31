# SPDX-License-Identifier: AGPL-3.0-only
"""The downloadable update-lock templates of the user guide (help/files) are exactly what
scripts/release/build-update-policy-oxt.py --templates writes, and each format carries the profile's locks.
tests/runtime/check-update-policy.py proves them in a real office (Linux here, Windows and macOS in CI)."""
import importlib.util
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from xml.dom import minidom

import _paths

FILES = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools", "help", "files")
SCRIPT = os.path.join(_paths.ROOT, "scripts", "release", "build-update-policy-oxt.py")
_spec = importlib.util.spec_from_file_location("build_update_policy", SCRIPT)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


class Templates(unittest.TestCase):
    def test_committed_templates_are_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, SCRIPT, "--templates", tmp], check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(sorted(os.listdir(tmp)), sorted(os.listdir(FILES)))
            for name in os.listdir(tmp):
                with open(os.path.join(tmp, name), "rb") as new, open(os.path.join(FILES, name), "rb") as old:
                    self.assertEqual(new.read(), old.read(), "%s is stale: run build-update-policy-oxt.py --templates" % name)

    def test_each_format_carries_the_locks(self):
        for name, (locks, _title) in gen.PROFILES.items():
            base = os.path.join(FILES, "hst-office-" + name)
            dom = minidom.parse(base + ".xcd")
            props = {p.getAttribute("oor:name"): (p.getAttribute("oor:finalized"), p.getElementsByTagName("value")[0].firstChild.data)
                     for p in dom.getElementsByTagName("prop")}
            self.assertEqual(props, {k: ("true", v) for k, v in locks})
            reg = open(base + ".reg", "rb").read().decode("ascii")
            self.assertTrue(reg.startswith("Windows Registry Editor Version 5.00\r\n"))
            self.assertNotIn("\n", reg.replace("\r\n", ""))
            self.assertIn("[-%s]" % gen.REG_KEY, reg)  # replaces any earlier lock
            for key, value in locks:
                self.assertIn('[%s\\%s]\r\n"Value"="%s"\r\n"Final"=dword:00000001' % (gen.REG_KEY, key, value), reg)
            profile = plistlib.load(open(base + ".mobileconfig", "rb"))
            self.assertEqual((profile["PayloadType"], profile["PayloadScope"], profile["PayloadIdentifier"]),
                             ("Configuration", "System", gen.MAC_IDENTIFIER))
            (payload,) = profile["PayloadContent"]
            self.assertEqual(payload["PayloadType"], gen.MAC_DOMAIN)
            self.assertEqual(payload["HSTUpdate"], {k: gen.typed(k, v) for k, v in locks})

    def test_profile_uuids_differ(self):
        ids = [plistlib.load(open(os.path.join(FILES, "hst-office-%s.mobileconfig" % n), "rb"))["PayloadUUID"] for n in gen.PROFILES]
        self.assertEqual(len(set(ids)), len(ids))


if __name__ == "__main__":
    unittest.main()
