# SPDX-License-Identifier: AGPL-3.0-only
"""Manifest generator and signer with the .rpm and AppImage assets: latest-3.json lists them, latest-2.json and
latest.json (read by installed 1.0.x clients) never do, and the signer refuses a schema that does not match the name."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import _paths
from hst_office import update_logic as logic


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_paths.ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load("generate_update_manifest", "scripts/release/generate-update-manifest.py")
signer = load("sign_update_manifest", "scripts/release/sign-update-manifest.py")
RELEASE = "1.0.2"
NAMES = {"windows": "HSTOffice_%s_Win_x86-64_en-US_vi.msi", "linux": "HSTOffice_%s_Linux_x86-64.deb",
         "linux-rpm": "HSTOffice_%s_Linux_x86-64.rpm", "linux-appimage": "HSTOffice_%s_Linux_x86-64.AppImage"}


class Generator(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.assets, self.site = self.root / "assets", self.root / "site"
        self.assets.mkdir()
        self.site.mkdir()
        lines = []
        for name in NAMES.values():
            data = ("content of " + name % RELEASE).encode()
            (self.assets / (name % RELEASE)).write_bytes(data)
            lines.append("%s  %s\n" % (hashlib.sha256(data).hexdigest(), name % RELEASE))
        (self.root / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")

    def generate(self):
        args = ["--tag", "v" + RELEASE, "--sums", str(self.root / "SHA256SUMS"), "--assets-dir", str(self.assets),
                "--site-dir", str(self.site), "--date", "2026-11-13"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(generator.main(args), 0)
        return {p.name: json.loads(p.read_bytes()) for p in self.site.iterdir()}

    def test_asset_names(self):
        for platform, name in NAMES.items():
            self.assertEqual(generator.parse_asset_name(name % RELEASE), (platform, RELEASE))
        self.assertIsNone(generator.parse_asset_name("HSTOffice_1.0.2_Linux_x86-64.appimage"))

    def test_three_files_and_legacy_files_without_new_platforms(self):
        out = self.generate()
        self.assertEqual(set(out), {"latest.json", "latest-2.json", "latest-3.json"})
        new, old = out["latest-3.json"]["channels"]["stable"], out["latest-2.json"]["channels"]["stable"]
        self.assertEqual(out["latest-3.json"]["schema"], 3)
        self.assertEqual(set(new["installers"]), set(NAMES))
        self.assertEqual(new["installers"]["linux-appimage"]["url"],
                         "https://office.hasontech.vn/tai/1.0.2/HSTOffice_1.0.2_Linux_x86-64.AppImage")
        self.assertEqual(set(new["downloads"]), set(logic.ALL_PLATFORMS))
        self.assertEqual(set(old["installers"]), {"windows", "linux"})
        self.assertEqual(set(old["downloads"]), set(logic.PLATFORMS))
        self.assertNotIn("linux-rpm", json.dumps(out["latest.json"]))
        for name in out:
            logic.parse_manifest((self.site / name).read_bytes())
        # A later release without new assets still updates latest-3.json (it exists now) and carries the others over.
        for name in ("linux-rpm", "linux-appimage"):
            (self.assets / (NAMES[name] % RELEASE)).unlink()
        sums = self.root / "SHA256SUMS"
        sums.write_text("".join(ln + "\n" for ln in sums.read_text().splitlines() if ".deb" in ln or ".msi" in ln))
        out = self.generate()
        self.assertEqual(set(out["latest-3.json"]["channels"]["stable"]["installers"]), {"windows", "linux"})


class Signer(unittest.TestCase):
    def test_schema_must_match_file_name(self):
        rel = {"version": "1.0.2", "date": "2026-11-13", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
               "downloads": {"linux": "https://office.hasontech.vn/tai/linux"}}
        with tempfile.TemporaryDirectory() as tmp:
            for name, schema, ok in (("latest-2.json", 3, False), ("latest-3.json", 2, False), ("latest-3.json", 3, True)):
                path = os.path.join(tmp, name)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump({"schema": schema, "channels": {"stable": rel, "beta": None}}, handle)
                with self.subTest(name=name, schema=schema), mock.patch.object(signer, "load_seed", side_effect=RuntimeError("seed")):
                    if ok:
                        with self.assertRaisesRegex(RuntimeError, "seed"):  # passed the schema check, stopped at the key
                            signer.sign(path, "unused")
                    else:
                        with self.assertRaises(SystemExit):
                            signer.sign(path, "unused")


if __name__ == "__main__":
    unittest.main()
