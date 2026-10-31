# SPDX-License-Identifier: AGPL-3.0-only
"""Ask each Vietnamese spell checker of a macOS HST Office which words it accepts (run with the bundled Python).

  spell-probe.py <out-dir>

Connects to the office on localhost:2002, lists the spell checking services configured and available for
vi-VN, then asks the dispatcher (what the documents use) and every service by itself about the words of
a Vietnamese paragraph written precomposed (NFC), decomposed (NFD) and with both tone placements.
Writes <out-dir>/spell-probe.json and spell-probe.md. Evidence only: always exits 0 once connected.
"""
import json
import sys
import time
import unicodedata

import uno

PORT = 2002
SERVICES = ["com.sun.star.linguistic2.SpellChecker", "org.openoffice.lingu.MySpellSpellChecker",
            "org.openoffice.lingu.MacOSXSpellChecker"]
PARAGRAPH = ("Vai trò cốt lõi của chuỗi cung ứng thông minh đối với được thể hiện qua trụ cột chiến lược "
             "tối ưu hóa tối ưu hoá tùy biến tuỳ biến thời gian sản phẩm thị trường khỏe khoẻ thủy thuỷ")


def connect():
    ctx = uno.getComponentContext()
    resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(120):
        try:
            return resolver.resolve(f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext")
        except Exception:  # noqa: BLE001
            time.sleep(1)
    raise SystemExit("cannot connect to soffice")


def main():
    out = sys.argv[1]
    ctx = connect()
    time.sleep(3)
    smgr = ctx.ServiceManager
    loc = uno.createUnoStruct("com.sun.star.lang.Locale")
    loc.Language, loc.Country = "vi", "VN"
    lsm = smgr.createInstanceWithContext("com.sun.star.linguistic2.LinguServiceManager", ctx)
    result = {"configured": list(lsm.getConfiguredServices("com.sun.star.linguistic2.SpellChecker", loc)),
              "available": list(lsm.getAvailableServices("com.sun.star.linguistic2.SpellChecker", loc)),
              "services": {}}
    words = PARAGRAPH.split()
    for name in SERVICES:
        try:
            svc = smgr.createInstanceWithContext(name, ctx)
        except Exception as error:  # noqa: BLE001
            result["services"][name] = {"error": repr(error)}
            continue
        if svc is None:
            result["services"][name] = {"error": "not available"}
            continue
        entry = {"hasLocale": bool(svc.hasLocale(loc))}
        for form in ("NFC", "NFD"):
            flagged = []
            for word in words:
                try:
                    if not svc.isValid(unicodedata.normalize(form, word), loc, ()):
                        flagged.append(word)
                except Exception as error:  # noqa: BLE001
                    flagged.append(f"{word}!{error!r}")
            entry[form] = flagged
        result["services"][name] = entry
    with open(f"{out}/spell-probe.json", "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    lines = ["# macOS Vietnamese spell probe", "", f"configured for vi-VN: {result['configured']}",
             f"available for vi-VN: {result['available']}", ""]
    for name, entry in result["services"].items():
        lines.append(f"- {name}: " + (entry.get("error") or f"hasLocale={entry['hasLocale']}; flagged NFC {entry['NFC']}; flagged NFD {entry['NFD']}"))
    with open(f"{out}/spell-probe.md", "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
