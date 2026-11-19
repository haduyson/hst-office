# SPDX-License-Identifier: AGPL-3.0-only
"""Trợ lý AI: provider requests and answers, the private HTTPS helper's rules, settings, texts, commands state.
No network: transports are recorded answers."""
import json
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


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.lang", "com.sun.star.frame",
              "com.sun.star.awt"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import ai_client, ai_config, ai_http, ai_keystore, ai_providers as providers  # noqa: E402
from hst_office.ai_document import excel_to_api  # noqa: E402
from hst_office.ai_handler import command_enabled  # noqa: E402
from hst_office.ai_options import changes_from_page, provider_at  # noqa: E402
from hst_office.ai_providers import AiError  # noqa: E402
from hst_office.ai_texts import ERRORS, TEXT, WRITING_MODES, error_text, extract_formula, writing_system  # noqa: E402


def answer(provider, text="Xin chào", **extra):
    if provider == "openai":
        doc = {"status": "completed", "output": [{"type": "reasoning", "summary": []},
                                                 {"type": "message", "content": [{"type": "output_text", "text": text}]}]}
    elif provider == "gemini":
        doc = {"candidates": [{"content": {"parts": [{"text": "nghĩ...", "thought": True}, {"text": text}]},
                               "finishReason": "STOP"}]}
    else:
        doc = {"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": text}],
               "stop_reason": "end_turn"}
    doc.update(extra)
    return json.dumps(doc).encode()


