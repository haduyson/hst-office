# SPDX-License-Identifier: AGPL-3.0-only
"""Anonymous install ID of the update check, without an office: ID format, persistence, opt-out (user and
administrator settings) and the query string. The request itself: test_update_install_id_request.py."""
import os
import unittest
import uuid
import xml.etree.ElementTree as ET
from unittest import mock

import _paths
from install_id_support import EXT, ID, OOR, FakeConfig, cfg
from hst_office import update_install_id as iid  # noqa: E402
from hst_office import update_logic as logic  # noqa: E402


class Format(unittest.TestCase):
    def test_new_ids_are_random_uuid4(self):
        ids = {iid.new_install_id() for _ in range(200)}
        self.assertEqual(len(ids), 200)
        for value in ids:
            self.assertTrue(iid.is_install_id(value), value)
            self.assertEqual(uuid.UUID(value).version, 4)
            self.assertEqual(str(uuid.UUID(value)), value)  # canonical lowercase form

    def test_id_is_not_derived_from_the_machine(self):
        # uuid1 carries the MAC address and time: never accepted, never created
        self.assertFalse(iid.is_install_id(str(uuid.uuid1())))
        with mock.patch.object(uuid, "getnode", side_effect=AssertionError("hardware read")):
            self.assertTrue(iid.is_install_id(iid.new_install_id()))

    def test_only_canonical_uuid4_is_accepted(self):
        for bad in ("", None, 42, ID.upper(), "{%s}" % ID, ID + " ", ID.replace("-", ""), "x" * 36,
                    ID[:14] + "1" + ID[15:]):
            self.assertFalse(iid.is_install_id(bad), bad)
        self.assertTrue(iid.is_install_id(ID))


class Persistence(unittest.TestCase):
    def test_choose(self):
        self.assertEqual(iid.choose(dict(cfg.DEFAULTS, InstallId=ID)), (ID, None))
        self.assertEqual(iid.choose(dict(cfg.DEFAULTS), create=lambda: ID), (ID, ID))
        self.assertEqual(iid.choose(dict(cfg.DEFAULTS, InstallId="garbage"), create=lambda: ID), (ID, ID))
        self.assertEqual(iid.choose(dict(cfg.DEFAULTS, SendInstallId=False, InstallId=ID)), (None, None))

    def test_first_check_creates_and_stores_then_reuses(self):
        config = FakeConfig().patch(self)
        first = iid.for_check(None)
        self.assertTrue(iid.is_install_id(first))
        self.assertEqual(config.saves, [("InstallId", first)])
        self.assertEqual(iid.for_check(None), first)
        self.assertEqual(iid.for_check(None), first)
        self.assertEqual(len(config.saves), 1)  # stored once, the same ID afterwards

    def test_opted_out_sends_and_creates_nothing(self):
        config = FakeConfig(SendInstallId=False).patch(self)
        self.assertIsNone(iid.for_check(None))
        self.assertEqual(config.saves, [])
        config.values["InstallId"] = ID  # an ID from before the opt-out stays unused
        self.assertIsNone(iid.for_check(None))

    def test_unstorable_id_is_not_sent(self):
        # a read-only profile would otherwise count as a new machine at every check
        FakeConfig(writable=False).patch(self)
        self.assertIsNone(iid.for_check(None))

    def test_failure_never_breaks_the_check(self):
        with mock.patch.object(cfg, "settings", side_effect=RuntimeError("no config")), \
                mock.patch.object(iid.diag_log, "exception") as logged:
            self.assertIsNone(iid.for_check(None))
        logged.assert_called_once()


class Settings(unittest.TestCase):
    def layer(self, finalized=(), **values):
        return {k: (v, k in finalized) for k, v in values.items()}

    def test_defaults(self):
        values, locked = cfg.resolve(None, None, {})
        self.assertIs(values["SendInstallId"], True)
        self.assertEqual(values["InstallId"], "")
        self.assertEqual(locked, set())

    def test_user_values_live_in_the_extension_schema(self):
        legacy = self.layer(SendInstallId=False, InstallId=ID)
        values, locked = cfg.resolve(self.layer(AutoCheck=True), legacy, {})
        self.assertEqual((values["SendInstallId"], values["InstallId"]), (False, ID))
        self.assertEqual(locked, set())

    def test_administrator_can_lock_it(self):
        values, locked = cfg.resolve(None, self.layer(("SendInstallId",), SendInstallId=False), {})
        self.assertIs(values["SendInstallId"], False)
        self.assertIn("SendInstallId", locked)
        values, locked = cfg.resolve(None, self.layer(SendInstallId=True), {"SendInstallId": False})  # macOS profile
        self.assertIs(values["SendInstallId"], False)
        self.assertIn("SendInstallId", locked)

    def test_core_schema_switch_wins_and_locks(self):
        # .xcd and the HKLM policy key reach only the core schema (read before the extension schemas)
        values, locked = cfg.resolve(self.layer(("SendInstallId",), SendInstallId=False),
                                     self.layer(SendInstallId=True, InstallId=ID), {})
        self.assertIs(values["SendInstallId"], False)
        self.assertIn("SendInstallId", locked)
        values, locked = cfg.resolve(self.layer(SendInstallId=False), self.layer(SendInstallId=True), {})
        self.assertIs(values["SendInstallId"], False)  # the user's core value
        self.assertEqual(locked, set())

    def test_policy_builder_locks_it(self):
        import importlib.util
        path = os.path.join(_paths.ROOT, "scripts", "release", "build-update-policy-oxt.py")
        spec = importlib.util.spec_from_file_location("build_update_policy_oxt", path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        locks = [("SendInstallId", "false")]
        self.assertIn('<prop oor:name="SendInstallId" oor:finalized="true" oor:op="fuse"><value>false</value></prop>',
                      builder.xcd_text(locks))
        self.assertIn("org.openoffice.Office.HSTUpdate\\SendInstallId]", builder.reg_text(locks))
        self.assertIs(builder.typed("SendInstallId", "false"), False)

    def test_install_id_is_not_an_administrator_setting(self):
        self.assertNotIn("InstallId", cfg.ADMIN_KEYS)
        self.assertIn("SendInstallId", cfg.ADMIN_KEYS)

    def test_schema_declares_both_properties(self):
        root = ET.parse(os.path.join(EXT, "update.xcs")).getroot()
        props = {p.get(OOR + "name"): p for p in root.iter("prop")}
        self.assertEqual(props["SendInstallId"].get(OOR + "type"), "xs:boolean")
        self.assertEqual(props["SendInstallId"].find("value").text, "true")
        self.assertEqual(props["InstallId"].get(OOR + "type"), "xs:string")
        self.assertIsNone(props["InstallId"].find("value").text)  # empty: created at the first check


class Query(unittest.TestCase):
    def test_feed_url(self):
        self.assertEqual(iid.feed_url(logic.MANIFEST_URL, ID), logic.MANIFEST_URL + "?i=" + ID)
        self.assertEqual(iid.feed_url("http://127.0.0.1:9/latest.json?x=1", ID), "http://127.0.0.1:9/latest.json?x=1&i=" + ID)

    def test_no_id_no_query(self):
        for value in (None, "", "not-an-id", ID + "&admin=1", "x\r\nHost: evil"):
            self.assertEqual(iid.feed_url(logic.MANIFEST_URL, value), logic.MANIFEST_URL, value)

    def test_url_with_id_stays_a_valid_fetch_url(self):
        self.assertTrue(logic.is_fetch_url(iid.feed_url(logic.MANIFEST_URL, ID)))


if __name__ == "__main__":
    unittest.main()
