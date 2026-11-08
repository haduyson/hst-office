# SPDX-License-Identifier: AGPL-3.0-only
"""Default-apps question per release: the profile outlives an uninstall (macOS keeps ~/Library/Application Support/
HSTOffice), so "Để sau" given to a pre-release must not snooze the next release. "Đồng ý" or a registration found on
the machine still end it for good. Without an office."""
import sys
import types
import unittest
from unittest import mock

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.lang"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import default_apps as da  # noqa: E402

DAY = 86400
NOW = 2_000_000_000
BETA = dict(da.DEFAULT_STATE, Asked=1, LastAsked=NOW - DAY, Release="1.0.0-beta.5")


class ForRelease(unittest.TestCase):
    def test_counts_of_an_earlier_release_start_again(self):
        state = da.for_release(BETA, "1.0.0")
        self.assertEqual((state["Asked"], state["LastAsked"], state["Release"]), (0, 0, "1.0.0"))
        self.assertTrue(da.should_ask(state, NOW, False))

    def test_profile_of_a_version_without_release_counts_as_earlier(self):
        old = dict(da.DEFAULT_STATE, Asked=3, LastAsked=NOW - DAY)
        old.pop("Release")
        self.assertTrue(da.should_ask(da.for_release(old, "1.0.0"), NOW, False))

    def test_same_release_keeps_snooze_and_limit(self):
        state = da.for_release(dict(BETA, Release="1.0.0"), "1.0.0")
        self.assertFalse(da.should_ask(state, NOW, False), "snoozed 14 days within the release")
        state = da.for_release(dict(BETA, Release="1.0.0", Asked=da.MAX_ASKS, LastAsked=0), "1.0.0")
        self.assertFalse(da.should_ask(state, NOW, False), "at most MAX_ASKS per release")

    def test_done_ends_it_for_every_later_release(self):
        state = da.for_release(dict(BETA, Done=True), "1.0.0")
        self.assertTrue(state["Done"])
        self.assertFalse(da.should_ask(state, NOW, False))

    def test_unknown_release_keeps_the_stored_counts(self):
        self.assertEqual(da.for_release(BETA, ""), BETA)


class StartupStepAcrossReleases(unittest.TestCase):
    def setUp(self):
        self.state = dict(BETA)
        for target, value in (("load_state", lambda ctx: dict(self.state)),
                              ("save_state", lambda ctx, s: self.state.update(s)),
                              ("_report", lambda *a, **k: None)):
            patcher = mock.patch.object(da, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, value in (("is_registered", False), ("system", "Linux")):
            patcher = mock.patch.object(da.osx, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_beta_later_does_not_snooze_the_release(self):
        self.assertFalse(da.offer_at_startup(None, now=NOW, release="1.0.0-beta.5",
                                             ask=lambda ctx, peer: self.fail("snoozed in the beta")))
        self.assertTrue(da.offer_at_startup(None, now=NOW, release="1.0.0", ask=lambda ctx, peer: False))
        self.assertEqual((self.state["Asked"], self.state["LastAsked"], self.state["Release"]), (1, NOW, "1.0.0"))
        self.assertFalse(da.offer_at_startup(None, now=NOW + DAY, release="1.0.0",
                                             ask=lambda ctx, peer: self.fail("snoozed within the release")))

    def test_agreed_in_the_beta_is_never_asked_again(self):
        self.state["Done"] = True
        self.assertFalse(da.offer_at_startup(None, now=NOW, release="1.0.0", ask=lambda ctx, peer: self.fail("asked")))

    def test_registered_ends_it_for_good(self):
        with mock.patch.object(da.osx, "is_registered", return_value=True):
            self.assertFalse(da.offer_at_startup(None, now=NOW, release="1.0.0", ask=lambda ctx, peer: self.fail("asked")))
        self.assertTrue(self.state["Done"])
        self.assertFalse(da.offer_at_startup(None, now=NOW, release="1.0.1", ask=lambda ctx, peer: self.fail("asked")))

    def test_mac_outside_applications_still_waits(self):
        with mock.patch.object(da.osx, "system", return_value="Darwin"), \
                mock.patch.object(da.osx, "mac_in_applications", return_value=False):
            self.assertFalse(da.offer_at_startup(None, now=NOW, release="1.0.0", ask=lambda ctx, peer: self.fail("asked")))
        self.assertEqual(self.state["Release"], "1.0.0-beta.5", "nothing written before the app is in /Applications")

    def test_release_comes_from_the_package_stamp(self):
        with mock.patch("hst_office.update_fetch.release_info", return_value={"release": "1.0.0"}):
            self.assertEqual(da._release(), "1.0.0")
        with mock.patch("hst_office.update_fetch.release_info", side_effect=OSError("no stamp")), \
                mock.patch("traceback.print_exc"):
            self.assertEqual(da._release(), "")


if __name__ == "__main__":
    unittest.main()
