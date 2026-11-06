// SPDX-License-Identifier: AGPL-3.0-only
// Runs dumpWindowsRegistry of the patched configmgr/source/winreg.cxx against an in-memory registry: the Windows
// policy layers read HST Office's own key, and from the old upstream key only the HSTUpdate subtree, and only while
// HST Office's key of the same hive lacks it. Built and run by tests/runtime/check-winreg-policy.sh.
#include <cstdio>
#include <string>
#include <rtl/ustring.hxx>
#include "windows.h"
#include "winreg.hxx"
#include "writemodfile.hxx"
MockKey g_hklm, g_hkcu;
int g_open = 0;
namespace configmgr { std::string g_last; }
using configmgr::g_last;
static int failures = 0;
static void check(bool ok, const char* what) { std::printf("%s %s\n", ok ? "PASS" : "FAIL", what); if (!ok) ++failures; }
static MockKey& key(MockKey& root, std::u16string path) {
    MockKey* k = &root; std::u16string part;
    for (size_t i = 0; i <= path.size(); ++i) {
        if (i == path.size() || path[i] == u'\\') { if (!part.empty()) k = &k->sub[part]; part.clear(); } else part += path[i];
    }
    return *k;
}
static void lock(MockKey& root, std::u16string path, std::u16string value) {
    MockKey& k = key(root, path); k.sz[u"Value"] = value; k.dw[u"Final"] = 1;
}
static bool dump(configmgr::WinRegType t) { g_last.clear(); OUString url; bool r = configmgr::dumpWindowsRegistry(&url, t);
    if (r)
        osl_removeFile(url.pData);
    return r;
}
static bool has(const char* s) { return g_last.find(s) != std::string::npos; }
const std::u16string HST = u"SOFTWARE\\Policies\\HASON TECH\\HST Office\\", LO = u"SOFTWARE\\Policies\\LibreOffice\\";
int main() {
    check(!dump(configmgr::LOCAL_MACHINE), "no policy key: nothing read");
    lock(g_hklm, LO + u"org.openoffice.Office.Common\\Misc\\ShowTipOfTheDay", u"false");
    check(!dump(configmgr::LOCAL_MACHINE), "LibreOffice key without the update subtree: nothing read");
    lock(g_hklm, LO + u"org.openoffice.Office.HSTUpdate\\AllowInstall", u"false");
    check(dump(configmgr::LOCAL_MACHINE), "old update lock: read");
    check(has("<item oor:path=\"/org.openoffice.Office.HSTUpdate\"><prop oor:name=\"AllowInstall\" oor:finalized=\"true\"><value>false</value></prop></item>"),
          "old update lock: AllowInstall finalized");
    check(!has("ShowTipOfTheDay") && !has("org.openoffice.Office.Common"), "other LibreOffice policy ignored");
    lock(g_hklm, HST + u"org.openoffice.Office.Common\\Misc\\ShowTipOfTheDay", u"true");
    check(dump(configmgr::LOCAL_MACHINE) && has("/org.openoffice.Office.Common/Misc\"><prop oor:name=\"ShowTipOfTheDay\" oor:finalized=\"true\"><value>true</value>"),
          "HST key: other policy read");
    check(has("AllowInstall"), "HST key without the update subtree: old update lock still read");
    lock(g_hklm, HST + u"org.openoffice.Office.HSTUpdate\\Channel", u"stable");
    check(dump(configmgr::LOCAL_MACHINE) && has("Channel") && !has("AllowInstall"), "HST update subtree wins over the old one");
    key(g_hklm, HST + u"org.openoffice.Office.HSTUpdate").sub.clear();
    check(dump(configmgr::LOCAL_MACHINE) && !has("HSTUpdate") && has("ShowTipOfTheDay"), "empty HST update subtree hides the old one");
    lock(g_hkcu, LO + u"org.openoffice.Office.HSTUpdate\\AutoCheck", u"false");
    check(dump(configmgr::CURRENT_USER) && has("AutoCheck") && !has("ShowTipOfTheDay"), "per-user hive decided on its own");
    check(g_open == 0, "every opened key closed");
    std::printf("%d failure(s)\n", failures);
    return failures != 0;
}
