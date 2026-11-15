"""Thẻ ảnh chia sẻ (og:image, twitter:image) riêng cho từng trang office.hasontech.vn.

Danh sách trang, tiêu đề ảnh và minh hoạ nằm trong scripts/og/pages.json; ảnh sinh bằng
scripts/render-og-images.py vào assets/img/og/<slug>.jpg. `apply_og(html, rel)` thay khối thẻ ảnh trong
<head> của một trang (dùng chung cho render-og-images.py, sync-help.py và build-install-guide.py) nên dựng
lại trang bằng script nào cũng giữ đúng ảnh riêng. Tham số ?v= là sha256[:8] của tệp ảnh: đổi ảnh thì
mạng xã hội tải lại ảnh mới.
"""
import hashlib, html, json, os, re, sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://office.hasontech.vn"
MANIFEST = os.path.join(SITE, "scripts", "og", "pages.json")
IMG_DIR = os.path.join(SITE, "assets", "img", "og")
WIDTH, HEIGHT = 1200, 630
# Thẻ do khối này quản lý; các thẻ og:title/description/url và twitter:title/description giữ nguyên.
MANAGED = re.compile(r'[ \t]*<meta (?:property="og:image(?::[a-z_]+)?"|name="twitter:(?:card|image(?::alt)?)") content="[^"]*">\n')


def load_pages():
    """Trả về {đường dẫn tệp HTML tính từ gốc site: mục trong pages.json}."""
    with open(MANIFEST, encoding="utf-8") as fh:
        pages = json.load(fh)["pages"]
    slugs = [p["slug"] for p in pages]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"{MANIFEST}: slug bị trùng")
    return {p["html"]: p for p in pages}


def image_path(slug):
    return os.path.join(IMG_DIR, slug + ".jpg")


def image_version(slug):
    with open(image_path(slug), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:8]


def alt_text(entry):
    title = " ".join(entry["title"].split())  # \n trong tiêu đề chỉ là chỗ xuống dòng trên ảnh
    return f"{title} — {entry['subtitle']}. HST Office, bộ ứng dụng văn phòng miễn phí của HASON TECH."


def entry_for(rel, pages=None):
    """Mục manifest của trang; trang chưa khai báo dùng ảnh của mục cha (và cảnh báo để bổ sung)."""
    pages = pages if pages is not None else load_pages()
    if rel in pages:
        return pages[rel]
    fallback = "huong-dan/index.html" if rel.startswith("huong-dan/") else "cai-dat/index.html" if rel.startswith("cai-dat/") else "index.html"
    print(f"Cảnh báo: {rel} chưa có trong scripts/og/pages.json, tạm dùng ảnh của {fallback}. "
          "Thêm mục cho trang rồi chạy scripts/render-og-images.py.", file=sys.stderr)
    return pages[fallback]


def og_block(entry, indent="  "):
    url = f"{BASE}/assets/img/og/{entry['slug']}.jpg?v={image_version(entry['slug'])}"
    alt = html.escape(alt_text(entry))
    tags = [('property="og:image"', url), ('property="og:image:type"', "image/jpeg"),
            ('property="og:image:width"', str(WIDTH)), ('property="og:image:height"', str(HEIGHT)),
            ('property="og:image:alt"', alt), ('name="twitter:card"', "summary_large_image"),
            ('name="twitter:image"', url), ('name="twitter:image:alt"', alt)]
    return "".join(f'{indent}<meta {attr} content="{value}">\n' for attr, value in tags)


def keeps_image(entry):
    """Mục có keep_existing_image: trang giữ nguyên thẻ ảnh đang có, không dựng ảnh og riêng."""
    return bool(entry.get("keep_existing_image"))


def apply_og(page, rel, pages=None):
    """Thay khối thẻ ảnh trong <head>; chèn ngay sau og:url (hoặc trước </head> nếu trang không có og:url)."""
    pages = pages if pages is not None else load_pages()
    entry = entry_for(rel, pages)
    if keeps_image(entry):
        return page
    head, sep, body = page.partition("</head>")
    if not sep:
        raise ValueError(f"{rel}: không có </head>")
    head = MANAGED.sub("", head)
    m = re.search(r'([ \t]*)<meta property="og:url" content="([^"]*)">\n', head)
    if m:
        expected = BASE + entry["url"]
        if rel in pages and m.group(2) != expected:
            raise ValueError(f"{rel}: og:url {m.group(2)} khác {expected} trong pages.json")
        head = head[:m.end()] + og_block(entry, m.group(1)) + head[m.end():]
    else:
        head = head.rstrip(" ") + og_block(entry)
    return head + sep + body
