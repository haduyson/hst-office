# SPDX-License-Identifier: AGPL-3.0-only
"""The HST settings (org.hasontech.hstoffice.*) are core configuration schemas, not extension schemas.

configmgr reads the user's registrymodifications.xcu before the profile's extension registration is complete when that
registration is missing or being renewed; values of a schema it does not know then are dropped (the welcome dialog came
back). hst-extension-settings-core.patch adds every HST settings schema to main.xcd, with the same paths and defaults,
and the bundled extension stops shipping them (one definition only)."""
import os
import re
import unittest

import _paths
import core_settings_schemas as core

EXT = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
PATCHES = os.path.join(_paths.ROOT, "patches", "libreoffice")
PYTHON = os.path.join(EXT, "python")
# what the 1.0.2 extension shipped: component -> {property: default value text, None when the schema gives none}
SHIPPED_1_0_2 = {
    "Banners": {"FeedURL": ""},
    "Citations": {"OnlineLookup": "true", "LookupContact": ""},
    "DefaultApps": {"Ask": "true", "Asked": "0", "LastAsked": "0", "Done": "false", "Release": ""},
    "ErrorReport": {"AskAfterCrash": "true"},
    "FeatureSearch": {"BubbleShown": "false", "Recent": None},
    "Nd30": {"AgencyRule": "2/5"},
    "NumberWords": {"Money": "false", "Formula": "false", "Unit": "đồng", "SubUnit": "", "MoneyOptions": "",
                    "NumberOptions": ""},
    "PreviousVersions": {"Enabled": "true"},
    "SaveFormatCheck": {"Remembered": ""},
    "UpdateCheck": {"AutoCheck": "true", "AllowInstall": "true", "LastCheck": "0", "SkippedVersion": "",
                    "SendInstallId": "true", "InstallId": ""},
    "Welcome": {"Shown": "false"},
}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class CoreSchemas(unittest.TestCase):
    def test_every_component_the_code_reads_is_a_core_schema(self):
        used = set()
        for base, _dirs, names in os.walk(PYTHON):
            for name in names:
                if name.endswith(".py"):
                    used.update(re.findall(r'"/org\.hasontech\.hstoffice\.(\w+)', read(os.path.join(base, name))))
        for name in os.listdir(PATCHES):
            if name.endswith(".patch"):
                used.update(re.findall(r'"/org\.hasontech\.hstoffice\.(\w+)"', read(os.path.join(PATCHES, name))))
        self.assertTrue(used)
        self.assertLessEqual(used, set(core.components()))

    def test_same_paths_properties_and_defaults_as_1_0_2(self):
        self.assertEqual(core.components(), sorted(SHIPPED_1_0_2))
        for component, props in SHIPPED_1_0_2.items():
            root = core.schema_root(component)
            self.assertEqual((root.get(core.OOR + "package"), root.get(core.OOR + "name")),
                             ("org.hasontech.hstoffice", component))
            got = {p.get(core.OOR + "name"): p.findtext("value") for p in root.find("component").iter("prop")}
            self.assertEqual(got, props, component)

    def test_schema_files_are_valid_officecfg_sources(self):
        for component in core.components():
            text = core.schema_text(component)
            self.assertTrue(text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n'), component)
            self.assertIn("http://mozilla.org/MPL/2.0/", text)
            # officecfg/registry/schema/org/hasontech/hstoffice/X.xcs -> officecfg/registry/component-schema.dtd
            self.assertIn('<!DOCTYPE oor:component-schema SYSTEM "../../../../component-schema.dtd">', text)

    def test_built_and_packed_into_main_xcd(self):
        patch = read(core.PATCH)
        listed = re.search(r"officecfg_HST_XCSFILES := \\\n((?:\+\t\w+ \\\n)+)", patch).group(1)
        self.assertEqual(sorted(re.findall(r"\t(\w+)", listed)), core.components())
        self.assertIn("$(addprefix org/hasontech/hstoffice/,$(addsuffix .xcs,$(officecfg_HST_XCSFILES)))", patch)
        packed = re.search(r"postprocess_FILES_main \+= \$\(addprefix \$\(call gb_XcsTarget_get_target,"
                           r"org/hasontech/hstoffice\)/,\\\n((?:\+\t\w+\.xcs(?: \\|\))\n)+)", patch).group(1)
        self.assertEqual(sorted(re.findall(r"\t(\w+)\.xcs", packed)), core.components())
        series = read(os.path.join(PATCHES, "series")).split()
        self.assertIn("hst-extension-settings-core.patch", series)


class ExtensionShipsNoSchema(unittest.TestCase):
    def test_no_schema_file_or_manifest_entry(self):
        self.assertEqual([n for n in os.listdir(EXT) if n.endswith(".xcs")], [])
        manifest = read(os.path.join(EXT, "META-INF", "manifest.xml"))
        self.assertNotIn("configuration-schema", manifest)

    def test_the_extension_data_still_fills_the_core_schema(self):
        data = read(os.path.join(EXT, "FeatureSearch.xcu"))
        self.assertIn('oor:name="FeatureSearch" oor:package="org.hasontech.hstoffice"', data)
        self.assertIn('full-path="FeatureSearch.xcu"', read(os.path.join(EXT, "META-INF", "manifest.xml")))
        templates = core.schema_text("FeatureSearch")
        self.assertIn('<group oor:name="Entry">', templates)
        self.assertIn('<set oor:name="Keywords" oor:node-type="Entry"/>', templates)

    def test_the_package_check_rejects_a_schema_in_the_extension(self):
        import importlib.util
        import io
        import zipfile
        spec = importlib.util.spec_from_file_location("extension_content",
                                                      os.path.join(_paths.ROOT, "scripts", "extension_content.py"))
        content = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(content)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("welcome.xcs", "<x/>")
            archive.writestr("META-INF/manifest.xml", "<manifest/>")
        errors = []
        with zipfile.ZipFile(buffer) as archive:
            content.check_registration(archive, set(archive.namelist()), errors)
        self.assertTrue(any("welcome.xcs" in e and "core" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
