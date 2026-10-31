# SPDX-License-Identifier: AGPL-3.0-only
"""User-visible results and restart decisions without touching tokens or user data."""
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import _paths
from hst_office import usb_token as action, usb_token_db as db, usb_token_nss as nss
from hst_office import usb_token_store as store
from hst_office.data_files import load_locale


class ActionTest(unittest.TestCase):
    def setUp(self):
        self.strings = load_locale("vi")["usbToken"]
        self.frame, self.ctx, self.box = Mock(), Mock(), Mock()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules, {"hst_office.dialogs": SimpleNamespace(message_box=self.box)}))
        action._pending_restart.clear()

    def test_windows_explains_without_database_or_detection(self):
        with patch.object(action, "platform_name", return_value="windows"), patch.object(action, "setup") as setup:
            action.run(self.ctx, self.frame)
        setup.assert_not_called()
        self.box.assert_called_once_with(self.ctx, self.frame.getContainerWindow(), self.strings["title"],
                                         self.strings["windows"], error=False)

    def test_error_shown_in_one_vietnamese_dialog(self):
        with patch.object(action, "platform_name", return_value="linux"), \
                patch.object(action, "setup", side_effect=PermissionError(13, "Permission denied")):
            action.run(self.ctx, self.frame)
        self.assertEqual(self.box.call_count, 1)
        self.assertIn("Chưa hoàn tất", self.box.call_args.args[3])
        self.assertIn("quyền", self.box.call_args.args[3])
        self.assertNotIn("Permission denied", self.box.call_args.args[3])
        self.assertNotIn("Errno", self.box.call_args.args[3])
        self.assertTrue(self.box.call_args.kwargs["error"])

    def test_missing_driver_gives_ca_guidance_without_download_links(self):
        text = action.result_text(self.strings, "/home/test/.pki/nssdb", [], False)
        for value in ("VNPT-CA Token Manager", "Viettel-CA", "BKAV-CA", "FPT-CA", "EasyCA", "MISA", "OpenSC"):
            self.assertIn(value, text)
        self.assertNotIn("https://", text)
        self.assertIn("Kho chứng thư", text)

    def test_mixed_results_show_path_status_restart_and_retry(self):
        rows = [dict(label="A", path="/a.so", status="added"), dict(label="B", path="/b.so", status="existing"),
                dict(label="C", path="/c.so", status="error", error="Thư viện không phù hợp")]
        text = action.result_text(self.strings, "/db", rows, True)
        for value in ("Đã tìm thấy và đăng ký: A", "Đã đăng ký từ trước: B", "chưa đăng ký được: C",
                      "/a.so", "/b.so", "/c.so", "/db", "Khởi động lại HST Office rồi", "Thư viện không phù hợp"):
            self.assertIn(value, text)

    def environment(self, initialized, rows):
        temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        path = Path(temp)
        (path / "cert9.db").touch()
        self.stack.enter_context(patch.object(db, "office_state", return_value=("", str(path), initialized, Mock())))
        self.stack.enter_context(patch.object(db, "select_db", return_value=(path, False)))
        self.stack.enter_context(patch.object(db, "user_database"))
        self.stack.enter_context(patch.object(action, "detect", return_value=[dict(label="A", path="/a.so")]))
        register = self.stack.enter_context(patch.object(nss, "register", return_value=rows))
        return path, register

    def test_already_initialized_needs_restart_and_remembers_on_repeat(self):
        _, register = self.environment(True, [dict(status="added")])
        self.assertTrue(action.setup(self.ctx)[2])
        register.return_value = [dict(status="existing")]
        self.assertTrue(action.setup(self.ctx)[2])

    def test_not_initialized_can_load_modules_without_restart(self):
        self.environment(False, [dict(status="added")])
        self.assertFalse(action.setup(self.ctx)[2])

    def test_existing_modules_after_restart_do_not_need_another_restart(self):
        self.environment(True, [dict(status="existing")])
        self.assertFalse(action.setup(self.ctx)[2])

    def test_failures_without_additions_do_not_request_restart(self):
        self.environment(True, [dict(status="error")])
        self.assertFalse(action.setup(self.ctx)[2])

    def test_start_center_with_no_frame_uses_same_result_helper(self):
        with patch.object(action, "platform_name", return_value="linux"), \
                patch.object(action, "setup", return_value=(Path("/db"), [], False)):
            action.run(self.ctx, None)
        self.assertIsNone(self.box.call_args.args[1])
        self.assertEqual(self.box.call_count, 1)

    def test_unexpected_exception_is_not_displayed_verbatim(self):
        with patch.object(action, "platform_name", return_value="linux"), \
                patch.object(action, "setup", side_effect=RuntimeError("English vendor details")):
            action.run(self.ctx, self.frame)
        self.assertNotIn("English", self.box.call_args.args[3])
        self.assertIn("Không thể hoàn tất", self.box.call_args.args[3])

    def test_only_errors_do_not_offer_signing_instruction(self):
        text = action.result_text(self.strings, "/db", [dict(label="A", path="/a", status="error", error="Lỗi")], False)
        self.assertNotIn(self.strings["next"], text)

    def test_private_store_selected_and_restart_required_with_cached_old_path(self):
        path, _ = self.environment(False, [])
        target = path / 'new-store'
        rows = [dict(label='VNPT-CA', path='/vnpt.so', status='added', private_store=True)]
        with patch.object(store, 'register', return_value=(target, rows, True)), patch.object(db, 'set_fallback') as select:
            result = action.setup(self.ctx)
        select.assert_called_once_with(self.ctx, target)
        self.assertEqual(result, (target, rows, True))
        text = action.result_text(self.strings, *result)
        self.assertIn('HST Office hiện dùng kho chứng thư riêng', text)
        self.assertIn('Kho cũ được giữ nguyên, không thay đổi', text)

    def test_repeat_before_restart_uses_owned_certdir_despite_cached_core_path(self):
        path, register = self.environment(True, [dict(status='existing')])
        target = store.directory(path, 'macos')
        with patch.object(db, 'office_state', return_value=(str(target), str(path), True, Mock())):
            selected, rows, restart = action.setup(self.ctx)
        self.assertEqual(selected, target)
        self.assertTrue(restart)
        self.assertEqual(register.call_args.args[0], target)
