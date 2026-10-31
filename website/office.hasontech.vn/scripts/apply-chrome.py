#!/usr/bin/env python3
"""Gắn menu đầu trang + chân trang dùng chung (scripts/site_chrome.py) vào các trang tĩnh.

Chạy từ thư mục gốc website:  python3 scripts/apply-chrome.py
Trang hướng dẫn /huong-dan/ do scripts/sync-help.py dựng và cũng dùng site_chrome.
Lần đầu, header/footer cũ được bao bằng vùng đánh dấu; các lần sau chỉ thay trong vùng đó.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_chrome import apply_chrome

# trang -> mục menu đang mở
PAGES = {"index.html": "home", "diem-moi/index.html": "whats-new", "404.html": None}


def ensure_markers(html):
    if "<!-- site-header -->" not in html:
        html = re.sub(r'<header class="site-header">.*?</header>', lambda m: "<!-- site-header -->" + m.group(0) + "<!-- /site-header -->", html, count=1, flags=re.S)
    if "<!-- site-footer -->" not in html:
        html = re.sub(r'<footer class="site-footer">.*?</footer>', lambda m: "<!-- site-footer -->" + m.group(0) + "<!-- /site-footer -->", html, count=1, flags=re.S)
    return html


root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for rel, active in PAGES.items():
    path = os.path.join(root, rel)
    with open(path, encoding="utf-8") as fh:
        before = fh.read()
    after = apply_chrome(ensure_markers(before), active)
    if after != before:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(after)
    print(f"{rel}: {'cập nhật' if after != before else 'không đổi'}")
