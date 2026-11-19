# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise packaged gettext lookup and strict equivalence failure modes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/l10n/check-ui-equivalence.py"
SPEC = importlib.util.spec_from_file_location("ui_equivalence", SCRIPT)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

HEADER = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
          '"Plural-Forms: nplurals=1; plural=0;\\n"\n')
VI = '''
msgctxt "dialog|open"
msgid "_Open"
msgstr "_Mở"

msgctxt "dialog|ok"
msgid "OK"
msgstr "OK"

msgctxt "COUNT"
msgid "%1 row"
msgid_plural "%1 rows"
msgstr[0] "%1 dòng"
'''
UI = '''<interface domain="DOMAIN"><object id="dialog">
<property name="label" translatable="yes" context="dialog|open">_Open</property>
<items><item translatable="yes" context="dialog|ok">OK</item><item>HST</item></items>
</object></interface>'''


@unittest.skipUnless(shutil.which("msgfmt"), "gettext tools required")
class Equivalence(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.work = Path(work.name)
        self.source = self.work / "src"
        module = self.source / "sfx2"
        module.mkdir(parents=True)
        (module / "AllLangMoTarget_sfx2.mk").write_text("$(eval $(call gb_AllLangMoTarget_AllLangMoTarget,sfx))")
        package_file = self.source / "scp2/source/ooo/file_ooo.scp"
        package_file.parent.mkdir(parents=True)
        package_file.write_text("MO_FILELIST_ALL_LANG(sfx)\n/* MO_FILELIST_ALL_LANG(sdext) */\n")
        optional = self.source / "sdext/AllLangMoTarget_sdext.mk"
        optional.parent.mkdir()
        optional.write_text("$(eval $(call gb_AllLangMoTarget_AllLangMoTarget,sdext))")
        (module / "strings.hrc").write_text(
            '#define NNC_(Context, A, B) TranslateNId(Context, A, B)\n'
            '/* NNC_("skip", "x", "z") */\n'
            '#define STR_COUNT NNC_("COUNT", "%1 " "row", "%1 rows")\n')
        route = self.source / "hst/l10n/domains.hxx"
        route.parent.mkdir(parents=True)
        route.write_text("HST_CATALOG(sfx,sfx2)\n")
        self.base = self.work / "before"
        self.candidate = self.work / "after"
        self.ui = Path("share/config/soffice.cfg/sfx/ui/dialog.ui")
        for install, domain in ((self.base, "sfx"), (self.candidate, "hst-sfx")):
            path = install / self.ui
            path.parent.mkdir(parents=True)
            path.write_text(UI.replace("DOMAIN", domain))
            self.catalog(install, domain, "vi", VI)
        self.catalog(self.candidate, "hst-sfx", "en_US", "")
        self.catalog(self.candidate, "sfx", "vi", "")

    def catalog(self, install, domain, lang, body):
        path = install / f"program/resource/{lang}/LC_MESSAGES/{domain}.mo"
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["msgfmt", "-o", path, "-"], input=(HEADER + body).encode(), check=True)

    def comparison(self):
        old = check.dump(self.source, self.base, False)
        new = check.dump(self.source, self.candidate, True)
        with contextlib.redirect_stdout(io.StringIO()):
            status = check.compare(old, new, self.work)
        return status, json.loads((self.work / "summary.json").read_text()), new

    def test_identity_translation_literal_and_plural_forms(self):
        status, summary, new = self.comparison()
        self.assertEqual((status, summary["base_rows"], summary["candidate_vi_fallbacks"]), (0, 5, 0))
        entries = list(new["rows"].values())
        self.assertEqual([r["vi"][1] for r in entries if r["msgid"] == "OK"], ["vi/LC_MESSAGES/hst-sfx.mo"])
        self.assertEqual([r["vi"] for r in entries if r["msgid"] == "HST"], [["HST", "literal"]])
        self.assertEqual({r["en"][0] for r in entries if r["context"] == "COUNT"}, {"%1 row", "%1 rows"})

    def test_dropped_identity_translation_is_fallback_even_when_text_matches(self):
        self.catalog(self.candidate, "hst-sfx", "vi", VI.replace('msgctxt "dialog|ok"', 'msgctxt "other"'))
        status, summary, _ = self.comparison()
        self.assertEqual((status, summary["text_differences"], summary["candidate_vi_fallbacks"]), (1, 0, 1))

    def test_removed_literal_and_changed_english_translation_are_reported(self):
        path = self.candidate / self.ui
        path.write_text(path.read_text().replace("<item>HST</item>", ""))
        self.catalog(self.candidate, "hst-sfx", "en_US", 'msgctxt "dialog|open"\nmsgid "_Open"\nmsgstr "Open!"\n')
        status, summary, _ = self.comparison()
        self.assertEqual((status, summary["text_differences"]), (1, 3))

    def test_missing_catalog_and_unrouted_dialog_fail_before_comparison(self):
        self.catalog(self.candidate, "sfx", "vi", VI)
        path = self.candidate / self.ui
        path.write_text(UI.replace("DOMAIN", "sfx"))
        with self.assertRaisesRegex(ValueError, "still requests sfx"):
            check.dump(self.source, self.candidate, True)
        (self.candidate / "program/resource/en_US/LC_MESSAGES/hst-sfx.mo").unlink()
        with self.assertRaisesRegex(ValueError, "en: missing HST domains .*sfx"):
            check.dump(self.source, self.candidate, True)

    def test_unparsed_header_message_fails_closed(self):
        (self.source / "sfx2/strings.hrc").write_text('#define SPECIAL NC_("C", MACRO)\n')
        with self.assertRaisesRegex(ValueError, "unsupported translation expression"):
            check.dump(self.source, self.base, False)

    def test_dropping_translation_flag_does_not_hide_an_identity_translation(self):
        path = self.candidate / self.ui
        path.write_text(path.read_text().replace('translatable="yes" context="dialog|ok"', 'context="dialog|ok"'))
        status, summary, _ = self.comparison()
        self.assertEqual((status, summary["text_differences"], summary["lost_translation_flags"]), (1, 0, 1))

    def test_unpacked_optional_module_cannot_gain_an_alias(self):
        self.catalog(self.candidate, "hst-sdext", "vi", "")
        with self.assertRaisesRegex(ValueError, "unexpected HST domains .*sdext"):
            check.dump(self.source, self.candidate, True)

    def test_upstream_catalog_list_must_match_even_for_unused_domains(self):
        self.catalog(self.base, "separate", "vi", "")
        status, summary, _ = self.comparison()
        self.assertEqual((status, summary["text_differences"]), (1, 0))
        self.assertEqual(summary["removed_upstream_mos"], ["vi/LC_MESSAGES/separate.mo"])


if __name__ == "__main__":
    unittest.main()
