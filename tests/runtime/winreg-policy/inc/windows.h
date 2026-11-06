// SPDX-License-Identifier: AGPL-3.0-only
// In-memory registry standing in for the Win32 API, enough for configmgr/source/winreg.cxx.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <iterator>
#include <map>
#include <string>
typedef uint32_t DWORD;
typedef long LONG;
typedef unsigned char* LPBYTE;
struct MockKey {
    std::map<std::u16string, MockKey> sub;
    std::map<std::u16string, std::u16string> sz;
    std::map<std::u16string, DWORD> dw;
};
typedef MockKey* HKEY;
extern MockKey g_hklm, g_hkcu;
extern int g_open;
#define HKEY_LOCAL_MACHINE (&g_hklm)
#define HKEY_CURRENT_USER (&g_hkcu)
#define ERROR_SUCCESS 0L
#define KEY_READ 0x20019
inline std::u16string mock_s(const wchar_t* p) { std::u16string s; while (p && *p) s += char16_t(*p++); return s; }
inline LONG RegOpenKeyExW(HKEY parent, const wchar_t* name, DWORD, DWORD, HKEY* out) {
    MockKey* k = parent; std::u16string path = mock_s(name), part;
    for (size_t i = 0; i <= path.size(); ++i) {
        if (i == path.size() || path[i] == u'\\') {
            if (!part.empty()) { auto it = k->sub.find(part); if (it == k->sub.end()) return 2L; k = &it->second; }
            part.clear();
        } else part += path[i];
    }
    *out = k; ++g_open; return ERROR_SUCCESS;
}
inline LONG RegCloseKey(HKEY) { --g_open; return ERROR_SUCCESS; }
inline LONG RegQueryInfoKeyW(HKEY k, wchar_t*, DWORD*, DWORD*, DWORD* nSub, DWORD*, DWORD*, DWORD* nVal, DWORD* maxName,
                             DWORD* maxLen, void*, void*) {
    *nSub = k->sub.size(); *nVal = k->sz.size() + k->dw.size(); *maxName = 0; *maxLen = 4;
    for (auto& v : k->sz) { *maxName = std::max<DWORD>(*maxName, v.first.size()); *maxLen = std::max<DWORD>(*maxLen, 2 * (v.second.size() + 1)); }
    for (auto& v : k->dw) *maxName = std::max<DWORD>(*maxName, v.first.size());
    return ERROR_SUCCESS;
}
inline void mock_copy(wchar_t* d, const std::u16string& s) { for (char16_t c : s) *d++ = wchar_t(c); *d = 0; }
inline LONG RegEnumKeyExW(HKEY k, DWORD i, wchar_t* name, DWORD* size, DWORD*, wchar_t*, DWORD*, void*) {
    auto it = k->sub.begin(); std::advance(it, i); mock_copy(name, it->first); *size = it->first.size(); return ERROR_SUCCESS;
}
inline LONG RegEnumValueW(HKEY k, DWORD i, wchar_t* name, DWORD* nameLen, DWORD*, DWORD*, LPBYTE data, DWORD* len) {
    if (i < k->sz.size()) { auto it = k->sz.begin(); std::advance(it, i); mock_copy(name, it->first);
        mock_copy(reinterpret_cast<wchar_t*>(data), it->second); *nameLen = it->first.size(); *len = 2 * (it->second.size() + 1); }
    else { auto it = k->dw.begin(); std::advance(it, i - k->sz.size()); mock_copy(name, it->first);
        std::memcpy(data, &it->second, 4); *nameLen = it->first.size(); *len = 4; }
    return ERROR_SUCCESS;
}
inline int mock_wcscmp(const wchar_t* a, const wchar_t* b) { while (*a && *a == *b) { ++a; ++b; } return int(*a) - int(*b); }
#define wcscmp mock_wcscmp
// o3tl/char16_t2wchar_t.hxx only defines these on _WIN32; -fshort-wchar gives the same 16-bit wchar_t.
namespace o3tl {
inline wchar_t const* toW(char16_t const* p) { return reinterpret_cast<wchar_t const*>(p); }
inline wchar_t* toW(char16_t* p) { return reinterpret_cast<wchar_t*>(p); }
inline char16_t const* toU(wchar_t const* p) { return reinterpret_cast<char16_t const*>(p); }
inline char16_t* toU(wchar_t* p) { return reinterpret_cast<char16_t*>(p); }
}
