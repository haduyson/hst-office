#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Reads the ladder states of the Sheets mockup (mockup-sheets-slides-draw/hinh-mau-sheets.html) at each width.

Usage: /root/.claude/skills/.venv/bin/python3 -I tests/runtime/render-sheets-mockup-expected.py \
           <mockup>/hinh-mau-sheets.html <out.json>
Renders the page in headless Chromium 1248 (the reference used for the Writer vectors), per tab (home, insert) and
width of the Writer set, and writes {"source", "states": {"home-1366": {"states": {...}, "used_pct"}}} in the same form
as ribbon-mockup-expected.json. Groups are the page's own keys (clip, font, align, number, styles, cellstyles, cells,
edit on Trang đầu); the owner's decision keeps the cell styles inside Kiểu.
"""
import json
import sys

from playwright.sync_api import sync_playwright

WIDTHS = [1100, 1280, 1366, 1440, 1485, 1600, 1920]
TABS = ["home", "insert"]


def main():
    src, out = sys.argv[1], sys.argv[2]
    result = {"source": "mockup-sheets-slides-draw/hinh-mau-sheets.html, headless Chromium 1248, 96 DPI", "states": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome")
        page = browser.new_page(viewport={"width": 2100, "height": 1200})
        page.goto("file://" + src, wait_until="load", timeout=60000)
        page.wait_for_function('typeof main !== "undefined" && main', timeout=20000)
        for tab in TABS:
            for width in WIDTHS:
                value = page.evaluate('''([tab, w]) => { main.setMode("full"); main.showTab(tab); main.setWidth(w);
                    return {states: main.S.states, pct: Math.round(main.S.used / main.S.avail * 1000) / 10}; }''', [tab, width])
                result["states"][f"{tab}-{width}"] = {"states": value["states"], "used_pct": value["pct"]}
        browser.close()
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(out)


if __name__ == "__main__":
    sys.exit(main())
