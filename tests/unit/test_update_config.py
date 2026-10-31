# SPDX-License-Identifier: AGPL-3.0-only
"""Update-check settings without an office: precedence of administrator locks, value clamping, the one-time
migration of the old extension settings and macOS managed preferences (plist files in a temporary folder)."""
import os
import plistlib
import tempfile
import unittest

import _paths  # noqa: F401

from hst_office import update_config as cfg  # noqa: E402


def layer(finalized=(), **values):
    return {k: (v, k in finalized) for k, v in values.items()}


class Resolve(unittest.TestCase):
    def test_defaults_without_any_schema(self):
        values, locked = cfg.resolve(None, None, {})
        self.assertEqual(values, cfg.DEFAULTS)
        self.assertEqual(locked, set())

    def test_user_value_from_core(self):
        values, locked = cfg.resolve(layer(AutoCheck=False, CheckIntervalHours=48), None, {})
        self.assertFalse(values["AutoCheck"])
        self.assertEqual(values["CheckIntervalHours"], 48)
        self.assertEqual(locked, set())

    def test_core_finalized_wins_over_everything(self):
        core = layer(("AutoCheck",), AutoCheck=False)
        legacy = layer(("AutoCheck",), AutoCheck=True)
        values, locked = cfg.resolve(core, legacy, {"AutoCheck": True})
        self.assertFalse(values["AutoCheck"])
        self.assertEqual(locked, {"AutoCheck"})

    def test_managed_preference_locks(self):
        values, locked = cfg.resolve(layer(AllowInstall=True), None, {"AllowInstall": False, "Channel": "stable"})
        self.assertFalse(values["AllowInstall"])
        self.assertEqual(values["Channel"], "stable")
        self.assertEqual(locked, {"AllowInstall", "Channel"})

    def test_old_policy_oxt_still_locks(self):
        core = layer(AutoCheck=True, AllowInstall=True)
        legacy = layer(("AutoCheck", "AllowInstall"), AutoCheck=False, AllowInstall=False)
        values, locked = cfg.resolve(core, legacy, {})
        self.assertFalse(values["AutoCheck"])
        self.assertFalse(values["AllowInstall"])
        self.assertEqual(locked, {"AutoCheck", "AllowInstall"})

    def test_legacy_user_value_is_not_a_lock(self):
        values, locked = cfg.resolve(layer(AutoCheck=True), layer(AutoCheck=False), {})
        self.assertTrue(values["AutoCheck"])  # migration copies it; resolve only follows the core
        self.assertEqual(locked, set())

    def test_old_core_without_schema_uses_legacy_values(self):
        values, _ = cfg.resolve(None, layer(AutoCheck=False, SkippedVersion="1.0.0-beta.3"), {})
        self.assertFalse(values["AutoCheck"])
        self.assertEqual(values["SkippedVersion"], "1.0.0-beta.3")

    def test_values_are_clamped(self):
        values, _ = cfg.resolve(layer(CheckIntervalHours=0, Channel="Nightly"), None, {})
        self.assertEqual(values["CheckIntervalHours"], 1)
        self.assertEqual(values["Channel"], "")
        self.assertEqual(cfg.normalize("CheckIntervalHours", 99999), 8760)
        self.assertEqual(cfg.normalize("CheckIntervalHours", "x"), 24)
        self.assertEqual(cfg.normalize("Channel", " Beta "), "beta")


class Migration(unittest.TestCase):
    def test_copies_changed_user_values_once(self):
        core = layer(AutoCheck=True, AllowInstall=True, LastCheck=0, SkippedVersion="")
        legacy = layer(AutoCheck=False, AllowInstall=True, LastCheck=1700000000, SkippedVersion="1.0.0-beta.3")
        self.assertEqual(cfg.migration_plan(core, legacy),
                         {"AutoCheck": False, "LastCheck": 1700000000, "SkippedVersion": "1.0.0-beta.3"})

    def test_skips_locked_and_already_set_values(self):
        core = layer(("AutoCheck",), AutoCheck=True, LastCheck=1800000000, SkippedVersion="")
        legacy = layer(("SkippedVersion",), AutoCheck=False, LastCheck=1700000000, SkippedVersion="1.0.0-beta.3")
        self.assertEqual(cfg.migration_plan(core, legacy), {})

    def test_nothing_without_legacy_schema(self):
        self.assertEqual(cfg.migration_plan(layer(AutoCheck=True), None), {})


class MacosManaged(unittest.TestCase):
    def write(self, path, doc):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            plistlib.dump(doc, fh)

    def test_computer_and_user_profiles(self):
        with tempfile.TemporaryDirectory() as base:
            self.write(os.path.join(base, "vn.hasontech.hstoffice.plist"),
                       {"HSTUpdate": {"AutoCheck": False, "AllowInstall": False, "Unknown": 1}, "Other": True})
            self.write(os.path.join(base, "an", "vn.hasontech.hstoffice.plist"),
                       {"HSTUpdate": {"AllowInstall": True, "CheckIntervalHours": 168}})
            self.assertEqual(cfg.macos_managed("an", base),
                             {"AutoCheck": False, "AllowInstall": True, "CheckIntervalHours": 168})
            self.assertEqual(cfg.macos_managed("binh", base), {"AutoCheck": False, "AllowInstall": False})

    def test_missing_or_broken_profiles(self):
        with tempfile.TemporaryDirectory() as base:
            self.assertEqual(cfg.macos_managed("an", os.path.join(base, "none")), {})
            with open(os.path.join(base, "vn.hasontech.hstoffice.plist"), "wb") as fh:
                fh.write(b"not a plist")
            self.assertEqual(cfg.macos_managed("an", base), {})


if __name__ == "__main__":
    unittest.main()
