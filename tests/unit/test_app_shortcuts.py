# SPDX-License-Identifier: AGPL-3.0-only
"""HST Writer, HST Sheets and HST Slides outside the office: Dock tiles (macOS) and desktop launchers (Linux).
Nothing on this machine is changed."""
import os
import plistlib
import stat
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import _paths  # noqa: F401
from hst_office import app_shortcuts as sc

HOST = "/Applications/HST Office.app"
LAUNCHER = """[Desktop Entry]
Version=1.0
Type=Application
Name=%s
Name[vi]=%s
Icon=vn.hasontech.hstoffice-writer
Exec=hst-office1.0 --writer %%U
"""


def dock(*paths, other=()):
    tiles = [{"tile-data": {"file-data": {"_CFURLString": sc.dock_url(p), "_CFURLStringType": 15}},
              "tile-type": "file-tile"} for p in paths]
    tiles += [{"tile-data": {"file-data": {"_CFURLString": url}}} for url in other]
    return {"persistent-apps": tiles, "persistent-others": []}


class Done:
    def __init__(self, returncode=0, stdout=b""):
        self.returncode, self.stdout = returncode, stdout


class MacDock(unittest.TestCase):
    def test_launchers_live_in_the_bundle_helpers_folder(self):
        self.assertEqual(sc.mac_launchers(HOST), [
            ("HST Writer", HOST + "/Contents/Helpers/HST Writer.app"),
            ("HST Sheets", HOST + "/Contents/Helpers/HST Sheets.app"),
            ("HST Slides", HOST + "/Contents/Helpers/HST Slides.app")])

    def test_url_is_percent_encoded_with_a_trailing_slash(self):
        self.assertEqual(sc.dock_url(HOST + "/Contents/Helpers/HST Writer.app"),
                         "file:///Applications/HST%20Office.app/Contents/Helpers/HST%20Writer.app/")

    def test_tile_is_a_plist_dict_with_escaped_text(self):
        tile = sc.dock_tile("A & B", "/Users/x/R&D/HST Office.app/Contents/Helpers/HST Writer.app")
        root = ET.fromstring(tile)
        self.assertEqual(root.tag, "dict")
        parsed = plistlib.loads(('<?xml version="1.0" encoding="UTF-8"?><plist version="1.0">%s</plist>' % tile).encode())
        self.assertEqual(parsed["tile-type"], "file-tile")
        self.assertEqual(parsed["tile-data"]["file-label"], "A & B")
        url = parsed["tile-data"]["file-data"]["_CFURLString"]
        self.assertEqual(url, "file:///Users/x/R%26D/HST%20Office.app/Contents/Helpers/HST%20Writer.app/")
        self.assertEqual(parsed["tile-data"]["file-data"]["_CFURLStringType"], 15)

    def test_only_missing_launchers_are_added(self):
        launchers = sc.mac_launchers(HOST)
        self.assertEqual(sc.missing_from_dock(launchers, dock()), launchers)
        pinned = dock(launchers[1][1], other=("file:///Applications/Safari.app/", "https://example.com/", 7))
        self.assertEqual(sc.missing_from_dock(launchers, pinned), [launchers[0], launchers[2]])
        self.assertEqual(sc.missing_from_dock(launchers, dock(*(p for _n, p in launchers))), [])
        self.assertEqual(sc.missing_from_dock(launchers, {}), launchers)
        self.assertEqual(sc.missing_from_dock(launchers, {"persistent-apps": [{"tile-type": "spacer-tile"}]}), launchers)

    def test_add_writes_each_tile_checks_then_restarts_the_dock(self):
        launchers = sc.mac_launchers(HOST)
        calls = []

        def run(argv, input=None, capture_output=True, timeout=None, check=False):
            calls.append(argv)
            if argv[:2] == ["defaults", "export"]:
                return Done(0, plistlib.dumps(dock(*(p for _n, p in launchers))))
            return Done()
        with mock.patch.object(sc.subprocess, "run", side_effect=run):
            sc.add_to_dock(launchers)
        writes = [c for c in calls if c[:2] == ["defaults", "write"]]
        self.assertEqual(len(writes), 3)
        self.assertTrue(all(c[2:5] == ["com.apple.dock", "persistent-apps", "-array-add"] for c in writes))
        self.assertEqual(calls[-1], ["killall", "Dock"])

    def test_dock_not_restarted_when_the_tiles_did_not_stick(self):
        calls = []

        def run(argv, **_kwargs):
            calls.append(argv)
            return Done(0, plistlib.dumps(dock())) if argv[1] == "export" else Done()
        with mock.patch.object(sc.subprocess, "run", side_effect=run):
            with self.assertRaises(sc.ShortcutError):
                sc.add_to_dock(sc.mac_launchers(HOST))
        self.assertNotIn(["killall", "Dock"], calls)

    def test_failed_write_stops_before_the_restart(self):
        with mock.patch.object(sc.subprocess, "run", return_value=Done(1)) as run:
            with self.assertRaises(sc.ShortcutError) as caught:
                sc.add_to_dock(sc.mac_launchers(HOST))
        self.assertIn("HST Writer", str(caught.exception))
        self.assertEqual(run.call_count, 1)

    def test_unreadable_dock_settings_are_reported(self):
        for done in (Done(1), Done(0, b"not a plist")):
            with mock.patch.object(sc.subprocess, "run", return_value=done):
                with self.assertRaises(sc.ShortcutError):
                    sc.read_dock()
        with mock.patch.object(sc.subprocess, "run", side_effect=OSError("no defaults")):
            with self.assertRaises(sc.ShortcutError):
                sc.read_dock()

    def test_bundle_without_launchers_is_reported_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "Contents", "Helpers", "HST Writer.app"))
            with self.assertRaises(sc.ShortcutError) as caught:
                sc.dock_status(tmp)
        self.assertIn("HST Sheets, HST Slides", str(caught.exception))


