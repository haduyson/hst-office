# SPDX-License-Identifier: AGPL-3.0-only
""""Cập nhật ngay" when the office does not close at once: refused quits, the extension's own open dialogs, and the
record that lets the next start reopen the documents."""
import unittest
from unittest import mock

import _paths  # noqa: F401
import test_update_job  # noqa: F401 - installs the UNO module stubs before hst_office.update_install is imported
from hst_office import update_install as install  # noqa: E402
from test_update_install import INFO, RESULT

TEXT = {"install_title": "t", "err_quit": "q", "retry": "r", "later": "l"}


class QuitRefused(unittest.TestCase):
    """The office did not close (a dialog or a save prompt): the user is told, never a silent "nothing happened"."""

    def run_install(self, results, answers):
        peer = mock.Mock()
        peer.isVisible.return_value = True
        with mock.patch.object(install, "launch_and_quit", side_effect=results) as launch, \
                mock.patch.object(install.launch, "end_own_dialogs", return_value=0), \
                mock.patch.object(install, "texts", return_value=TEXT), \
                mock.patch.object(install, "_ask", side_effect=answers) as ask:
            install.install(mock.Mock(), peer, RESULT, INFO)
        return launch, ask

    def test_refused_quit_is_reported_and_can_be_retried(self):
        launch, ask = self.run_install([False, True], ["retry"])
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(ask.call_args.args[3], "q")

    def test_later_keeps_the_office_open(self):
        launch, ask = self.run_install([False], ["later"])
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(ask.call_count, 1)

    def test_quitting_office_shows_nothing(self):
        for result in (True, None):  # quitting, or installing was turned off by the administrator meanwhile
            launch, ask = self.run_install([result], [])
            ask.assert_not_called()


class OwnDialogsFirst(unittest.TestCase):
    def test_open_extension_dialogs_are_ended_and_the_quit_waits_a_turn(self):
        posted = []
        ctx = mock.Mock()
        with mock.patch.object(install.launch, "end_own_dialogs", side_effect=[1, 0]) as end, \
                mock.patch.object(install.ui, "on_main_thread", side_effect=lambda c, fn: posted.append(fn)), \
                mock.patch.object(install, "launch_and_quit", return_value=True) as launch:
            install.install(ctx, None, RESULT, INFO)
            launch.assert_not_called()  # the welcome dialog of another window is still in its modal loop
            self.assertEqual(len(posted), 1)
            posted[0]()
        self.assertEqual(end.call_count, 2)
        launch.assert_called_once_with(ctx, RESULT, INFO)

    def test_the_wait_is_bounded(self):
        posted = []
        with mock.patch.object(install.launch, "end_own_dialogs", return_value=1), \
                mock.patch.object(install.ui, "on_main_thread", side_effect=lambda c, fn: posted.append(fn)), \
                mock.patch.object(install, "launch_and_quit", return_value=True) as launch:
            install.install(mock.Mock(), None, RESULT, INFO)
            while posted:
                posted.pop()()
        launch.assert_called_once()

    def test_end_own_dialogs_ends_every_open_extension_dialog(self):
        from hst_office import dialog_registry
        first, second = mock.Mock(), mock.Mock()
        second.endExecute.side_effect = RuntimeError("disposed")
        with mock.patch.object(dialog_registry, "OPEN", [first, second]):
            self.assertEqual(install.launch.end_own_dialogs(), 1)
        first.endExecute.assert_called_once_with()


class PendingRecord(unittest.TestCase):
    """The documents to reopen are recorded before the quit, and forgotten when the office stays open."""

    def launch(self, closing):
        import tempfile
        cache = tempfile.mkdtemp()
        ctx = mock.Mock()
        with mock.patch.object(install.platform, "system", return_value="Linux"), \
                mock.patch.object(install.installer, "cache_dir", return_value=cache), \
                mock.patch.object(install.linux_install, "linux_kind", return_value="deb"), \
                mock.patch.object(install, "office_paths", return_value=("/opt/hst-office1.0/program/soffice", None)), \
                mock.patch.object(install.update_config, "settings", return_value={"AllowInstall": True}), \
                mock.patch.object(install.resume, "document_urls", return_value=["file:///home/u/a.docx"]), \
                mock.patch.object(install.launch, "spawn_and_quit", return_value=closing) as quit_:
            result = install.launch_and_quit(ctx, dict(RESULT, path="/home/u/.cache/hst-office/update/x.deb"), INFO)
        quit_.assert_called_once()
        return result, install.resume.read(cache)

    def test_record_names_documents_and_releases_when_quitting(self):
        result, record = self.launch(True)
        self.assertIs(result, True)
        self.assertEqual((record["from"], record["to"], record["documents"]), ("1.0.0-beta.5", "1.0.0", ["file:///home/u/a.docx"]))

    def test_record_is_removed_when_the_office_stays_open(self):
        result, record = self.launch(False)
        self.assertIs(result, False)
        self.assertIsNone(record)


class DialogRegistry(unittest.TestCase):
    def test_a_dialog_is_listed_only_inside_its_modal_loop(self):
        from hst_office import dialog_registry
        dialog, seen = mock.Mock(), []
        dialog.execute.side_effect = lambda: seen.append(list(dialog_registry.OPEN)) or 1
        self.assertEqual(dialog_registry.execute(dialog), 1)
        dialog.execute.side_effect = RuntimeError("disposed")
        with self.assertRaises(RuntimeError):
            dialog_registry.execute(dialog)
        self.assertEqual((seen, dialog_registry.OPEN), ([[dialog]], []))


if __name__ == "__main__":
    unittest.main()
