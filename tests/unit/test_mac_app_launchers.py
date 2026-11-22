# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The macOS app launchers copied out of HST Office.app into /Applications or ~/Applications: first start, refresh
after an update, no duplicates, removal and re-adding (office side: test_mac_app_launchers_ui.py).
Everything happens in a temporary folder; ditto is emulated by a tree copy."""
import os
import plistlib
import shutil
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401
from hst_office import mac_app_launchers as ml

HOST_ID = "vn.hasontech.hstoffice"
SUFFIX = {"HST Writer": "writer", "HST Sheets": "sheets", "HST Slides": "slides", "HST Draw": "draw", "HST PDF": "pdf"}


class Done:
    def __init__(self, returncode=0):
        self.returncode, self.stdout, self.stderr = returncode, b"", b""


def write_info(app, info):
    os.makedirs(os.path.join(app, "Contents"), exist_ok=True)
    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as handle:
        plistlib.dump(info, handle)


class Machine(unittest.TestCase):
    """A home folder, a stand-in for /Applications and an HST Office bundle with its five launchers."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.home = os.path.join(self.root, "home")
        self.system = os.path.join(self.root, "Applications")
        os.makedirs(self.system)
        patcher = mock.patch.object(ml, "SYSTEM_FOLDER", self.system)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bundle = os.path.join(self.system, "HST Office.app")
        self.make_host("1.0.3.100")
        self.calls = []

    def make_host(self, version, names=ml.NAMES):
        shutil.rmtree(self.bundle, ignore_errors=True)
        write_info(self.bundle, {"CFBundleIdentifier": HOST_ID, "CFBundleVersion": version})
        for name in names:
            write_info(os.path.join(self.bundle, "Contents", "Helpers", name + ".app"),
                       {"CFBundleIdentifier": "%s.launcher.%s" % (HOST_ID, SUFFIX[name]), "CFBundleVersion": version})

    def run_tool(self, argv):
        self.calls.append(argv)
        if argv[0] == "ditto":
            shutil.copytree(argv[-2], argv[-1], symlinks=True)
        return Done()

    def sync(self, writable=True):
        return ml.sync(self.bundle, self.home, lambda _path: writable, self.run_tool)

    def version_of(self, folder, name):
        return ml.read_info(os.path.join(folder, name + ".app")).get("CFBundleVersion")


class FirstStart(Machine):
    def test_all_five_go_to_applications_with_a_notice(self):
        state = self.sync()
        self.assertEqual(ml.present(self.system, HOST_ID), list(ml.NAMES))
        self.assertEqual((state["folder"], state["notice"], state["version"]), (self.system, "pending", "1.0.3.100"))
        self.assertEqual(ml.load_state(self.home)["installed"], list(ml.NAMES))
        ditto = [argv for argv in self.calls if argv[0] == "ditto"]
        self.assertEqual(len(ditto), 5)
        self.assertTrue(all(argv[1] == "--noqtn" for argv in ditto))  # the app's own copies carry no quarantine
        self.assertEqual(self.calls[-1][:2], [ml.LSREGISTER, "-f"])
        self.assertEqual([n for n in os.listdir(self.system) if n.startswith(".")], [])  # no partial copy left

    def test_user_folder_when_applications_needs_a_password(self):
        state = self.sync(writable=False)
        user = os.path.join(self.home, "Applications")
        self.assertEqual(state["folder"], user)
        self.assertEqual(ml.present(user, HOST_ID), list(ml.NAMES))
        self.assertEqual(ml.present(self.system, HOST_ID), [])

    def test_second_start_changes_nothing(self):
        self.sync()
        self.calls.clear()
        self.assertIsNone(self.sync())
        self.assertEqual(self.calls, [])
        self.assertEqual(ml.load_state(self.home)["notice"], "pending")

    def test_another_apps_bundle_of_the_same_name_is_left_alone(self):
        foreign = os.path.join(self.system, "HST PDF.app")
        write_info(foreign, {"CFBundleIdentifier": "com.example.pdf"})
        self.sync()
        self.assertEqual(ml.read_info(foreign)["CFBundleIdentifier"], "com.example.pdf")
        self.assertEqual(ml.load_state(self.home)["installed"], list(ml.NAMES[:4]))

    def test_failed_copy_keeps_the_old_launcher_and_leaves_no_partial_copy(self):
        self.sync()
        self.make_host("1.0.4.1")

        def broken(argv):
            if argv[0] == "ditto":
                os.makedirs(argv[-1])
                return Done(1)
            return Done()
        with self.assertRaises(ml.LauncherError):
            ml.sync(self.bundle, self.home, lambda _p: True, broken)
        self.assertEqual(self.version_of(self.system, "HST Writer"), "1.0.3.100")
        self.assertEqual([n for n in os.listdir(self.system) if n.startswith(".")], [])
        self.assertEqual(ml.load_state(self.home)["version"], "1.0.3.100")  # tried again at the next start

    def test_a_bundle_without_launchers_is_reported(self):
        self.make_host("1.0.3.100", names=ml.NAMES[:3])
        with self.assertRaises(ml.LauncherError):
            self.sync()