class LinuxDesktop(unittest.TestCase):
    def test_desktop_folder_from_user_dirs(self):
        self.assertEqual(sc.desktop_dir("/home/an", {}, 'XDG_DESKTOP_DIR="$HOME/Màn hình nền"\n'), "/home/an/Màn hình nền")
        self.assertEqual(sc.desktop_dir("/home/an", {}, 'XDG_DESKTOP_DIR="/data/desk"\n'), "/data/desk")
        # disabled ($HOME itself), relative or absent: the usual ~/Desktop
        for text in ('XDG_DESKTOP_DIR="$HOME/"\n', 'XDG_DESKTOP_DIR="desk"\n', "# none\n", ""):
            self.assertEqual(sc.desktop_dir("/home/an", {}, text), "/home/an/Desktop", text)

    def test_desktop_folder_read_from_config_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "user-dirs.dirs"), "w", encoding="utf-8") as handle:
                handle.write('XDG_DESKTOP_DIR="$HOME/Bureau"\n')
            self.assertEqual(sc.desktop_dir("/home/an", {"XDG_CONFIG_HOME": tmp}), "/home/an/Bureau")

    def write_launchers(self, base, names=None):
        apps = os.path.join(base, "applications")
        os.makedirs(apps)
        for module, name in sc.APPS:
            with open(os.path.join(apps, sc.DESKTOP_IDS[module]), "w", encoding="utf-8") as handle:
                handle.write(LAUNCHER % (((names or {}).get(name, name),) * 2))
        return [base]

    def test_copies_the_three_launchers_executable_and_replaces_on_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            launchers = sc.installed_launchers(self.write_launchers(os.path.join(tmp, "share")))
            self.assertEqual([n for n, _d, _p in launchers], ["HST Writer", "HST Sheets", "HST Slides"])
            desk = os.path.join(tmp, "Màn hình nền")
            with mock.patch.object(sc.shutil, "which", return_value="/usr/bin/gio"), \
                    mock.patch.object(sc.subprocess, "run", return_value=Done()) as run:
                first = sc.copy_to_desktop(launchers, desk)
                second = sc.copy_to_desktop(launchers, desk)
            self.assertEqual(first, second)
            self.assertEqual(sorted(os.listdir(desk)), sorted(sc.DESKTOP_IDS.values()))
            for path in first:
                self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR)
            trusted = [c.args[0] for c in run.call_args_list]
            self.assertEqual(trusted[:3], [["gio", "set", p, "metadata::trusted", "true"] for p in first])

    def test_works_without_gio(self):
        with tempfile.TemporaryDirectory() as tmp:
            launchers = sc.installed_launchers(self.write_launchers(os.path.join(tmp, "share")))
            with mock.patch.object(sc.shutil, "which", return_value=None), mock.patch.object(sc.subprocess, "run") as run:
                self.assertEqual(len(sc.copy_to_desktop(launchers, os.path.join(tmp, "Desktop"))), 3)
            run.assert_not_called()

    def test_missing_or_foreign_launcher_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sc.ShortcutError) as caught:
                sc.installed_launchers([tmp])
            self.assertIn("HST Writer, HST Sheets, HST Slides", str(caught.exception))
            launchers = sc.installed_launchers(self.write_launchers(os.path.join(tmp, "share"), {"HST Sheets": "Other"}))
            with self.assertRaises(sc.ShortcutError):
                sc.copy_to_desktop(launchers, os.path.join(tmp, "Desktop"))

    def test_launcher_check(self):
        self.assertTrue(sc.check_launcher(LAUNCHER % ("HST Writer", "HST Writer"), "HST Writer"))
        self.assertFalse(sc.check_launcher("[Desktop Entry]\nType=Link\nName=HST Writer\nURL=x\n", "HST Writer"))
        self.assertFalse(sc.check_launcher("garbage", "HST Writer"))


if __name__ == "__main__":
    unittest.main()
