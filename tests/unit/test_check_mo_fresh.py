# SPDX-License-Identifier: AGPL-3.0-only
"""Stale translation catalogues: scripts/l10n/check-mo-fresh.py and the invalidation rule of the local build scripts
(a language's .mo/registry files are dropped when one of its .po files is newer than its oldest catalogue)."""
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_mo_fresh", ROOT / "scripts/l10n/check-mo-fresh.py")
cmf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmf)

PO_HEAD = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'


def po_text(entries):
    return PO_HEAD + "".join(f'msgctxt "{c}"\nmsgid "{i}"\nmsgstr "{s}"\n\n' for c, i, s in entries)


@unittest.skipUnless(shutil.which("msgfmt") and shutil.which("msguniq"), "gettext tools not installed")
class CheckMoFreshTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name)
        (self.tree / "instdir/program/resource/vi/LC_MESSAGES").mkdir(parents=True)
        (self.tree / "xmlsecurity").mkdir()
        (self.tree / "xmlsecurity/AllLangMoTarget_xsc.mk").write_text(
            "$(eval $(call gb_AllLangMoTarget_set_polocation,xsc,xmlsecurity))\n")

    def put(self, location, name, po_entries, mo_entries):
        po = self.tree / "translations/source/vi" / location / "messages.po"
        po.parent.mkdir(parents=True, exist_ok=True)
        po.write_text(po_text(po_entries), encoding="utf-8")
        src = self.tree / "mo-source.po"
        src.write_text(po_text(mo_entries), encoding="utf-8")
        subprocess.run(["msgfmt", str(src), "-o", str(self.tree / f"instdir/program/resource/vi/LC_MESSAGES/{name}.mo")],
                       check=True)

    def test_fresh_catalogues_pass(self):
        entries = [("STR_A", "Vietnamese Tools", "Tiện ích Việt"), ("STR_B", "Open", "Mở")]
        self.put("sw", "sw", entries, entries)
        self.put("xmlsecurity", "xsc", entries[:1], entries[:1])   # name differs from its .po directory
        out = io.StringIO()
        self.assertEqual(cmf.check(str(self.tree), "vi", out=out), 0)
        self.assertIn("2 vi catalogues checked, 0 stale", out.getvalue())

    def test_missing_and_changed_strings_are_stale(self):
        new = [("STR_A", "Vietnamese Tools", "Tiện ích Việt"), ("STR_B", "Open", "Mở tệp")]
        old = [("STR_B", "Open", "Mở")]
        self.put("sw", "sw", new, old)
        out = io.StringIO()
        self.assertEqual(cmf.check(str(self.tree), "vi", out=out), 1)
        text = out.getvalue()
        self.assertIn("STALE vi/sw.mo", text)
        self.assertIn("1 missing, 1 changed", text)
        self.assertIn("Vietnamese Tools", text)

    def test_no_catalogues_is_an_error(self):
        self.assertEqual(cmf.check(str(self.tree), "vi", out=io.StringIO()), 1)


def shell_function(path, name):
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(rf"^{name}\(\) {{.*?^}}$", text, re.S | re.M)
    if not match:
        raise AssertionError(f"{name} not found in {path}")
    return match.group(0)


class InvalidateStaleTranslationsTest(unittest.TestCase):
    def make_tree(self, root, po_newer):
        lo = Path(root) / "lo"
        (lo / "translations/source/vi/sw").mkdir(parents=True)
        (lo / "translations/source/de/sw").mkdir(parents=True)
        (lo / "workdir/MoTarget").mkdir(parents=True)
        (lo / "workdir/XcdTarget").mkdir(parents=True)
        (lo / "workdir/XcuResTarget/officecfg/vi").mkdir(parents=True)
        old, new = time.time() - 3600, time.time()
        for f in ("workdir/MoTarget/swvi.mo", "workdir/MoTarget/scvi.mo", "workdir/XcdTarget/registry_vi.xcd"):
            (lo / f).write_text("x")
            os.utime(lo / f, (old, old) if po_newer else (new, new))
        po = lo / "translations/source/vi/sw/messages.po"
        po.write_text("x")
        os.utime(po, (new, new) if po_newer else (old, old))
        de_po = lo / "translations/source/de/sw/messages.po"   # no de catalogues built: nothing to drop
        de_po.write_text("x")
        return lo

    def run_rule(self, script, var, lo):
        fn = shell_function(script, "invalidate_stale_translations")
        snippet = f'log() {{ echo "$*"; }}\n{var}="{lo}"\n{fn}\ninvalidate_stale_translations\n'
        return subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, check=True)

    def check_script(self, script, var):
        with tempfile.TemporaryDirectory() as root:
            lo = self.make_tree(root, po_newer=True)
            done = self.run_rule(script, var, lo)
            self.assertIn("translations of vi", done.stdout)
            self.assertEqual(list((lo / "workdir/MoTarget").iterdir()), [])
            self.assertFalse((lo / "workdir/XcdTarget/registry_vi.xcd").exists())
            self.assertFalse((lo / "workdir/XcuResTarget/officecfg/vi").exists())
        with tempfile.TemporaryDirectory() as root:
            lo = self.make_tree(root, po_newer=False)
            self.run_rule(script, var, lo)
            self.assertEqual(len(list((lo / "workdir/MoTarget").iterdir())), 2)

    def test_windows_tree_sync(self):
        self.check_script("scripts/windows/hst4-tree.sh", "LO")

    def test_linux_local_build(self):
        self.check_script("scripts/linux/local-build.sh", "SRC")


if __name__ == "__main__":
    unittest.main()