class Update(Machine):
    def test_new_version_replaces_the_copies_in_place(self):
        self.sync()
        self.make_host("1.0.4.1")
        state = self.sync()
        self.assertEqual([self.version_of(self.system, n) for n in ml.NAMES], ["1.0.4.1"] * 5)
        self.assertEqual(ml.present(self.system, HOST_ID), list(ml.NAMES))
        self.assertEqual(sorted(os.listdir(self.system)), sorted(["HST Office.app"] + [n + ".app" for n in ml.NAMES]))
        self.assertEqual(state["notice"], "pending")  # an update never adds a second notice

    def test_a_launcher_the_user_deleted_stays_deleted(self):
        self.sync()
        shutil.rmtree(os.path.join(self.system, "HST Draw.app"))
        self.make_host("1.0.4.1")
        self.sync()
        self.assertEqual(ml.present(self.system, HOST_ID), [n for n in ml.NAMES if n != "HST Draw"])

    def test_a_launcher_new_in_this_version_is_added(self):
        ml.install(self.bundle, ml.NAMES[:3], self.home, lambda _p: True, self.run_tool)
        ml.save_state({"version": "1.0.2.9", "folder": self.system, "installed": list(ml.NAMES[:3])}, self.home)
        self.sync()
        self.assertEqual(ml.present(self.system, HOST_ID), list(ml.NAMES))

    def test_launchers_already_in_the_user_folder_are_never_doubled(self):
        self.sync(writable=False)
        os.remove(os.path.join(self.home, *ml.STATE))  # even without the state file
        self.sync(writable=True)
        self.assertEqual(ml.present(self.system, HOST_ID), [])
        self.assertEqual(ml.present(os.path.join(self.home, "Applications"), HOST_ID), list(ml.NAMES))


class RemoveAndAdd(Machine):
    def test_removed_launchers_are_not_copied_again(self):
        self.sync()
        removed = ml.remove(HOST_ID, self.home)
        ml.set_removed(True, "1.0.3.100", home=self.home)
        self.assertEqual(len(removed), 5)
        self.make_host("1.0.4.1")
        self.assertIsNone(self.sync())
        self.assertEqual(ml.present(self.system, HOST_ID), [])
        self.assertTrue(os.path.isdir(self.bundle))  # HST Office itself is never touched

    def test_added_again_and_refreshed_after_the_next_update(self):
        self.sync()
        ml.remove(HOST_ID, self.home)
        ml.set_removed(True, "1.0.3.100", home=self.home)
        folder, copied = ml.install(self.bundle, home=self.home, writable=lambda _p: True, run=self.run_tool)
        ml.set_removed(False, "1.0.3.100", folder, self.home)
        self.assertEqual((folder, copied), (self.system, list(ml.NAMES)))
        self.make_host("1.0.4.1")
        self.sync()
        self.assertEqual([self.version_of(self.system, n) for n in ml.NAMES], ["1.0.4.1"] * 5)
        self.assertEqual(ml.load_state(self.home)["notice"], "shown")

    def test_plan(self):
        self.assertEqual(ml.plan({}, "2", []), list(ml.NAMES))
        self.assertEqual(ml.plan({"version": "2"}, "2", []), [])
        self.assertEqual(ml.plan({"version": "1", "removed": True}, "2", list(ml.NAMES)), [])
        self.assertEqual(ml.plan({"version": "1", "installed": list(ml.NAMES)}, "2", ["HST PDF"]), ["HST PDF"])


if __name__ == "__main__":
    unittest.main()
