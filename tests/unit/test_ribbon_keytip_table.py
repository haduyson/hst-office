# SPDX-License-Identifier: AGPL-3.0-only
"""Key letters of the ribbon (sfx2 HstKeyTipTable.hxx from hst-ribbon-keytips.patch).

No tip may be a prefix of another on one level, a taken or missing letter gets a free one, and Y and Z stay reserved for
two-letter tips. The header has no LibreOffice dependencies, so it is taken from the patch and compiled with a small
driver (skipped when no C++ compiler is available).
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-keytips.patch")
HEADER = "sfx2/source/notebookbar/HstKeyTipTable.hxx"

DRIVER = r"""
#include "HstKeyTipTable.hxx"
#include <cstdio>
using namespace hst::keytips;
static int failures = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)
static bool prefixFree(const std::vector<std::string>& tips)
{
    for (size_t a = 0; a < tips.size(); ++a)
        for (size_t b = 0; b < tips.size(); ++b)
            if (a != b && tips[a].starts_with(tips[b]))
                return false;
    return true;
}
int main()
{
    const auto mixed = assign({ "V", "X", "C", "V", "", "FP", "F", "" });
    CHECK(mixed[0] == "V" && mixed[1] == "X" && mixed[5] == "FP");
    CHECK(mixed[3] != "V" && mixed[6] != "F");
    CHECK(prefixFree(mixed));
    const auto many = assign(std::vector<std::string>(60));
    CHECK(prefixFree(many));
    CHECK(many[0].size() == 1 && many[59].size() == 2);
    for (const std::string& tip : many)
        CHECK(tip.size() == 2 || (tip[0] != 'Y' && tip[0] != 'Z'));
    // the access keys Microsoft documents for the tabs
    CHECK(lookup(std::begin(TAB_KEYS), std::end(TAB_KEYS), "HomeLabel") == "H");
    CHECK(lookup(std::begin(TAB_KEYS), std::end(TAB_KEYS), "InsertLabel") == "N");
    CHECK(lookup(std::begin(TAB_KEYS), std::end(TAB_KEYS), "ReviewLabel") == "R");
    CHECK(lookup(std::begin(COMMAND_KEYS), std::end(COMMAND_KEYS), "Bold") == "1");
    CHECK(lookup(std::begin(COMMAND_KEYS), std::end(COMMAND_KEYS), "NoSuchCommand").empty());
    // one entry per id; Q stays free on the tab level for the feature search (owner, 2026-11-07)
    for (const Key* a = std::begin(COMMAND_KEYS); a != std::end(COMMAND_KEYS); ++a)
        for (const Key* b = a + 1; b != std::end(COMMAND_KEYS); ++b)
            CHECK(a->id != b->id);
    for (const Key& k : TAB_KEYS)
        CHECK(k.tip != "Q");
    std::printf("%d failures\n", failures);
    return failures != 0;
}
"""


def header_from_patch():
    with open(PATCH, encoding="utf-8") as handle:
        text = handle.read()
    section = re.split(r"(?m)^(?=--- )", text)
    body = next(part for part in section if f"+++ b/{HEADER}" in part)
    return "".join(line[1:] + "\n" for line in body.split("\n")[3:] if line.startswith("+"))


def header_from_series(work):
    """The header as the series leaves it: created by hst-ribbon-keytips.patch, then edited by later patches."""
    target = os.path.join(work, HEADER)
    os.makedirs(os.path.dirname(target))
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(header_from_patch())
    directory = os.path.dirname(PATCH)
    with open(os.path.join(directory, "series"), encoding="utf-8") as handle:
        names = [n.strip() for n in handle if n.strip() and not n.startswith("#")]
    later = names[names.index(os.path.basename(PATCH)) + 1:]
    for name in later:
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            if f"+++ b/{HEADER}" not in handle.read():
                continue
        hunks = subprocess.run(["filterdiff", "-i", f"*/{HEADER}", os.path.join(directory, name)], capture_output=True,
                               text=True, check=True).stdout
        subprocess.run(["patch", "-d", work, "-p1", "-s", "-f"], input=hunks, text=True, check=True)
    with open(target, encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(shutil.which("g++") and shutil.which("filterdiff") and shutil.which("patch"),
                     "no C++ compiler or patch tools")
class KeyTipTable(unittest.TestCase):
    def test_assignment(self):
        with tempfile.TemporaryDirectory() as work:
            header = header_from_series(os.path.join(work, "tree"))
            with open(os.path.join(work, "HstKeyTipTable.hxx"), "w", encoding="utf-8") as handle:
                handle.write(header)
            driver = os.path.join(work, "driver.cpp")
            with open(driver, "w", encoding="utf-8") as handle:
                handle.write(DRIVER)
            binary = os.path.join(work, "driver")
            subprocess.run(["g++", "-std=c++20", "-I", work, driver, "-o", binary], check=True)
            result = subprocess.run([binary], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
