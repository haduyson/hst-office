// SPDX-License-Identifier: AGPL-3.0-only
// Test double of configmgr/source/writemodfile.hxx: collects the generated .xcu text in memory.
#pragma once
#include <string>
#include <string_view>
#include <rtl/ustring.hxx>
#include <osl/file.h>
namespace configmgr {
extern std::string g_last;
struct TempFile {
    OUString url;
    oslFileHandle handle = nullptr;
    std::string text;
    ~TempFile() { if (handle) osl_closeFile(handle); }
    oslFileError closeWithoutUnlink() { g_last = text; oslFileError e = osl_closeFile(handle); handle = nullptr; return e; }
    void writeString(std::string_view s) { text += s; }
};
inline void writeAttributeValue(TempFile& f, std::u16string_view v) { f.writeString(OUStringToOString(v, RTL_TEXTENCODING_UTF8)); }
inline void writeValueContent(TempFile& f, std::u16string_view v) { writeAttributeValue(f, v); }
}
