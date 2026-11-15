# SPDX-License-Identifier: AGPL-3.0-only
"""The GUI harness drives only its own office: when another office (e.g. the same check running in parallel with the
same deterministic port) answers on the UNO port, hst_gui refuses it instead of sending every call there."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
import hst_gui  # noqa: E402


class _PathSubstitution:
    def __init__(self, user):
        self.user = user

    def getSubstituteVariableValue(self, name):  # noqa: N802 - UNO method name
        assert name == "$(user)"
        return self.user


class _ServiceManager:
    def __init__(self, user):
        self.user = user

    def createInstanceWithContext(self, name, _ctx):  # noqa: N802 - UNO method name
        assert name == "com.sun.star.util.PathSubstitution"
        return _PathSubstitution(self.user)


class _Context:
    def __init__(self, user):
        self.ServiceManager = _ServiceManager(user)  # noqa: N815 - UNO attribute name


class OwnOfficeTest(unittest.TestCase):
    def setUp(self):
        self.office = hst_gui.Office("/opt/hst-office1.0", "/data/runs/tệp a", 22164)

    def test_own_profile_is_accepted(self):
        hst_gui.ensure_own_office(_Context("file:///data/runs/t%E1%BB%87p%20a/profile/user/"), self.office.workdir, 22164)

    def test_another_office_on_the_port_is_refused(self):
        with self.assertRaises(hst_gui.ForeignOfficeError) as raised:
            hst_gui.ensure_own_office(_Context("file:///data/runs/other/profile/user"), self.office.workdir, 22164)
        self.assertIn("22164", str(raised.exception))

    def test_refusal_stops_only_our_own_process(self):
        stopped = []

        def taken():
            raise hst_gui.ForeignOfficeError("taken")
        self.office._connect = taken
        self.office.stop = lambda: stopped.append(self.office.ctx)  # ctx None: stop() ends our process only
        with self.assertRaises(hst_gui.ForeignOfficeError):
            self.office._connect_own()
        self.assertEqual(stopped, [None])


if __name__ == "__main__":
    unittest.main()
