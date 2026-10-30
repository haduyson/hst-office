# SPDX-License-Identifier: AGPL-3.0-only
"""Pure-Python Ed25519 used by the update check: RFC 8032 section 7.1 vectors and rejection cases."""
import json
import os
import unittest

import _paths  # noqa: F401
from hst_office import ed25519

with open(os.path.join(_paths.ROOT, "tests", "fixtures", "update", "rfc8032-ed25519.json"), encoding="utf-8") as _f:
    VECTORS = json.load(_f)["vectors"]


class Rfc8032Vectors(unittest.TestCase):
    def test_all_five_vectors_are_present(self):
        self.assertEqual([v["name"] for v in VECTORS], ["TEST 1", "TEST 2", "TEST 3", "TEST 1024", "TEST SHA(abc)"])

    def test_public_key_sign_and_verify(self):
        for v in VECTORS:
            with self.subTest(v["name"]):
                secret, public = bytes.fromhex(v["secret"]), bytes.fromhex(v["public"])
                msg, sig = bytes.fromhex(v["message"]), bytes.fromhex(v["signature"])
                self.assertEqual(ed25519.secret_to_public(secret), public)
                self.assertEqual(ed25519.sign(secret, msg), sig)
                self.assertTrue(ed25519.verify(public, msg, sig))


class Rejections(unittest.TestCase):
    def setUp(self):
        v = VECTORS[2]  # TEST 3
        self.public, self.msg, self.sig = bytes.fromhex(v["public"]), bytes.fromhex(v["message"]), bytes.fromhex(v["signature"])

    def test_flipped_bits_anywhere_fail(self):
        for i in (0, 31, 32, 63):
            bad = bytearray(self.sig)
            bad[i] ^= 0x01
            self.assertFalse(ed25519.verify(self.public, self.msg, bytes(bad)), i)
        self.assertFalse(ed25519.verify(self.public, self.msg + b"x", self.sig))
        self.assertFalse(ed25519.verify(bytes.fromhex(VECTORS[0]["public"]), self.msg, self.sig))

    def test_malformed_inputs_return_false(self):
        self.assertFalse(ed25519.verify(self.public, self.msg, self.sig[:63]))
        self.assertFalse(ed25519.verify(self.public, self.msg, self.sig + b"\0"))
        self.assertFalse(ed25519.verify(self.public[:31], self.msg, self.sig))
        self.assertFalse(ed25519.verify(self.public, self.msg, None))
        self.assertFalse(ed25519.verify(self.public, "text", self.sig))
        self.assertFalse(ed25519.verify(b"\xff" * 32, self.msg, self.sig))  # not a curve point

    def test_non_canonical_s_is_rejected(self):
        s = int.from_bytes(self.sig[32:], "little") + ed25519.q
        self.assertFalse(ed25519.verify(self.public, self.msg, self.sig[:32] + s.to_bytes(32, "little")))


if __name__ == "__main__":
    unittest.main()
