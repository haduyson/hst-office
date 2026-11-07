# SPDX-License-Identifier: AGPL-3.0-only
"""check-msi-upgrade.py: HST Office's own UpgradeCode and the bounded removal of the LibreOffice-coded betas."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_msi_upgrade", ROOT / "scripts/check-msi-upgrade.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
HST, LO = MOD.HST_UPGRADE_CODE, MOD.LIBREOFFICE_UPGRADE_CODE
HEADER = "UpgradeCode\tVersionMin\tVersionMax\tLanguage\tAttributes\tRemove\tActionProperty\ns38\tS20\tS20\tS255\ti4\tS255\ts72\nUpgrade\tUpgradeCode\tVersionMin\tVersionMax\tLanguage\tAttributes\n"
# Upgrade table of the first beta.5 candidate (msiinfo export), built with LibreOffice's code.
RC_UPGRADE = HEADER + f"{LO}\t\t1.0.0.500\t\t513\t\tOLDPRODUCTS\n{LO}\t1.0.0.500\t\t\t2\t\tNEWPRODUCTS\n"
PROPERTIES = {"UpgradeCode": HST, "ProductCode": "{E50EE16B-3A90-40B3-BE64-CB7DB8597BCB}",
              "SecureCustomProperties": "NEWPRODUCTS;OLDPRODUCTS;WINMAJORVER;INSTALLLOCATION;HSTLEGACYPRODUCTS"}


def row(code, low, high, attributes, action):
    return {"UpgradeCode": code, "VersionMin": low, "VersionMax": high, "Attributes": attributes, "ActionProperty": action}


def good_rows():
    return [row(HST, "", "1.0.0.500", 513, "OLDPRODUCTS"), row(HST, "1.0.0.500", "", 2, "NEWPRODUCTS"),
            row(LO, "1.0.0.0", "1.0.1.0", 257, "OLDPRODUCTS"), row(LO, "1.0.0.0", "1.0.1.0", 258, "HSTLEGACYPRODUCTS")]


def good_actions():
    """CustomAction and sequence rows of the beta.5 MSI around FindRelatedProducts, plus the forced-reinstall actions."""
    actions = {"HstLegacyReinstallMode": (51, "REINSTALLMODE", "amus"), "HstLegacyNoVcRedist": (51, "VC_REDIST", "0"),
               "SetAdminInstallProperty": (51, "ADMININSTALL", "1"), "ISInitAllUsers": (307, "ALLUSERS", "1")}
    sequences = {
        "InstallExecuteSequence": [("Shellextensionsdll5", "Not REMOVE=\"ALL\" And Not PATCH", 98), ("FindRelatedProducts", "", 100),
                                   ("HstLegacyReinstallMode", "HSTLEGACYPRODUCTS", 101), ("HstLegacyNoVcRedist", "HSTLEGACYPRODUCTS", 102),
                                   ("CheckInstallDirectory", "Not Installed", 106), ("CostInitialize", "", 350), ("ISInitAllUsers", "Not Installed And Privileged", 525)],
        "InstallUISequence": [("FindRelatedProducts", "", 150), ("HstLegacyReinstallMode", "HSTLEGACYPRODUCTS", 151),
                              ("HstLegacyNoVcRedist", "HSTLEGACYPRODUCTS", 152), ("CostInitialize", "", 400)]}
    return actions, sequences


class Rules(unittest.TestCase):
    def test_hst_code_with_bounded_legacy_removal_passes(self):
        self.assertEqual(MOD.validate(good_rows(), PROPERTIES), [])

    def test_hst_code_is_new_and_permanent(self):
        self.assertNotEqual(HST, LO)
        self.assertRegex(HST, MOD.GUID)
        self.assertIn(HST, (ROOT / "docs/BUILD_MATRIX.md").read_text(encoding="utf-8"))

    def test_candidate_built_with_libreoffice_code_fails(self):
        rows = MOD.upgrade_rows(MOD.parse_idt(RC_UPGRADE))
        errors = MOD.validate(rows, dict(PROPERTIES, UpgradeCode=LO))
        self.assertTrue(any("LibreOffice's" in e for e in errors), errors)
        self.assertTrue(any("newer-version detection" in e for e in errors), errors)

    def test_newer_version_detection_only_on_hst_code(self):
        rows = good_rows() + [row(LO, "1.0.0.0", "1.0.1.0", 2, "NEWPRODUCTS")]
        self.assertTrue(any("newer-version detection" in e for e in MOD.validate(rows, PROPERTIES)))

    def test_legacy_row_must_stay_below_3_0(self):
        for low, high in (("1.0.0.0", ""), ("", "1.0.1.0"), ("1.0.0.0", "3.0.0.0"), ("1.0.0.0", "26.8.1.1")):
            rows = good_rows()[:2] + [row(LO, low, high, 257, "OLDPRODUCTS")]
            self.assertTrue(MOD.validate(rows, PROPERTIES), (low, high))

    def test_legacy_row_must_cover_the_betas(self):
        # Only the first three fields count: an exclusive maximum of 1.0.0.500 leaves out 1.0.0.1.
        for rows in (good_rows()[:2], good_rows()[:2] + [row(LO, "1.0.0.0", "1.0.0.500", 257, "OLDPRODUCTS")]):
            self.assertTrue(any("betas installed under LibreOffice" in e for e in MOD.validate(rows, PROPERTIES)))

    def test_action_property_must_be_secure(self):
        rows = good_rows()[:2] + [row(LO, "1.0.0.0", "1.0.1.0", 257, "LEGACYPRODUCTS")]
        errors = MOD.validate(rows, PROPERTIES)
        self.assertTrue(any("SecureCustomProperties" in e for e in errors), errors)

    def test_legacy_detect_row_is_required(self):
        errors = MOD.validate(good_rows()[:3], PROPERTIES)
        self.assertTrue(any("detect-only row sets HSTLEGACYPRODUCTS" in e for e in errors), errors)

    def test_legacy_detect_row_must_stay_on_the_legacy_range(self):
        for bad in (row(LO, "1.0.0.0", "26.8.1.1", 258, "HSTLEGACYPRODUCTS"), row(HST, "1.0.0.0", "1.0.1.0", 258, "HSTLEGACYPRODUCTS"),
                    row(LO, "1.0.0.0", "1.0.1.0", 2, "OLDPRODUCTS")):
            self.assertTrue(MOD.validate(good_rows() + [bad], PROPERTIES), bad)

    def test_global_forced_reinstall_is_rejected(self):
        errors = MOD.validate(good_rows(), dict(PROPERTIES, REINSTALLMODE="amus"))
        self.assertTrue(any("C++ runtime" in e for e in errors), errors)

    def test_forced_reinstall_actions_pass(self):
        self.assertEqual(MOD.forced_reinstall_errors(*good_actions()), [])

    def test_beta5_without_the_actions_fails(self):
        actions, sequences = good_actions()
        sequences = {t: [r for r in rows if not r[0].startswith("HstLegacy")] for t, rows in sequences.items()}
        self.assertEqual(len(MOD.forced_reinstall_errors(actions, sequences)), 4)

    def test_forced_reinstall_must_be_conditional_and_before_costing(self):
        for table, index, change in (("InstallExecuteSequence", 2, ("HstLegacyReinstallMode", "", 101)),
                                     ("InstallExecuteSequence", 3, ("HstLegacyNoVcRedist", "HSTLEGACYPRODUCTS", 400)),
                                     ("InstallUISequence", 1, ("HstLegacyReinstallMode", "HSTLEGACYPRODUCTS", 149))):
            actions, sequences = good_actions()
            sequences[table][index] = change
            errors = MOD.forced_reinstall_errors(actions, sequences)
            self.assertEqual(len(errors), 1, (change, errors))
            self.assertIn(table, errors[0])

    def test_forced_reinstall_values_and_extra_setters(self):
        actions, sequences = good_actions()
        actions["HstLegacyReinstallMode"] = (51, "REINSTALLMODE", "omus")
        self.assertTrue(MOD.forced_reinstall_errors(actions, sequences))
        actions, sequences = good_actions()
        actions["Other"] = (51, "VC_REDIST", "1")
        sequences["InstallExecuteSequence"].append(("Other", "", 700))
        self.assertTrue(any("VC_REDIST" in e for e in MOD.forced_reinstall_errors(actions, sequences)))

    def test_bad_version_text_is_reported(self):
        rows = good_rows()[:2] + [row(LO, "1.0.0.0", "1.0.x", 257, "OLDPRODUCTS")]
        self.assertTrue(any("is not a version" in e for e in MOD.validate(rows, PROPERTIES)))

    def test_version_ranges_ignore_the_fourth_field(self):
        legacy = row(LO, "1.0.0.0", "1.0.1.0", 257, "OLDPRODUCTS")
        for version, inside in (("1.0.0.1", True), ("1.0.0.401", True), ("1.0.1.1", False), ("3.3.0.4", False), ("26.8.1.1", False)):
            self.assertEqual(MOD.matches(legacy, version), inside, version)


class Sources(unittest.TestCase):
    def test_patch_series_generates_valid_rows(self):
        rows, properties = MOD.from_patch(MOD.PATCH.read_text(encoding="utf-8"), MOD.repo_msi_version(), legacy_detect=True)
        secure, actions, sequences = MOD.from_legacy_patch(MOD.LEGACY_PATCH.read_text(encoding="utf-8"))
        self.assertEqual(MOD.validate(rows, properties | secure), [])
        self.assertEqual(MOD.forced_reinstall_errors(actions, sequences), [])
        self.assertEqual(properties["UpgradeCode"], HST)
        self.assertIn("HSTLEGACYPRODUCTS", secure["SecureCustomProperties"].split(";"))

    def test_patch_is_in_the_series(self):
        series = (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split()
        for patch in (MOD.PATCH, MOD.LEGACY_PATCH):
            self.assertIn(patch.name, series)
        self.assertLess(series.index(MOD.PATCH.name), series.index(MOD.LEGACY_PATCH.name))

    def test_legacy_patch_without_the_detect_row_is_rejected(self):
        text = MOD.LEGACY_PATCH.read_text(encoding="utf-8").replace('"258"', '"257"')
        with self.assertRaises(ValueError):
            MOD.from_legacy_patch(text)

    def test_patch_without_codes_file_is_rejected(self):
        with self.assertRaises(ValueError):
            MOD.from_patch("+            CODEFILENAME codes_hst.txt\n", "1.0.0.500")

    def test_component_guid_seed_is_set(self):
        self.assertEqual(MOD.seed_errors(MOD.SEED_PATCH.read_text(encoding="utf-8")), [])
        self.assertIn(MOD.SEED_PATCH.name, (ROOT / "patches/libreoffice/series").read_text(encoding="utf-8").split())
        self.assertTrue(MOD.seed_errors("+            COMPONENTGUIDSEED 1.0\n"))

    def test_beta_component_guids_are_reported(self):
        # soffice.com's GUID in the beta.4 MSI and in the first beta.5 build (same seed, PRODUCTVERSION 1.0).
        name = "auto_brand_exe_soffice_com__hstoffice_program"
        self.assertEqual(MOD.legacy_guid(name), "{B79CFE98-60B6-93CD-3878-9FFACB645578}")
        self.assertTrue(MOD.component_errors([(name, "{B79CFE98-60B6-93CD-3878-9FFACB645578}")]))
        self.assertEqual(MOD.component_errors([(name, "{4405A3C3-6CFB-E049-C203-040EE1EAA400}")]), [])

    def test_parse_idt_pads_missing_columns(self):
        rows = MOD.parse_idt(HEADER + f"{HST}\t1.0.0.500\n")
        self.assertEqual(rows[0]["ActionProperty"], "")
        with self.assertRaises(ValueError):
            MOD.upgrade_rows([{"UpgradeCode": HST, "Attributes": "x"}])


if __name__ == "__main__":
    unittest.main()
