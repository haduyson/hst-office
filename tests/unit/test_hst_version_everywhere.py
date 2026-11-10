# SPDX-License-Identifier: AGPL-3.0-only
"""Sources of every place a user sees a version: the HST release, never the engine version (26.8) or LibreOffice.

Works on the patch series alone (no LibreOffice tree): for each source file it follows the lines that the
series adds and removes in order, so a later patch that brings back the engine version, the upstream generator
or "Calc" fails here. tests/runtime/check-hst-version-everywhere.py checks the same on a built program.
"""
import collections
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches" / "libreoffice"
FORBIDDEN = re.compile(r"\b26\.8\b|LibreOffice", re.IGNORECASE)
# Upstream calls that return the engine version.
ENGINE_CALLS = re.compile(r"getProductVersion\(\)|getAboutBoxProductVersion\(\)|LIBO_VERSION_DOTTED\b")


def series():
    return [line.strip() for line in (PATCHES / "series").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def file_lines(path):
    """(lines the series adds and keeps, upstream lines the series removes) for one source file."""
    added, removed = collections.Counter(), collections.Counter()
    for name in series():
        current = None
        for line in (PATCHES / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("+++ "):
                current = line[4:].split("\t")[0].removeprefix("b/")
            elif line.startswith("--- ") or line.startswith("@@"):
                continue
            elif current == path and line.startswith("+"):
                added[line[1:]] += 1
            elif current == path and line.startswith("-"):
                if added[line[1:]]:
                    added[line[1:]] -= 1
                else:
                    removed[line[1:]] += 1
    return +added, +removed


def code(lines):
    """Added lines without comments, joined: what the compiler sees of the series' changes."""
    return "\n".join(re.sub(r"//.*$", "", line) for line in lines if not line.strip().startswith("//"))


class GeneratorMetadata(unittest.TestCase):
    """meta:generator (ODF) and docProps/app.xml Application (OOXML) both come from GetGeneratorString."""

    def test_generator_is_hst_release_without_engine_or_upstream_project(self):
        added, removed = file_lines("unotools/source/config/docinfohelper.cxx")
        body = code(added)
        self.assertIn('u"HSTOffice/" HST_RELEASE "$"_ustr + os + "_" + arch', body)
        self.assertIn("#include <hst_version.h>", body)
        self.assertIn('                aResult.append( "LibreOffice_project/" );', removed)
        self.assertIn("                aValue = utl::ConfigManager::getProductVersion();", removed)
        self.assertNotRegex(body, FORBIDDEN)
        self.assertNotRegex(body, ENGINE_CALLS)

    def test_import_maps_hst_documents_to_their_engine_version(self):
        added, _ = file_lines("xmloff/source/meta/xmlmetai.cxx")
        body = code(added)
        self.assertIn('o3tl::starts_with(i_rBuildId, u"HSTOffice/")', body)
        # HST Office 1.0.x documents were written by engine 26.8 (LO_268 in SvXMLImport).
        self.assertIn('if (o3tl::starts_with(aRelease, u"1.0."))\n            sBuildId += ";26.8";', body)
        self.assertIn('sBuildId += ";" LIBO_VERSION_DOTTED_2;', body)

    def test_ooxml_app_version_is_left_to_the_compatibility_value(self):
        # AppVersion "15.0000" is what other office suites parse; it must not become the HST version.
        for name in series():
            text = (PATCHES / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\+.*AppVersion.*HST_", name)


class ExportedFiles(unittest.TestCase):
    def test_pdf_producer_and_creator(self):
        added, removed = file_lines("filter/source/pdf/pdfexport.cxx")
        body = code(added)
        self.assertIn('" " HST_RELEASE " (" + arch + ")"', body)
        self.assertIn("                        utl::ConfigManager::getAboutBoxProductVersion() +", removed)
        for name in ("HST Writer", "HST Sheets", "HST Slides"):
            self.assertIn(f'u"{name}"_ustr', body)
        self.assertIn('"HST " + aCreator', body)
        self.assertNotRegex(body, ENGINE_CALLS)

    def test_eps_creator(self):
        added, removed = file_lines("vcl/source/filter/eps/eps.cxx")
        self.assertIn('getProductName() + " " HST_RELEASE;', code(added))
        self.assertIn("                   utl::ConfigManager::getProductVersion();", removed)

    def test_full_version_variable_is_the_hst_release(self):
        # HTML export generator: "%PRODUCTNAME %PRODUCTVERSION%PRODUCTEXTENSION (%1)" was "HST Office 1.0.1.1".
        added, _ = file_lines("desktop/source/app/app.cxx")
        self.assertIn('"%PRODUCTVERSION%PRODUCTEXTENSION", u"" HST_RELEASE ""_ustr', code(added))
        # It must run before the plain "%PRODUCTVERSION" (HST major.minor) replacement.
        patch = (PATCHES / "hst-version-everywhere.patch").read_text(encoding="utf-8")
        self.assertLess(patch.index("%PRODUCTVERSION%PRODUCTEXTENSION"),
                        patch.index('sRet.replaceAll( "%PRODUCTVERSION", sVersion )'))

    def test_object_names_and_message_titles_use_the_string_hook(self):
        for path in ("svtools/source/dialogs/insdlg.cxx", "sw/source/ui/config/optload.cxx", "uui/source/iahndl.cxx"):
            added, removed = file_lines(path)
            self.assertIn("Translate::ExpandVariables", code(added), path)
            self.assertTrue(any("getProductVersion()" in line for line in removed), path)


class AboutDialog(unittest.TestCase):
    def test_copy_text_and_misc_line(self):
        added, removed = file_lines("cui/source/dialogs/about.cxx")
        body = code(added)
        self.assertNotIn("Engine", body)
        self.assertNotIn("GetEngineVersion", body)
        self.assertIn('    sMisc += "Calc:" + aCalcMode;', removed)
        self.assertIn('return "Sheets: " + aCalcMode;', body)
        self.assertIn(r'u"t\u00EDnh \u0111a lu\u1ED3ng"_ustr', body)  # "tính đa luồng"
        self.assertIn('u"" HST_RELEASE " ("', body)
        self.assertNotRegex(body, ENGINE_CALLS)
        self.assertNotRegex(re.sub(r"Calc::|// .*", "", body), r'"[^"]*\bCalc\b')


class OperatingSystemFields(unittest.TestCase):
    def test_windows_version_resource_is_the_hst_release(self):
        added, removed = file_lines("include/default.rc")
        body = code(added)
        for line in ("FILEVERSION    HST_VERSION_MAJOR, HST_VERSION_MINOR, HST_VERSION_MICRO, HST_VERSION_BUILD",
                     'VALUE "ProductVersion",   HST_RELEASE "\\0"', 'VALUE "FileVersion",      HST_FILE_VERSION "\\0"',
                     'VALUE "ProductName",      "HST Office\\0"'):
            self.assertIn(line, body)
        self.assertNotRegex(body, r"\bLIBO_VERSION|\b26\.8\b")

    def test_windows_launcher_descriptions_use_hst_app_names(self):
        for module, name in (("scalc", "HST Sheets"), ("simpress", "HST Slides"), ("swriter", "HST Writer"),
                             ("sweb", "HST Writer (Web)")):
            added, _ = file_lines(f"desktop/Executable_{module}.mk")
            self.assertIn(f"$(eval $(call gb_Executable_add_default_nativeres,{module},{name}))", added)

    def test_release_file_is_a_plain_hst_release(self):
        release = json.loads((ROOT / "data/hst/release.json").read_text(encoding="utf-8"))["release"]
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertTrue(release.startswith(version), release)
        self.assertNotRegex(release, FORBIDDEN)


class SeriesOrder(unittest.TestCase):
    def test_version_patch_follows_the_about_and_title_patches(self):
        names = series()
        last = names.index("hst-version-everywhere.patch")
        for earlier in ("hst-about.patch", "hst-version.patch", "hst-window-title.patch", "hst-copyright.patch"):
            self.assertLess(names.index(earlier), last, earlier)


if __name__ == "__main__":
    unittest.main()