class ProviderTests(unittest.TestCase):
    def test_no_default_provider_and_three_choices(self):
        self.assertEqual(providers.ORDER, ("openai", "gemini", "claude"))
        self.assertEqual(ai_config.DEFAULTS["Provider"], "")
        self.assertFalse(ai_config.DEFAULTS["Enabled"])
        for provider in providers.ORDER:
            for model in providers.PROVIDERS[provider]["models"]:
                self.assertTrue(providers.MODEL_ID.fullmatch(model), model)

    def test_requests_never_carry_the_key(self):
        for provider in providers.ORDER:
            request = providers.chat_request(provider, providers.PROVIDERS[provider]["models"][0], "hệ thống", "câu hỏi")
            self.assertTrue(request["url"].startswith("https://" + providers.PROVIDERS[provider]["host"] + "/"))
            self.assertNotIn("key", json.dumps(request).lower().replace("api-key", ""))
            body = json.loads(request["body"])
            self.assertIn("câu hỏi", request["body"])
            self.assertTrue(body)
        openai = json.loads(providers.chat_request("openai", "gpt-6.2-sol", "s", "p")["body"])
        self.assertEqual((openai["instructions"], openai["input"], openai["store"]), ("s", "p", False))
        gemini = providers.chat_request("gemini", "gemini-3.8-flash", "s", "p")
        self.assertTrue(gemini["url"].endswith("/v1beta/models/gemini-3.8-flash:generateContent"))
        claude = providers.chat_request("claude", "claude-sonnet-5-5", "s", "p")
        self.assertEqual(claude["headers"]["anthropic-version"], providers.CLAUDE_VERSION)
        self.assertEqual(json.loads(claude["body"])["messages"], [{"role": "user", "content": "p"}])

    def test_refused_requests(self):
        with self.assertRaises(AiError):
            providers.chat_request("other", "m", "s", "p")
        for model in ("", "a/b", "../x", "x" * 101, "a b"):
            with self.assertRaises(AiError) as caught:
                providers.chat_request("gemini", model, "s", "p")
            self.assertEqual(caught.exception.kind, "model")
        for prompt in ("", "   ", "x" * (providers.MAX_PROMPT + 1)):
            with self.assertRaises(AiError):
                providers.chat_request("openai", "gpt-6.2-sol", "s", prompt)

    def test_answers_skip_reasoning(self):
        for provider in providers.ORDER:
            self.assertEqual(providers.parse_chat(provider, 200, answer(provider)), ("Xin chào", False))
        self.assertTrue(providers.parse_chat("openai", 200, answer("openai", status="incomplete"))[1])
        self.assertTrue(providers.parse_chat("claude", 200, answer("claude", stop_reason="max_tokens"))[1])

    def test_errors(self):
        body = json.dumps({"error": {"message": "Incorrect API key provided"}}).encode()
        cases = {401: "key", 403: "key", 429: "quota", 404: "model", 400: "request", 500: "server", 529: "server"}
        for status, kind in cases.items():
            with self.assertRaises(AiError) as caught:
                providers.parse_chat("openai", status, body)
            self.assertEqual((caught.exception.kind, caught.exception.detail), (kind, "Incorrect API key provided"))
        gemini_key = json.dumps({"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}})
        with self.assertRaises(AiError) as caught:
            providers.parse_chat("gemini", 400, gemini_key)
        self.assertEqual(caught.exception.kind, "key")
        blocked = json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}).encode()
        for provider, data in (("gemini", blocked), ("claude", json.dumps({"content": [], "stop_reason": "refusal"}))):
            with self.assertRaises(AiError) as caught:
                providers.parse_chat(provider, 200, data)
            self.assertEqual(caught.exception.kind, "blocked")
        for data in (b"<html>", b"[]", json.dumps({"output": []}).encode()):
            with self.assertRaises(AiError) as caught:
                providers.parse_chat("openai", 200, data)
            self.assertEqual(caught.exception.kind, "reply")

    def test_models(self):
        openai = json.dumps({"data": [{"id": "gpt-6.2-sol"}, {"id": "bad id"}, {"id": "gpt-6-luna"}]})
        self.assertEqual(providers.parse_models("openai", 200, openai), ["gpt-6-luna", "gpt-6.2-sol"])
        gemini = json.dumps({"models": [{"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                                        {"name": "models/embedding-1", "supportedGenerationMethods": ["embedContent"]}]})
        self.assertEqual(providers.parse_models("gemini", 200, gemini), ["gemini-3.8-flash"])
        self.assertEqual(providers.models_request("claude")["headers"]["anthropic-version"], providers.CLAUDE_VERSION)


class ClientTests(unittest.TestCase):
    def test_complete_through_transport(self):
        seen = []

        def transport(request, settings):
            seen.append((request, settings.key))
            return 200, answer("claude", "=SUM(A1:A3)")
        settings = ai_client.Settings("claude", "claude-sonnet-5-5", "sk-ant-test-key", "1.0.3")
        self.assertEqual(ai_client.complete(settings, "s", "tổng", transport), ("=SUM(A1:A3)", False))
        self.assertEqual(seen[0][1], "sk-ant-test-key")
        self.assertNotIn("sk-ant-test-key", json.dumps(seen[0][0]))

    def test_settings_checked_before_any_request(self):
        never = mock.Mock(side_effect=AssertionError("no request"))
        for settings, kind in ((ai_client.Settings("", "m", "k"), "provider"),
                               (ai_client.Settings("openai", "gpt-6.2-sol", ""), "nokey")):
            with self.assertRaises(AiError) as caught:
                ai_client.complete(settings, "s", "p", never)
            self.assertEqual(caught.exception.kind, kind)
            self.assertIn(kind, ERRORS)

    def test_transport_maps_helper_failures(self):
        settings = ai_client.Settings("openai", "gpt-6.2-sol", "sk-test-12345678", "1.0.3")
        request = providers.chat_request("openai", "gpt-6.2-sol", "s", "p")
        from hst_office import banner_fetch
        for raised, kind in ((TimeoutError("x"), "timeout"), (ValueError("x"), "network"), (OSError("x"), "network")):
            with mock.patch.object(banner_fetch, "_run", side_effect=raised):
                with self.assertRaises(AiError) as caught:
                    ai_client.http_transport()(request, settings)
                self.assertEqual(caught.exception.kind, kind)
        with mock.patch.object(banner_fetch, "_run", return_value=b'{"status": 200, "body": "{}"}') as run:
            self.assertEqual(ai_client.http_transport()(request, settings), (200, b"{}"))
            payload = json.loads(run.call_args[0][0])
            self.assertEqual((payload["key"], payload["provider"], run.call_args[0][2]),
                             ("sk-test-12345678", "openai", "ai_http.py"))

    def test_helper_that_never_answers_ends_in_the_timeout_message(self):
        """A real helper process that hangs (stuck DNS, proxy or TLS) is killed at the deadline and the dialog gets
        the "timeout" message; it must never wait for the process by itself."""
        import time
        from hst_office import banner_fetch
        settings = ai_client.Settings("openai", "gpt-6.2-sol", "sk-test-12345678", "1.0.3")
        request = providers.chat_request("openai", "gpt-6.2-sol", "s", "p")
        hang = ([sys.executable, "-c", "import sys, time; sys.stdin.read(); time.sleep(60)"], None)
        with mock.patch.object(banner_fetch, "helper_command", return_value=hang):
            started = time.monotonic()
            with self.assertRaises(AiError) as caught:
                ai_client.http_transport(timeout=1.5)(request, settings)
            elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.kind, "timeout")
        self.assertLess(elapsed, 10)
        self.assertIn("2 phút", error_text(caught.exception))

    def test_request_stuck_before_its_helper_starts_still_times_out(self):
        """Queued behind banner helpers, or a slow interpreter probe: the dialog still gets the timeout message at
        DEADLINE + GRACE, never an endless "sending"."""
        import threading
        import time
        from hst_office import banner_fetch
        settings = ai_client.Settings("claude", "claude-sonnet-5-5", "sk-ant-test-12345678", "1.0.3")
        request = providers.chat_request("claude", "claude-sonnet-5-5", "s", "p")
        never = threading.Event()
        with mock.patch.object(banner_fetch, "_run", side_effect=lambda *a: never.wait(30)), \
                mock.patch.object(ai_client, "GRACE", 0.5):
            started = time.monotonic()
            with self.assertRaises(AiError) as caught:
                ai_client.http_transport(timeout=0.5)(request, settings)
            elapsed = time.monotonic() - started
        never.set()
        self.assertEqual(caught.exception.kind, "timeout")
        self.assertLess(elapsed, 5)

    def test_helper_that_exits_without_answer_is_the_network_message(self):
        from hst_office import banner_fetch
        settings = ai_client.Settings("gemini", "gemini-3.8-flash", "test-key-12345678", "1.0.3")
        request = providers.chat_request("gemini", "gemini-3.8-flash", "s", "p")
        failing = ([sys.executable, "-c", "import sys; sys.stdin.read(); sys.exit(1)"], None)
        with mock.patch.object(banner_fetch, "helper_command", return_value=failing):
            with self.assertRaises(AiError) as caught:
                ai_client.http_transport(timeout=10)(request, settings)
        self.assertEqual(caught.exception.kind, "network")


class HelperTests(unittest.TestCase):
    def test_only_the_chosen_provider_host(self):
        self.assertTrue(ai_http.allowed("https://api.openai.com/v1/responses", "openai"))
        for url, provider in (("https://api.openai.com/v1/responses", "claude"), ("http://api.openai.com/v1", "openai"),
                              ("https://api.openai.com:8443/v1", "openai"), ("https://evil.example/v1", "openai"),
                              ("https://user:pw@api.anthropic.com/v1", "claude"),
                              ("https://api.openai.com.evil.example/v1", "openai")):
            self.assertFalse(ai_http.allowed(url, provider), url)

    def test_key_rules(self):
        self.assertTrue(ai_http.valid_key("sk-proj-AbC123_x"))
        for key in (None, "", "short", "sk-abc\r\nX-Evil: 1", "sk abc defgh", "sk-ăâ-12345678", "x" * 513):
            self.assertFalse(ai_http.valid_key(key), repr(key))

    def test_auth_header_only_inside_the_helper(self):
        captured = {}

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return b"{}"

        class Opener:
            def open(self, request, timeout):
                captured.update(request.header_items(), url=request.full_url, method=request.get_method())
                return Response()
        request = providers.chat_request("claude", "claude-sonnet-5-5", "s", "p")
        args = dict(request, provider="claude", key="sk-ant-12345678", version="1.0.3", proxy=None)
        args["headers"] = dict(request["headers"], Cookie="a=b")
        with mock.patch("urllib.request.build_opener", return_value=Opener()):
            self.assertEqual(ai_http.send(args), (200, b"{}"))
        self.assertEqual(captured["X-api-key"], "sk-ant-12345678")
        self.assertEqual(captured["User-agent"], "HSTOffice/1.0.3")
        self.assertNotIn("Cookie", captured)
        self.assertEqual(captured["method"], "POST")
        with self.assertRaises(ValueError):
            ai_http.send(dict(args, url="https://api.openai.com/v1/responses"))


class SettingsTextsTests(unittest.TestCase):
    def test_config_normalize(self):
        values = ai_config.normalize({"Enabled": 1, "Provider": "other", "ClaudeModel": " claude-opus-5-5 "})
        self.assertEqual((values["Enabled"], values["Provider"], values["ClaudeModel"]), (True, "", "claude-opus-5-5"))
        self.assertEqual(ai_config.model_for(values, "claude"), "claude-opus-5-5")
        self.assertEqual(ai_config.model_for(values, "openai"), providers.PROVIDERS["openai"]["models"][0])

    def test_options_page_changes(self):
        self.assertEqual(provider_at(0), "")
        self.assertEqual(changes_from_page(False, 0, ""), {"Enabled": False, "Provider": ""})
        self.assertEqual(changes_from_page(True, 3, "claude-sonnet-5-5"),
                         {"Enabled": True, "Provider": "claude", "ClaudeModel": ""})  # the suggested model stays implicit
        self.assertEqual(changes_from_page(True, 2, "gemini-x"), {"Enabled": True, "Provider": "gemini",
                                                                  "GeminiModel": "gemini-x"})

    def test_commands_state(self):
        active = ("openai", "gpt-6.2-sol")
        self.assertTrue(command_enabled("Options", None, None))
        self.assertFalse(command_enabled("Help", "writer", None))  # off by default
        self.assertTrue(command_enabled("Help", "writer", active))
        self.assertFalse(command_enabled("FormulaWrite", "writer", active))
        self.assertTrue(command_enabled("FormulaWrite", "calc", active))

    def test_texts(self):
        self.assertEqual(extract_formula("```\n=SUMIF(B:B,\"Đã thu\",C:C)\n```\n\nGiải thích"), '=SUMIF(B:B,"Đã thu",C:C)')
        self.assertIsNone(extract_formula("Không có công thức"))
        self.assertIn("chính tả", writing_system(0))
        self.assertIn("in hoa", writing_system(len(WRITING_MODES) - 1, "viết in hoa"))
        self.assertTrue(error_text(AiError("key", "bad key")).endswith("(bad key)"))

    def test_excel_separators_to_api(self):
        self.assertEqual(excel_to_api('=IF(A1>1,"a,b",SUM(B1,B2))'), '=IF(A1>1;"a,b";SUM(B1;B2))')
        self.assertEqual(excel_to_api("=SUM({1,2;3,4})"), "=SUM({1;2|3;4})")


class KeystoreTests(unittest.TestCase):
    def test_session_fallback_and_never_settings(self):
        store = ai_keystore.Keystore(None, ai_keystore.SessionStore())
        self.assertFalse(store.persistent)
        self.assertEqual(store.set("openai", "sk-test-12345678"), ai_keystore.SESSION_LABEL)
        self.assertEqual(store.get("openai"), "sk-test-12345678")
        self.assertTrue(store.delete("openai"))
        self.assertIsNone(store.get("openai"))
        self.assertNotIn("Key", "".join(ai_config.DEFAULTS))

    def test_failing_os_store_keeps_the_key_for_the_session_only(self):
        broken = mock.Mock(label="OS")
        broken.set.side_effect = OSError("locked")
        broken.get.side_effect = OSError("locked")
        store = ai_keystore.Keystore(None, broken)
        self.assertEqual(store.set("gemini", "AIza-test-123"), ai_keystore.SESSION_LABEL)
        self.assertEqual(store.get("gemini"), "AIza-test-123")
        store.delete("gemini")

    def test_platform_choice(self):
        with mock.patch("hst_office.ai_keystore_linux.Store", side_effect=OSError("no libsecret")):
            self.assertIsNone(ai_keystore.os_store("linux"))


class FormulaColumnsTests(unittest.TestCase):
    """"Viết công thức" sends the data region's address and column names, never a data value."""
    DATA = [("Khu vực", "Tháng", "Doanh thu"), ("Hà Nội", 1, 120), ("Đà Nẵng", 1, 80), ("Hà Nội", 2, 150),
            ("TP.HCM", 2, 200), ("Hà Nội", 3, 90)]

    def sheet(self, data):
        rows, cols = len(data), max(len(r) for r in data)

        class Address:
            def __init__(self, c1, r1, c2, r2):
                self.StartColumn, self.StartRow, self.EndColumn, self.EndRow = c1, r1, c2, r2

        def name(col, row):
            return "$%s$%d" % (chr(65 + col), row + 1)

        class Cell:
            def __init__(self, col, row):
                self.col, self.row = col, row
                value = data[row][col] if row < rows and col < len(data[row]) else None
                self.value = value
                self.AbsoluteName = "$Sheet1." + name(col, row)

            def getType(self):
                kind = "EMPTY" if self.value is None else "TEXT" if isinstance(self.value, str) else "VALUE"
                return types.SimpleNamespace(value=kind)

            def getString(self):
                return "" if self.value is None else str(self.value)

        class Cursor:
            def __init__(self, cell=None):
                self.cell = cell
                self.area = Address(cell.col, cell.row, cell.col, cell.row) if cell else None

            def collapseToCurrentRegion(self):
                if self.cell.col < cols and self.cell.row < rows:
                    self.area = Address(0, 0, cols - 1, rows - 1)

            def gotoStartOfUsedArea(self, expand):
                pass

            def gotoEndOfUsedArea(self, expand):
                self.area = Address(0, 0, cols - 1, rows - 1)

            def getRangeAddress(self):
                return self.area

        class Sheet:
            def createCursorByRange(self, cell):
                return Cursor(cell)

            def createCursor(self):
                return Cursor()

            def getCellByPosition(self, col, row):
                return Cell(col, row)

            def getCellRangeByPosition(self, c1, r1, c2, r2):
                return types.SimpleNamespace(AbsoluteName="$Sheet1.%s:%s" % (name(c1, r1), name(c2, r2)))
        return Sheet(), Cell

    def request(self, data, col, row):
        from hst_office.ai_document import cell_name, data_region
        from hst_office.ai_texts import formula_request
        sheet, cell_type = self.sheet(data)
        controller = mock.Mock(getActiveSheet=mock.Mock(return_value=sheet))
        cell = cell_type(col, row)
        region = data_region(controller, cell)
        return region, formula_request("Tổng doanh thu của khu vực Hà Nội", cell_name(cell), region)

    def test_headers_and_range_are_sent_but_no_data_value(self):
        region, text = self.request(self.DATA, 4, 1)  # E2, next to the data
        self.assertEqual(region, ("A1:C6", [("A", "Khu vực"), ("B", "Tháng"), ("C", "Doanh thu")]))
        for wanted in ("E2", "A1:C6", "A = Khu vực", "B = Tháng", "C = Doanh thu"):
            self.assertIn(wanted, text)
        for value in ("Đà Nẵng", "TP.HCM", "120", "80", "150", "200", "90"):
            self.assertNotIn(value, text)
        self.assertEqual(text.count("Hà Nội"), 1)  # only the user's own description

    def test_no_header_row_sends_the_description_alone(self):
        numbers = [(1, 2), (3, 4)]
        region, text = self.request(numbers, 3, 0)
        self.assertIsNone(region)
        self.assertEqual(text, "Tổng doanh thu của khu vực Hà Nội Công thức sẽ đặt tại ô D1.")

    def test_dialog_note_says_only_column_names(self):
        self.assertEqual(TEXT["columns_note"], "Sẽ gửi tên cột của bảng (không gửi số liệu).")


class LiveProviderFindingsTests(unittest.TestCase):
    """What a real free-tier Gemini key showed: the default model must answer, an overloaded model must point to
    another one, a stalled connection is a timeout (not "no connection"), and a rate limit is not "out of money"."""

    def test_default_gemini_model_is_the_one_that_answers_on_the_free_tier(self):
        self.assertEqual(ai_config.model_for({}, "gemini"), "gemini-3.6-flash")
        self.assertIn("gemini-3.8-flash", providers.PROVIDERS["gemini"]["models"])

    def test_overloaded_server_suggests_another_model(self):
        text = error_text(AiError("server", "This model is currently experiencing high demand."))
        self.assertIn("chọn mô hình khác", text)
        self.assertIn("Tùy chọn", text)
        self.assertTrue(text.endswith("(This model is currently experiencing high demand.)"))

    def test_quota_says_rate_or_plan_limit_and_keeps_the_provider_text(self):
        text = error_text(AiError("quota", "You exceeded your current quota."))
        self.assertIn("vượt hạn mức (giới hạn số lượt hoặc hết hạn mức của gói)", text)
        self.assertNotIn("hết tiền", text)
        self.assertTrue(text.endswith("(You exceeded your current quota.)"))

    def _helper_reply(self, raised):
        import io
        stdin = io.BytesIO(json.dumps({"provider": "gemini"}).encode())
        stdout = io.BytesIO()
        with mock.patch.object(ai_http, "send", side_effect=raised), \
                mock.patch.object(sys, "stdin", mock.Mock(buffer=stdin)), \
                mock.patch.object(sys, "stdout", mock.Mock(buffer=stdout)):
            code = ai_http.main()
        return code, stdout.getvalue()

    def test_helper_reports_a_read_or_connect_timeout_as_timeout(self):
        import socket
        import urllib.error
        for raised in (socket.timeout("timed out"), TimeoutError("timed out"),
                       urllib.error.URLError(socket.timeout("timed out"))):
            code, out = self._helper_reply(raised)
            self.assertEqual((code, json.loads(out)), (0, {"timeout": True}), raised)
        code, out = self._helper_reply(urllib.error.URLError(ConnectionRefusedError()))
        self.assertEqual((code, out), (1, b""))

    def test_client_maps_the_helper_timeout_to_the_timeout_message(self):
        from hst_office import banner_fetch
        settings = ai_client.Settings("gemini", "gemini-3.6-flash", "test-key-12345678", "1.0.3")
        request = providers.chat_request("gemini", "gemini-3.6-flash", "s", "p")
        with mock.patch.object(banner_fetch, "_run", return_value=b'{"timeout": true}'):
            with self.assertRaises(AiError) as caught:
                ai_client.http_transport()(request, settings)
        self.assertEqual(caught.exception.kind, "timeout")


if __name__ == "__main__":
    unittest.main()
