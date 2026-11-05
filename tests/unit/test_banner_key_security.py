# SPDX-License-Identifier: AGPL-3.0-only
import base64
from unittest.mock import patch

from banner_fixtures import KEY, Remote, signed, manifest
from banner_review_fixtures import FeedCase
from hst_office import banner_verify as verify, ed25519


class KeySecurityTests(FeedCase):
    def test_noncanonical_identity_and_small_order_keys_disable_all_requests(self):
        invalid = [b"", b"x", bytes(32), b"\1" + bytes(31),
                   (ed25519.p - 1).to_bytes(32, "little"), ed25519.p.to_bytes(32, "little"),
                   (1 + 2**255).to_bytes(32, "little"), bytes([255]) * 32]
        # A valid point with a torsion component is not in the prime-order subgroup.
        mixed = ed25519.point_add(ed25519.point_decompress(KEY), ed25519.point_decompress(bytes(32)))
        invalid.append(ed25519.point_compress(mixed))
        data, _ = signed(manifest())
        forged = base64.b64encode(b"\1" + bytes(63))
        for key in invalid:
            with self.subTest(key=key.hex()):
                self.assertFalse(verify.valid_key(key))
                with self.assertRaises(ValueError):
                    verify.verify_manifest(data, forged, key)
                remote = Remote()
                with patch("hst_office.banner_store.load", side_effect=AssertionError("cache read")):
                    self.assertEqual(len(self.refresh(self.feed(remote, key))["items"]), 7)
                self.assertEqual(remote.calls, [])
                self.assertFalse(self.root.exists())

    def test_generated_prime_order_key_accepts_only_its_signatures(self):
        self.assertTrue(verify.valid_key(KEY))
        data, signature = signed(manifest())
        self.assertEqual(verify.verify_manifest(data, signature, KEY)["schemaVersion"], 1)
        with self.assertRaises(ValueError):
            verify.verify_manifest(data + b" ", signature, KEY)
