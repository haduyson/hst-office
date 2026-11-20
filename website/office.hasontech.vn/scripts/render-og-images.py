#!/usr/bin/env python3
"""Sinh ảnh chia sẻ 1200x630 riêng cho từng trang và cập nhật thẻ og:image / twitter:image.

Chạy từ thư mục gốc website (cần Pillow và Playwright có Chromium: pip install playwright pillow &&
python3 -m playwright install chromium):

    python3 scripts/render-og-images.py                     # dựng mọi ảnh, gắn thẻ meta, kiểm tra
    python3 scripts/render-og-images.py --only huong-dan-nd30 --sheet /tmp/og-sheet.jpg
    python3 scripts/render-og-images.py --check             # chỉ kiểm tra thẻ và ảnh hiện có

Mẫu: scripts/og/template.html (HTML/SVG, chạy hàm renderOg(data) rồi ogCheck() để bảo đảm chữ nằm trong
vùng an toàn). Nội dung từng ảnh: scripts/og/pages.json. Ảnh ra: assets/img/og/<slug>.jpg (JPEG ≤ 300 KB).
Trang mới: thêm mục vào pages.json rồi chạy lại script này; sync-help.py và build-install-guide.py tự gắn thẻ.
"""
import argparse, glob, io, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from og_meta import BASE, HEIGHT, IMG_DIR, SITE, WIDTH, apply_og, image_path, load_pages

TEMPLATE = os.path.join(SITE, "scripts", "og", "template.html")
MAX_BYTES = 300 * 1024


def encode_jpeg(png_bytes):
    """JPEG 4:4:4 (chữ nhỏ không nhoè màu), giảm chất lượng tới khi dưới MAX_BYTES."""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    for quality in (90, 86, 82, 78, 74, 70):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, subsampling=0, optimize=True, progressive=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
    raise RuntimeError(f"ảnh vẫn lớn hơn {MAX_BYTES} byte ở chất lượng 70")


def render(entries, chromium=None):
    from playwright.sync_api import sync_playwright
    os.makedirs(IMG_DIR, exist_ok=True)
    failed = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium)
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            for entry in entries:
                page.goto("file://" + TEMPLATE)
                page.evaluate("d => window.renderOg(d)", entry)
                check = page.evaluate("() => window.ogCheck()")
                if not check["ok"]:
                    failed.append(f"{entry['slug']}: " + "; ".join(check["problems"]))
                    continue
                data = encode_jpeg(page.screenshot(type="png", clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT}))
                with open(image_path(entry["slug"]), "wb") as fh:
                    fh.write(data)
                print(f"{entry['slug']}.jpg  {len(data) // 1024} KB")
        finally:
            browser.close()
    if failed:
        sys.exit("Mẫu báo lỗi bố cục (chữ ra ngoài vùng an toàn hoặc tràn dòng):\n  " + "\n  ".join(failed))


def public_pages():
    """Mọi trang HTML công khai (trừ 404.html: trang lỗi noindex, không có URL riêng để chia sẻ)."""
    rels = [os.path.relpath(p, SITE) for p in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True)]
    return sorted(r for r in rels if not r.startswith("scripts" + os.sep) and r != "404.html")


def apply_all(pages):
    for rel in public_pages():
        path = os.path.join(SITE, rel)
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        after = apply_og(before, rel, pages)
        if after != before:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(after)
            print(f"{rel}: cập nhật thẻ ảnh")


def meta(head, attr):
    m = re.search(rf'<meta {attr} content="([^"]*)">', head)
    return m.group(1) if m else None


def verify(pages):
    from PIL import Image
    problems, seen = [], {}
    for rel in public_pages():
        with open(os.path.join(SITE, rel), encoding="utf-8") as fh:
            head = fh.read().split("</head>")[0]
        img = meta(head, 'property="og:image"') or ""
        if rel not in pages:
            problems.append(f"{rel}: chưa có mục trong scripts/og/pages.json")
        if not img.startswith(BASE + "/assets/img/og/") or "?v=" not in img:
            problems.append(f"{rel}: og:image không trỏ tới assets/img/og/…?v=: {img}")
            continue
        file = os.path.join(SITE, img[len(BASE) + 1:].split("?")[0])
        if not os.path.isfile(file):
            problems.append(f"{rel}: thiếu tệp {file}")
            continue
        size = Image.open(file).size
        if size != (WIDTH, HEIGHT) or os.path.getsize(file) > MAX_BYTES:
            problems.append(f"{rel}: {file} có kích thước {size}, {os.path.getsize(file)} byte")
        if meta(head, 'name="twitter:image"') != img or meta(head, 'name="twitter:card"') != "summary_large_image":
            problems.append(f"{rel}: twitter:image/twitter:card không khớp og:image")
        for attr in ('property="og:image:alt"', 'property="og:title"', 'property="og:description"'):
            if not meta(head, attr):
                problems.append(f"{rel}: thiếu {attr}")
        if (meta(head, 'property="og:image:width"'), meta(head, 'property="og:image:height"')) != (str(WIDTH), str(HEIGHT)):
            problems.append(f"{rel}: og:image:width/height sai")
        url = meta(head, 'property="og:url"')
        if rel in pages and url != BASE + pages[rel]["url"]:
            problems.append(f"{rel}: og:url {url} không khớp {pages[rel]['url']}")
        seen.setdefault(img.split("?")[0], []).append(rel)
    problems += [f"dùng chung ảnh {img}: {', '.join(rels)}" for img, rels in seen.items() if len(rels) > 1]
    print(f"Kiểm tra {len(public_pages())} trang: " + ("đạt" if not problems else f"{len(problems)} lỗi"))
    return problems


def contact_sheet(entries, out, cols=3, scale=0.5):
    """Ghép ảnh thành lưới để duyệt bằng mắt (mỗi ô 600x315, kèm slug)."""
    from PIL import Image, ImageDraw
    w, h, label = int(WIDTH * scale), int(HEIGHT * scale), 28
    rows = (len(entries) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 16) + 16, rows * (h + label + 16) + 16), "#e9eef4")
    draw = ImageDraw.Draw(sheet)
    for i, entry in enumerate(entries):
        x, y = 16 + (i % cols) * (w + 16), 16 + (i // cols) * (h + label + 16)
        sheet.paste(Image.open(image_path(entry["slug"])).convert("RGB").resize((w, h), Image.LANCZOS), (x, y))
        draw.text((x, y + h + 6), f"{entry['slug']}  ({entry['url']})", fill="#172d47")
    sheet.save(out, "JPEG", quality=88)
    print(f"Lưới duyệt: {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", metavar="SLUG", help="chỉ dựng các ảnh này")
    ap.add_argument("--check", action="store_true", help="không dựng ảnh, chỉ kiểm tra")
    ap.add_argument("--sheet", metavar="JPG", help="ghép mọi ảnh thành lưới để duyệt")
    ap.add_argument("--chromium", metavar="PATH", help="tệp chạy Chromium/headless shell (khi bản Playwright cài sẵn khác phiên bản)")
    a = ap.parse_args()
    pages = load_pages()
    entries = list(pages.values())
    if a.only:
        unknown = set(a.only) - {e["slug"] for e in entries}
        if unknown:
            sys.exit(f"slug không có trong pages.json: {', '.join(sorted(unknown))}")
    if not a.check:
        render([e for e in entries if not a.only or e["slug"] in a.only], a.chromium)
        apply_all(pages)
    if a.sheet:
        contact_sheet(entries, a.sheet)
    problems = verify(pages)
    if problems:
        sys.exit("\n".join(problems))


if __name__ == "__main__":
    main()
