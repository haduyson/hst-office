# SPDX-License-Identifier: AGPL-3.0-only
"""Crash and power-cut durability of document recovery (offline checks of the patches and extension files).

Patches (appended to the series in this order): hst-durable-file-helpers, hst-profile-durability,
hst-emergency-save-crash-log, hst-recovery-durability, hst-unsaved-documents-entry, hst-save-atomic-replace,
hst-recovery-dialog-details. The runtime behaviour is checked by tests/runtime/check-recovery-kill.py,
check-emergency-save.py, check-profile-corruption.py, check-unsaved-documents.py and check-save-replace.py."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
EXT = ROOT / "extensions/hst-vietnamese-tools"
NEW = ["hst-durable-file-helpers", "hst-profile-durability", "hst-emergency-save-crash-log", "hst-recovery-durability",
       "hst-unsaved-documents-entry", "hst-save-atomic-replace", "hst-recovery-dialog-details"]


def after(name):
    """{path: text of the patched hunks (context and added lines)} of a patch."""
    out, current = {}, None
    for line in (PATCHES / (name + ".patch")).read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], [])
        elif current is not None and line[:1] in (" ", "+") and not line.startswith("+++"):
            current.append(line[1:])
    return {path: "\n".join(lines) for path, lines in out.items()}


def ordered(text, *parts):
    """True when the parts occur in this order in text."""
    pos = 0
    for part in parts:
        pos = text.find(part, pos)
        if pos < 0:
            return False
        pos += len(part)
    return True


class Series(unittest.TestCase):
    def test_new_patches_are_appended_in_order(self):
        names = [n for n in (PATCHES / "series").read_text().split() if not n.startswith("#")]
        self.assertEqual(names[-len(NEW):], [n + ".patch" for n in NEW])

    def test_new_cxx_modules_stay_small(self):
        for name in NEW:
            text = (PATCHES / (name + ".patch")).read_text(encoding="utf-8")
            for block in re.split(r"^--- /dev/null\n", text, flags=re.M)[1:]:
                path = block.splitlines()[0][6:]
                added = re.match(r"\+\+\+ b/\S+\n@@ -0,0 \+1,(\d+) @@", block)
                self.assertTrue(added and int(added.group(1)) <= 199, path)


class Durability(unittest.TestCase):
    def test_atomic_write_syncs_before_the_rename(self):
        cxx = after("hst-durable-file-helpers")["comphelper/source/misc/hstdurablefile.cxx"]
        self.assertTrue(ordered(cxx, "bool writeFileAtomically", "osl_syncFile(hFile)", "osl::File::replace",
                                "syncParentDirectory(rFileURL)"))

    def test_configuration_is_synced_and_repaired(self):
        p = after("hst-profile-durability")
        self.assertTrue(ordered(p["configmgr/source/writemodfile.cxx"], "osl_syncFile(handle)", "osl_closeFile(handle)",
                                "handle = nullptr;", "syncParentDirectory(_url)"))
        comp = p["configmgr/source/components.cxx"]
        for part in ('".hong-"', '".hst-repaired"', "tryPopRegistryModifications()", "hstIsEmptyFile(url)"):
            self.assertIn(part, comp)
        self.assertIn("tryPop_file(maUserConfigWorkURL, getPackURL(), maRegModName, maExt)",
                      p["comphelper/source/misc/backupfilehelper.cxx"])

    def test_recovery_list_is_on_disk_before_the_old_copy_goes(self):
        p = after("hst-recovery-durability")
        ar = p["framework/source/services/autorecovery.cxx"]
        self.assertTrue(ordered(ar, "implts_startModifyListeningOnDoc(rInfo);",
                                "flushConfiguration(m_xContext);", "st_impl_removeFile(sRemoveFile);"))
        self.assertTrue(ordered(ar, "flushConfiguration(m_xContext);", "st_impl_removeFile(sRemoveURL1);"))
        self.assertTrue(ordered(ar, "while(nRetry>0);", "writeIndexFromConfiguration();"))
        self.assertTrue(ordered(ar, "mergeIntoConfiguration(m_xContext);", "RecoveryList::get());"))
        app = p["desktop/source/app/app.cxx"]
        self.assertTrue(ordered(app, "theAutoRecovery::get(", "impl_checkRecoveryState(bCrashed"))
        store = p["framework/source/services/hstrecoverystore.cxx"]
        self.assertIn('"hst-recovery-index.txt"', store)
        self.assertIn("KEEP_SECONDS = 7 * 24 * 3600", store)
        self.assertIn('u"odt", u"ods", u"odp"', store)  # only recovery copies are orphans or swept

    def test_first_copy_after_thirty_seconds(self):
        ar = after("hst-recovery-durability")["framework/source/services/autorecovery.cxx"]
        self.assertIn("HST_FIRST_COPY_MS = 20000", ar)  # + 10 s user-idle wait = 30 s
        self.assertIn("rInfo.OldTempURL.isEmpty() ? std::min(nNormalMs, HST_FIRST_COPY_MS) : nNormalMs", ar)
        self.assertTrue(ordered(ar, "bFirstChange = pIt->OldTempURL.isEmpty();", "implts_updateTimer();"))

    def test_unsaved_documents_kept_seven_days_and_500_mb(self):
        p = after("hst-recovery-durability")
        ar = p["framework/source/services/autorecovery.cxx"]
        self.assertTrue(ordered(ar, "keepUnsaved(framework::hstrecovery::unsavedDir(), aKept)",
                                "aInfo.OldTempURL.clear();", "implts_flushConfigItem(aInfo, true);"))
        unsaved = p["framework/source/services/hstunsavedstore.cxx"]
        self.assertIn("KEEP_SECONDS = 7 * 24 * 3600", unsaved)
        self.assertIn("KEEP_BYTES = sal_uInt64(500) * 1024 * 1024", unsaved)
        self.assertIn('$(user)/hst-unsaved', unsaved)

    def test_tab_layout_survives_emergency_save(self):
        p = after("hst-recovery-durability")
        ar = p["framework/source/services/autorecovery.cxx"]
        self.assertTrue(ordered(ar, "freezeLayout();", "implts_changeAllDocVisibility(false);"))
        self.assertTrue(ordered(ar, "implts_doSessionSave()", "freezeLayout();"))
        tabs = p["framework/source/services/documenttabgroup.cxx"]
        self.assertIn("writeFileAtomically(aURL, aText.makeStringAndClear())", tabs)
        self.assertNotIn("StreamMode::TRUNC", tabs)
        self.assertTrue(ordered(tabs, "if (!m_bLayoutFrozen)", "osl::File::remove(lcl_layoutURL());"))
        self.assertTrue(ordered(tabs, "m_aSaveLayoutTimer.Stop();", "saveLayout();", "void DocumentTabGroup::shutdown()"))

    def test_saving_over_a_file(self):
        p = after("hst-save-atomic-replace")
        doc = p["sfx2/source/doc/docfile.cxx"]
        self.assertTrue(ordered(doc, "comphelper::hst::syncFile(aSourceMainURL);", "osl::File::replace(aSourceMainURL",
                                "syncParentDirectory(aDestMainURL);", "replaceThroughTarget(aSourceMainURL"))
        self.assertIn("sweepStaleSaveTemps(aLogicBase);", doc)
        helper = p["sfx2/source/doc/hstsavefile.cxx"]
        for part in ("realpath(", "fchmod(nOut", "fchown(nOut", "COPYFILE_XATTR | COPYFILE_ACL", "fsetxattr(",
                     "fsync(nOut)", "rename(aTemp.c_str(), aReal)"):
            self.assertIn(part, helper)
        self.assertIn('u".~hst-save-"', p["sfx2/source/doc/hstsavetemps.cxx"])


class EmergencySave(unittest.TestCase):
    def test_no_faulthandler_and_the_office_logs_the_fault(self):
        diag = (EXT / "python/hst_office/diag_crash.py").read_text(encoding="utf-8")
        self.assertNotIn("faulthandler.enable", diag)
        svmain = after("hst-emergency-save-crash-log")["vcl/source/app/svmain.cxx"]
        self.assertTrue(ordered(svmain, "bIn = true;", "Fatal exception: Signal %d", "vcl::SolarMutexTryAndBuyGuard"))


    def test_crash_signature_takes_the_fault_not_the_abort(self):
        import sys
        sys.path.insert(0, str(EXT / "python"))
        from hst_office import crash_signature as sig
        text = sig.from_linux_stderr("Fatal exception: Signal 11\nStack:\n#0 /opt/p/libswlo.so(+0x10) [0x7f00]\n"
                                     "Fatal exception: Signal 6\nStack:\n#0 /lib/libc.so.6(abort+0x1) [0x7f01]\n")
        self.assertEqual(text.splitlines()[0], "Office handler: Signal 11 (SIGSEGV)")
        self.assertIn("libswlo.so +0x10", text)


class DialogAndEntries(unittest.TestCase):
    def test_recovery_dialog_time_column_and_tooltip(self):
        p = after("hst-recovery-dialog-details")
        self.assertIn('context="docrecoveryrecoverdialog|savedft">Autosaved at', p["svx/uiconfig/ui/docrecoveryrecoverdialog.ui"])
        self.assertIn("connect_query_tooltip", p["svx/source/dialog/docrecovery.cxx"])
        po = p["translations/source/vi/svx/messages.po"]
        self.assertIn('msgstr "Tự lưu lúc"', po)
        self.assertIn('msgstr "Chưa lưu lần nào"', po)

    def test_wording_uses_khoi_phuc_only(self):
        rows = [json.loads(line) for line in (ROOT / "l10n/vi-overrides.jsonl").read_text(encoding="utf-8").splitlines()
                if '"docrecovery' in line or 'RECOV' in line]
        texts = {r["msgctxt"]: r["msgstr"] for r in rows}
        self.assertEqual(texts["RID_SVXSTR_RECOVFAILED"], "Không khôi phục được")
        self.assertEqual(texts["docrecoveryrecoverdialog|label2"], "Tài liệu có bản tự lưu:")
        self.assertIn("Có tài liệu không khôi phục được", texts["RID_SVXSTR_RECOVERYONLY_FINISH_DESCR"])
        for key, text in texts.items():
            self.assertNotIn("phục hồi", text.lower(), key)

    def test_entries_of_unsaved_documents(self):
        p = after("hst-unsaved-documents-entry")
        self.assertIn('id="hst_unsaved"', p["sfx2/uiconfig/ui/startcenter.ui"])
        self.assertIn("org.hst.office.vi:UnsavedDocuments", p["sfx2/source/dialog/backingwindow.cxx"])
        self.assertIn("org.hst.office.vi:UnsavedDocuments", p["sfx2/source/backstage/hstbackstagewindow.cxx"])
        addons = (EXT / "Addons.xcu").read_text(encoding="utf-8")
        self.assertTrue(ordered(addons, ".uno:PickList\\.uno:RecentFileList", "org.hst.office.vi:UnsavedDocuments"))

    def test_backup_copy_is_off_by_default(self):
        defaults = (EXT / "StartupDefaults.xcu").read_text(encoding="utf-8")
        self.assertTrue(ordered(defaults, '<node oor:name="Save">', '<node oor:name="Document">',
                                '<prop oor:name="CreateBackup">', "<value>false</value>"))

    def test_privacy_mentions_unsaved_documents(self):
        privacy = (ROOT / "docs/PRIVACY.md").read_text(encoding="utf-8")
        self.assertIn("hst-unsaved", privacy)
        self.assertIn("7 ngày", privacy)


if __name__ == "__main__":
    unittest.main()
