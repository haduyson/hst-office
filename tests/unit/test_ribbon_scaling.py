# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon collapse ladder (vcl HstRibbonScaling.hxx from hst-ribbon-scaling-helper.patch).

The helper picks, for an available width, the size state of every ribbon group from an ordered
ladder, and moves groups from the right end into the overflow popup when the ladder is used up.
The header has no LibreOffice dependencies, so it is taken from the patch and compiled with a
small driver (skipped when no C++ compiler is available).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from ribbon_scaling_driver import DRIVER

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-scaling-helper.patch")
HEADER = "vcl/inc/HstRibbonScaling.hxx"


def header_from_patch():
    """Contents of the new ladder header as added by the patch."""
    text = open(PATCH, encoding="utf-8").read()
    match = re.search(r"^\+\+\+ b/" + re.escape(HEADER) + r"\n@@ [^\n]*\n((?:\+[^\n]*\n)+)", text, re.M)
    if not match:
        raise AssertionError(f"{HEADER} not added by {os.path.basename(PATCH)}")
    return "".join(line[1:] + "\n" for line in match.group(1).splitlines())


class RibbonScalingTest(unittest.TestCase):
    def test_patch_adds_header_without_libreoffice_types(self):
        header = header_from_patch()
        self.assertIn("namespace hst::ribbon", header)
        includes = re.findall(r"^#include\s+[<\"]([^>\"]+)[>\"]", header, re.M)
        self.assertEqual(sorted(includes), ["cstddef", "vector"])
        self.assertNotRegex(header, r"\b(OUString|tools::|vcl::|VclPtr|sal_)")

    @unittest.skipUnless(shutil.which("g++"), "no C++ compiler")
    def test_ladder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "HstRibbonScaling.hxx"), "w", encoding="utf-8") as handle:
                handle.write(header_from_patch())
            with open(os.path.join(tmp, "driver.cxx"), "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            exe = os.path.join(tmp, "driver")
            build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-o", exe,
                                    os.path.join(tmp, "driver.cxx")], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)


if __name__ == "__main__":
    unittest.main()
