#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the banner UNO boundary or full service registration in an isolated user profile.

Full: PYTHONPATH=<office>/program python3 tests/runtime/check-banner-service.py --soffice <office>/program/soffice
Boundary: URE_BOOTSTRAP=vnd.sun.star.pathname:<office>/program/fundamentalrc PYTHONPATH=<office>/program \
python3 tests/runtime/check-banner-service.py --boundary-only
The boundary check uses real UNO types but substitutes profile lookup; it does not prove native deployment.
"""
import argparse
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
    for scale, suffix in ((1, "@1x.png"), (1.5, "@2x.png"), (3, "@3x.png")):
        result = json.loads(service.execute((NamedValue("Scale", scale),)))
        assert result["rotateSeconds"] == 10 and len(result["items"]) == 6
        assert result["items"][0]["name"] == "AIOS"
        for item in result["items"]:
            assert item["image_path"].endswith(suffix) and Path(item["image_path"]).is_file()
            assert uno.fileUrlToSystemPath(item["image_url"]) == item["image_path"]
            assert "utm_medium=banner" in item["click_url_with_utm"]
            if ctx is not None:
                provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", ctx)
                prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
                prop.Name, prop.Value = "URL", item["image_url"]
                graphic = provider.queryGraphic((prop,))
                assert graphic is not None and graphic.getType() > 0
                assert (graphic.SizePixel.Width, graphic.SizePixel.Height) == (360 * int(suffix[1]), 104 * int(suffix[1]))
        print("PASS UNO NamedValue / JSON / six images / file URLs at scale", scale)


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
