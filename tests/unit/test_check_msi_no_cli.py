# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/check-msi-no-cli.py: no legacy CLI-UNO bridge file and no GAC assembly in the Windows MSI."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_msi_no_cli", ROOT / "scripts/check-msi-no-cli.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

CONF = "--host=x86_64-pc-cygwin\n--without-java\n--without-dotnet\n--disable-cli\n--disable-odk\n"


def files(*names):
    return [{"File": f"f{i}", "Component_": "c", "FileName": name} for i, name in enumerate(names)]


def tables(file_rows, remove="675", initialize="700", **extra):
    sequence = [{"Action": "RemoveExistingProducts", "Condition": "", "Sequence": remove},
                {"Action": "InstallInitialize", "Condition": "", "Sequence": initialize}]
    return {"File": file_rows, "InstallExecuteSequence": sequence} | extra


class Msi(unittest.TestCase):
    def test_clean_msi_passes(self):
        rows = files("SOFFICE.BIN|soffice.bin", "cli-32.exe", "CLI-AR~1.EXE|cli-arm64.exe", "client.dll", "CPPUHE~1.DLL|cppuhelper3MSC.dll")
        self.assertEqual(check.msi_errors(tables(rows, MsiAssembly=[], MsiAssemblyName=[])), [])
        self.assertEqual(check.msi_errors(tables(rows)), [])  # the tables may be absent altogether

    def test_each_cli_file_fails(self):
        names = ("cli_ure.dll", "cli_uno.dll", "CLI_UR~1.DLL|cli_uretypes.dll", "POLICY~4.DLL|policy.1.0.cli_cppuhelper.dll",
                 "CLI_OO~2.CON|cli_oootypes.config", "CLI_BASETYPES.DLL")
        for name in names:
            with self.subTest(name=name):
                errors = check.msi_errors(tables(files("soffice.bin", name)))
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("CLI-UNO", errors[0])

    def test_assembly_rows_fail(self):
        row = {"Component_": "gid_file_dl_cli_ure_assembly", "Feature_": "gm_r_Ure_Hidden"}
        for table in ("MsiAssembly", "MsiAssemblyName"):
            with self.subTest(table=table):
                errors = check.msi_errors(tables(files("soffice.bin"), **{table: [row]}))
                self.assertEqual(len(errors), 1)
                self.assertIn("GAC", errors[0])

    def test_late_or_missing_remove_existing_products_fails(self):
        self.assertIn("after InstallInitialize", check.msi_errors(tables(files("soffice.bin"), remove="6550"))[0])
        bad = tables(files("soffice.bin"))
        bad["InstallExecuteSequence"] = bad["InstallExecuteSequence"][1:]
        self.assertIn("lacks RemoveExistingProducts", check.msi_errors(bad)[0])

    def test_empty_file_table_fails(self):
        self.assertTrue(check.msi_errors(tables([])))


class Sources(unittest.TestCase):
    def patch(self):
        return (ROOT / "patches/libreoffice" / check.PATCH).read_text(encoding="latin-1")

    def test_repository_passes(self):
        self.assertEqual(check.source_errors(*check.read_sources()), [])

    def test_configure_options(self):
        series, patches = [check.PATCH], {check.PATCH: self.patch()}
        self.assertEqual(check.source_errors(CONF, series, patches), [])
        self.assertEqual(len(check.source_errors(CONF.replace("--disable-cli\n", ""), series, patches)), 1)
        self.assertEqual(len(check.source_errors(CONF + "--enable-cli\n", series, patches)), 1)
        self.assertEqual(len(check.source_errors(CONF.replace("--without-dotnet", "--with-dotnet"), series, patches)), 2)
        self.assertEqual(len(check.source_errors(CONF + "# --enable-cli\n", series, patches)), 0)

    def test_patch_must_be_in_series_and_gate_every_item(self):
        self.assertIn("not in the patch series", check.source_errors(CONF, [], {})[0])
        weakened = self.patch().replace("+\tENABLE_CLI \\\n", "", 1)
        errors = check.source_errors(CONF, [check.PATCH], {check.PATCH: weakened})
        self.assertEqual(len(errors), 1)
        self.assertIn("ENABLE_CLI", errors[0])

    def test_a_patch_adding_a_gac_item_fails(self):
        extra = ("--- a/scp2/source/ooo/file_library_ooo.scp\n+++ b/scp2/source/ooo/file_library_ooo.scp\n@@ -1,1 +1,3 @@\n"
                 "+File gid_File_Lib_Cli_Hst\n+    Styles = (PACKED, ASSEMBLY);\n")
        series = [check.PATCH, "hst-extra.patch"]
        errors = check.source_errors(CONF, series, {check.PATCH: self.patch(), "hst-extra.patch": extra})
        self.assertEqual(len(errors), 1)
        self.assertIn("hst-extra.patch adds an ASSEMBLY", errors[0])


if __name__ == "__main__":
    unittest.main()
