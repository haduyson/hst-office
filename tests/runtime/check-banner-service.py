#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the banner UNO boundary or full service registration in an isolated user profile.

Full: PYTHONPATH=<office>/program python3 tests/runtime/check-banner-service.py --soffice <office>/program/soffice
Boundary: URE_BOOTSTRAP=vnd.sun.star.pathname:<office>/program/fundamentalrc PYTHONPATH=<office>/program \
python3 tests/runtime/check-banner-service.py --boundary-only
The boundary check uses real UNO types but substitutes profile lookup; it does not prove native deployment.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extensions/hst-vietnamese-tools/python"))
sys.path.insert(0, str(ROOT / "tests/fixtures/vietnamese/runtime"))


def snapshot_check(service, ctx=None):
    import uno
    from com.sun.star.beans import NamedValue
    expected = json.loads((ROOT / "data/hst/banners.json").read_text())
    expected = {i["id"]: i for i in expected["items"]}
    for scale, level in ((1, 1), (1.5, 2), (3, 3)):
        for slot, identifier in enumerate(expected):
            raw = service.execute((NamedValue("Scale", scale), NamedValue("Slot", slot)))
            assert len(raw.encode("utf-8")) <= 432 * 1024
            result = json.loads(raw)
            assert result["rotateSeconds"] == 10 and len(result["items"]) == 1
            assert result["slotCount"] == len(expected) and result["slot"] == slot
            item = result["items"][0]
            assert item["id"] == identifier and item["name"] == expected[identifier]["name"]
            blob = base64.b64decode(item["image_base64"], validate=True)
            spec = expected[item["id"]]["image"][f"{level}x"]
            assert len(blob) == spec["size"] and hashlib.sha256(blob).hexdigest() == spec["sha256"]
            assert item["tagline"] == expected[item["id"]]["tagline"]
            assert "image_url" not in item and "image_path" not in item
            assert "utm_medium=banner" in item["click_url_with_utm"]
            if ctx is not None:
                provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", ctx)
                prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
                stream = ctx.ServiceManager.createInstanceWithContext("com.sun.star.io.SequenceInputStream", ctx)
                stream.initialize((uno.ByteSequence(blob),))
                prop.Name, prop.Value = "InputStream", stream
                graphic = provider.queryGraphic((prop,))
                assert graphic is not None and graphic.getType() > 0
                assert (graphic.SizePixel.Width, graphic.SizePixel.Height) == (360 * level, 104 * level)
        print(f"PASS UNO NamedValue / {len(expected)} bounded snapshots / verified buffers at scale", scale)


def boundary():
    import uno
    from hst_office import banner_uno
    from hst_office.banner_feed import BannerFeed
    with tempfile.TemporaryDirectory() as tmp:
        feed = BannerFeed(tmp, "1.0.0-beta.5", public_key=b"")  # offline, no key or network
        with patch.object(banner_uno, "feed_for_context", return_value=feed):
            service = banner_uno.BannerService(uno.getComponentContext())
            snapshot_check(service)
            with feed._lock:
                pass  # let the background worker finish before deleting the temporary profile
    return 0


def full(soffice, extension):
    from lo_session import Session
    session = Session(str(soffice.resolve()), str(extension.resolve()), "/tmp/hst-banner-runtime", port=2197)
    try:
        ok, detail, _ = session.install()
        if not ok:
            print("BLOCKED: extension installation:", detail)
            return 2
        session.start()
        service = session.ctx.ServiceManager.createInstanceWithContext("org.hst.office.BannerFeed", session.ctx)
        if service is None:
            # A fresh HST profile first synchronizes bundled/user registries; activate them on restart.
            session.stop()
            session.start()
            service = session.ctx.ServiceManager.createInstanceWithContext("org.hst.office.BannerFeed", session.ctx)
        assert service is not None
        for kind in ("swriter", "scalc", "simpress"):
            doc = session.new_doc(kind)
            snapshot_check(service, session.ctx)
            doc.close(True)
            print("PASS registered service in", kind)
    finally:
        session.stop()
        session.cleanup()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary-only", action="store_true")
    parser.add_argument("--soffice", type=Path, default=Path("/opt/hst/program/soffice"))
    parser.add_argument("--extension", type=Path, default=ROOT / "dist/extensions/hst-vietnamese-tools.oxt")
    args = parser.parse_args()
    return boundary() if args.boundary_only else full(args.soffice, args.extension)


if __name__ == "__main__":
    sys.exit(main())
