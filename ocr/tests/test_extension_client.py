# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Unit tests of the extension's UNO-free parts: engine process client and blocks → Writer items."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "extension", "python"))

from hst_ocr_uno import blocks, engine_client  # noqa: E402
from hst_ocr_uno.engine_client import EngineError  # noqa: E402


def fake_engine(body):
    """HST_OCR_ENGINE value running a tiny Python program that reads the request and executes body."""
    return {"HST_OCR_ENGINE": json.dumps([sys.executable, "-c", "import json,sys,time\nreq=json.load(sys.stdin)\n"
                                                                + body]), "PATH": os.environ.get("PATH", "")}


class EngineClientTest(unittest.TestCase):
    def setUp(self):
        fd, self.image = tempfile.mkstemp(suffix=".png")
        os.close(fd)

    def tearDown(self):
        os.unlink(self.image)

    def test_ok_response_and_request_shape(self):
        env = fake_engine("print(json.dumps({'version': 1, 'ok': True, 'blocks': [], 'echo': req}))")
        resp = engine_client.recognize(self.image, mode="page", threads=3, env=env)
        self.assertEqual(resp["echo"], {"version": 1, "image": os.path.abspath(self.image), "mode": "page",
                                        "lang": "vie", "threads": 3})

    def test_core_error_code_is_kept(self):
        env = fake_engine("print(json.dumps({'version': 1, 'ok': False, 'error': {'code': 'image-unreadable',"
                          " 'message': 'x'}}))")
        with self.assertRaises(EngineError) as caught:
            engine_client.recognize(self.image, env=env)
        self.assertEqual(caught.exception.code, "image-unreadable")

    def test_garbage_crash_and_timeout(self):
        cases = [("print('hello')", "engine-failed"), ("sys.exit(3)", "engine-failed"),
                 ("print(json.dumps({'version': 2, 'ok': True}))", "engine-failed"),
                 ("print(json.dumps({'version': 1, 'ok': True}))", "engine-failed"),
                 ("time.sleep(5)", "timeout")]
        for body, code in cases:
            with self.subTest(body=body), self.assertRaises(EngineError) as caught:
                engine_client.recognize(self.image, env=fake_engine(body), timeout=1)
            self.assertEqual(caught.exception.code, code)

    def test_engine_lookup(self):
        for raw in ("not json", "[]", '["ok", 3]', '"python3"'):
            with self.subTest(raw=raw), self.assertRaises(EngineError) as caught:
                engine_client.engine_command({"HST_OCR_ENGINE": raw})
            self.assertEqual(caught.exception.code, "engine-config")
        with tempfile.TemporaryDirectory() as root, self.assertRaises(EngineError) as caught:
            engine_client.engine_command({}, ext_root=root)
        self.assertEqual(caught.exception.code, "engine-missing")
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, "engine"))
            exe = os.path.join(root, "engine", "hst-ocr.exe" if sys.platform == "win32" else "hst-ocr")
            open(exe, "w").close()
            self.assertEqual(engine_client.engine_command({}, ext_root=root), [exe])


class BlocksTest(unittest.TestCase):
    def test_items(self):
        items = blocks.to_items([
            {"type": "paragraph", "text": "  Câu 1.\x0b tiếp  "},
            {"type": "formula", "latex": "a=5\\$+b$"},
            {"type": "table", "rows": [["A", "B"], ["1"]]},
            {"type": "table", "rows": [["A", 3]]},
            {"type": "paragraph", "text": "   "},
            {"type": "figure"}, "junk", {"type": "paragraph", "text": None},
        ])
        self.assertEqual(items, [blocks.Item("text", "Câu 1. tiếp"), blocks.Item("text", "$$a=5\\\\$+b\\$$$"),
                                 blocks.Item("table", [["A", "B"], ["1", ""]])])
        self.assertTrue(blocks.has_formula(items))
        self.assertFalse(blocks.has_formula(items[:1]))


if __name__ == "__main__":
    unittest.main()
