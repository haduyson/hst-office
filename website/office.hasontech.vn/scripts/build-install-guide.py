#!/usr/bin/env python3
"""Dựng mục "Hướng dẫn cài đặt" (/cai-dat/) của office.hasontech.vn từ nội dung trong scripts/install-guide/.

Chạy từ thư mục gốc website:  python3 scripts/build-install-guide.py
- Nội dung từng trang: scripts/install-guide/<trang>.html (phần trong <article>). {VERSION}, {MSI}, {DMG_ARM},
  {DMG_INTEL}, {DEB} được thay theo phiên bản trong config.js, nên khi ra bản mới chỉ cần chạy lại.
- Ảnh: đặt ảnh gốc ở scripts/install-guide/images/<tên>.png và viết <img src="images/<tên>.png" alt="…"> trong nội
  dung. Script thu nhỏ (tối đa 1200 px), ghi cai-dat/images/<tên>.png + .webp, gắn ?v=<sha256[:8]> vì ảnh được cache
  một năm, thêm width/height chống xô lệch trang. Thiếu ảnh gốc thì dừng với lỗi (không để khung ảnh trống).
- {CARD_WINDOWS}, {CARD_MACOS}, {CARD_LINUX}: ô tải về lấy nguyên từ mục Tải về của index.html (bỏ dòng đếm lượt tải),
  nên nút và trạng thái do config.js + main.js điều khiển giống trang chủ.
- {ERROR_INDEX}: ô tìm nhanh + mục lục dựng từ các <section class="err-group"> (h2 có id) và
  <section class="err-item" id=… data-keywords=…> (h3). main.js lọc các mục theo từ khóa, không phân biệt dấu.
- Trang nằm ngoài /huong-dan/ vì scripts/sync-help.py xóa và dựng lại toàn bộ thư mục đó.
Menu đầu trang và chân trang lấy từ site_chrome.py (mục đang mở: "install").
"""
import hashlib, html, io, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_chrome import apply_chrome

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(SITE, "scripts", "install-guide")
OUT = os.path.join(SITE, "cai-dat")
BASE = "https://office.hasontech.vn"
MAX_WIDTH = 1200

# đường dẫn trên site, tệp nội dung, tiêu đề <title>, mô tả, tên ở đường dẫn, trang trước/sau (nhãn, đường dẫn)
PAGES = [
    {"url": "/cai-dat/", "src": "cai-dat.html", "out": "index.html",
     "title": "Hướng dẫn cài đặt HST Office trên Windows, macOS, Linux",
     "description": "Tải và cài HST Office miễn phí từng bước trên Windows 10/11, macOS (Apple Silicon và Intel), Ubuntu, Debian, Linux Mint. Kèm cách gỡ cài đặt và kiểm tra bộ cài.",
     "crumb": "Hướng dẫn cài đặt", "prev": None, "next": ("Gỡ lỗi khi cài đặt", "/cai-dat/go-loi/")},
    {"url": "/cai-dat/go-loi/", "src": "go-loi.html", "out": "go-loi/index.html",
     "title": "Gỡ lỗi khi cài đặt HST Office – Lỗi 1603, SmartScreen và lỗi thường gặp",
     "description": "Cách xử lý các lỗi khi cài HST Office: lỗi 1603 do Kiểm soát ứng dụng thông minh (Smart App Control), cảnh báo SmartScreen, máy Windows 32-bit, gói Linux và macOS.",
     "crumb": "Gỡ lỗi khi cài đặt", "prev": ("Hướng dẫn cài đặt", "/cai-dat/"), "next": ("Hướng dẫn sử dụng", "/huong-dan/")},
]

SIDEBAR = [
    ("Cài đặt", [("Trước khi cài", "/cai-dat/#truoc-khi-cai"), ("Windows", "/cai-dat/#windows"), ("macOS", "/cai-dat/#macos"),
                 ("Linux", "/cai-dat/#linux"), ("Gỡ cài đặt", "/cai-dat/#go-cai-dat"), ("Kiểm tra bộ cài", "/cai-dat/#kiem-tra-bo-cai")]),
    ("Khi gặp lỗi", [("Gỡ lỗi khi cài đặt", "/cai-dat/go-loi/")]),
    ("Tiếp theo", [("Hướng dẫn sử dụng", "/huong-dan/")]),
]

HEAD = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Google tag (gtag.js): tải sau thao tác đầu tiên hoặc 4 giây sau khi trang tải xong (xem index.html). -->
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-LRLQZ0R9QJ');
    (function () {{
      var loaded = false, events = ['scroll', 'pointerdown', 'keydown', 'touchstart'];
      function load() {{
        if (loaded) return; loaded = true;
        events.forEach(function (e) {{ removeEventListener(e, load); }});
        var s = document.createElement('script'); s.async = true;
        s.src = 'https://www.googletagmanager.com/gtag/js?id=G-LRLQZ0R9QJ';
        document.head.appendChild(s);
      }}
      events.forEach(function (e) {{ addEventListener(e, load, {{ once: true, passive: true }}); }});
      addEventListener('load', function () {{ setTimeout(load, 4000); }});
    }})();
  </script>
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <meta name="theme-color" content="#0B6FC1">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="article">
  <meta property="og:locale" content="vi_VN">
  <meta property="og:site_name" content="HST Office">
  <meta property="og:title" content="{crumb} — HST Office">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="https://office.hasontech.vn/assets/img/og-hst-office.jpg?v=2">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="628">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/assets/img/favicon.svg?v=1" type="image/svg+xml">
  <link rel="icon" href="/assets/img/favicon-32.png?v=1" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png?v=1" sizes="180x180">
  <link rel="preload" href="/assets/fonts/be-vietnam-pro-latin-800-normal.woff2?v=1" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/assets/fonts/be-vietnam-pro-vietnamese-800-normal.woff2?v=1" as="font" type="font/woff2" crossorigin>
  <script>document.documentElement.classList.add('nav-enhanced')</script>
  <link rel="stylesheet" href="/assets/css/style.css?v={css_v}">
  <script src="/config.js?v={config_v}" defer></script>
  <script src="/assets/js/main.js?v={js_v}" defer></script>
  <script type="application/ld+json">
{jsonld}
  </script>
</head>
<body>
  <svg class="svg-library" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">{symbols}</svg>
  <a href="#noi-dung" class="skip-link">Đến nội dung chính</a>
  <!-- site-header -->
  <!-- /site-header -->
  <main id="noi-dung" class="guide">
    <div class="container guide-top">
      <nav class="guide-breadcrumb" aria-label="Đường dẫn">{breadcrumb}</nav>
      <p class="guide-version"><span class="status-dot" aria-hidden="true"></span> Hướng dẫn cho HST Office phiên bản {version}</p>
    </div>
    <div class="container guide-layout">
      <nav class="guide-sidebar" aria-label="Hướng dẫn cài đặt">{sidebar}</nav>
      <div class="guide-body">
        <details class="guide-toc-mobile"><summary>Mục lục hướng dẫn cài đặt</summary><div class="guide-sidebar-list">{sidebar}</div></details>
        <article>
{content}
        </article>
        <nav class="page-nav" aria-label="Chuyển trang hướng dẫn">{page_nav}</nav>
      </div>
    </div>
  </main>
  <!-- site-footer -->
  <!-- /site-footer -->
</body>
</html>
"""


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def asset_version(name):
    """Số ?v= của CSS/JS lấy từ index.html để mọi trang dùng cùng bản (giống sync-help.py)."""
    m = re.search(re.escape(name) + r"\?v=(\d+)", read(os.path.join(SITE, "index.html")))
    return m.group(1) if m else "1"


def release_version():
    m = re.search(r'version:\s*"([^"]+)"', read(os.path.join(SITE, "config.js")))
    if not m:
        raise SystemExit("không đọc được version trong config.js")
    return m.group(1)


def sidebar(current_url):
    parts = []
    for heading, links in SIDEBAR:
        current = ' aria-current="page"'
        items = "".join(f'<li><a href="{href}"{current if href == current_url else ""}>{label}</a></li>'
                        for label, href in links)
        parts.append(f"<section><h2>{heading}</h2><ul>{items}</ul></section>")
    return "".join(parts)


def picture(tag):
    """<img src="images/x.png" alt="…"> → <picture> webp + png đã thu nhỏ, có ?v= và kích thước."""
    from PIL import Image
    src = re.search(r'src="images/([a-z0-9-]+)\.png"', tag)
    if not src:
        return tag
    name = src.group(1)
    raw = os.path.join(SRC, "images", name + ".png")
    if not os.path.exists(raw):
        raise SystemExit(f"thiếu ảnh gốc {os.path.relpath(raw, SITE)}")
    im = Image.open(raw)
    im.load()
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    png, webp = io.BytesIO(), io.BytesIO()
    im.save(png, "PNG", optimize=True)
    im.save(webp, "WEBP", quality=82, method=6)
    for ext, buf in (("png", png), ("webp", webp)):
        with open(os.path.join(OUT, "images", f"{name}.{ext}"), "wb") as fh:
            fh.write(buf.getvalue())
    v = hashlib.sha256(png.getvalue()).hexdigest()[:8]
    tag = tag.replace(f'src="images/{name}.png"',
                      f'src="/cai-dat/images/{name}.png?v={v}" width="{im.width}" height="{im.height}" loading="lazy" decoding="async"')
    return f'<picture><source type="image/webp" srcset="/cai-dat/images/{name}.webp?v={v}">{tag}</picture>'


def home_snippets():
    """Ô tải về và biểu tượng SVG lấy từ index.html để trang cài đặt luôn giống mục Tải về của trang chủ."""
    home = read(os.path.join(SITE, "index.html"))
    symbols = "".join(re.search(r'<symbol id="%s"[\s\S]*?</symbol>' % name, home).group(0)
                      for name in ("i-download", "i-copy", "i-windows", "i-apple", "i-linux"))
    cards = {}
    for key in ("windows", "macos", "linux"):
        card = re.search(r'<article class="download-card[^"]*" data-platform-card="%s"[\s\S]*?</article>' % key, home).group(0)
        card = card.replace(" data-reveal", "")
        start = card.find('<span class="download-count')
        if start >= 0:  # bỏ dòng đếm lượt tải (span lồng nhau): trang này không tải /thong-ke.json
            depth, end = 0, start
            for m in re.finditer(r"<span\b|</span>", card[start:]):
                depth += 1 if m.group(0) == "<span" else -1
                if depth == 0:
                    end = start + m.end()
                    break
            card = card[:start] + card[end:]
        cards["CARD_" + key.upper()] = f'<div class="install-download">{card}</div>'
    return symbols, cards


def strip_tags(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def error_index(content):
    """Ô tìm nhanh + mục lục cho trang gỡ lỗi, dựng từ các nhóm (h2) và mục lỗi (h3) trong nội dung."""
    groups = []
    for group in content.split('<section class="err-group">')[1:]:
        h2 = re.search(r'<h2 id="([^"]+)">([\s\S]*?)</h2>', group)
        items = re.findall(r'<section class="err-item" id="([^"]+)"[^>]*>\s*<h3>([\s\S]*?)</h3>', group)
        links = "".join(f'<li data-target="{i}"><a href="#{i}">{html.escape(strip_tags(t))}</a></li>' for i, t in items)
        groups.append(f'<div class="error-index-group" data-group="{h2.group(1)}"><p class="error-index-title">'
                      f'<a href="#{h2.group(1)}">{strip_tags(h2.group(2))}</a></p><ul>{links}</ul></div>')
    return ('<div class="error-finder" data-error-finder hidden>'
            '<label for="error-search">Tìm nhanh lỗi bạn gặp</label>'
            '<input id="error-search" type="search" placeholder="Gõ mã lỗi hoặc nội dung thông báo, ví dụ: 1603, SmartScreen, glibc" autocomplete="off" enterkeyhint="search">'
            '<p class="error-finder-status" role="status" aria-live="polite"></p>'
            '<p class="error-empty" hidden>Không thấy lỗi phù hợp. Hãy thử từ khóa khác hoặc xem <a href="#van-chua-duoc">Vẫn chưa cài được</a>.</p></div>\n'
            '<nav class="error-index" aria-label="Mục lục các lỗi"><p class="error-index-heading">Mục lục</p>'
            f'<div class="error-index-groups">{"".join(groups)}</div></nav>')


def jsonld(page, version):
    import json
    url = BASE + page["url"]
    crumbs = [("HST Office", BASE + "/"), ("Hướng dẫn cài đặt", BASE + "/cai-dat/")]
    if page["url"] != "/cai-dat/":
        crumbs.append((page["crumb"], url))
    graph = [
        {"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": page["title"], "description": page["description"],
         "inLanguage": "vi", "isPartOf": {"@id": BASE + "/#website"}, "about": {"@id": BASE + "/#software"},
         "breadcrumb": {"@id": url + "#breadcrumb"}},
        {"@type": "BreadcrumbList", "@id": url + "#breadcrumb",
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]},
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)


def build(page, version, versions, snippets):
    names = {"VERSION": version, "MSI": f"HSTOffice_{version}_Win_x86-64_en-US_vi.msi",
             "DMG_ARM": f"HSTOffice_{version}_macOS_arm64.dmg", "DMG_INTEL": f"HSTOffice_{version}_macOS_x86_64.dmg",
             "DEB": f"HSTOffice_{version}_Linux_x86-64.deb"}
    content = read(os.path.join(SRC, page["src"]))
    for key, value in names.items():
        content = content.replace("{" + key + "}", value)
    symbols, cards = snippets
    for key, card in cards.items():
        content = content.replace("{" + key + "}", card)
    if "{ERROR_INDEX}" in content:
        content = content.replace("{ERROR_INDEX}", error_index(content))
    content = re.sub(r"<img\s[^>]*>", lambda m: picture(m.group(0)), content)
    crumb = '<a href="/">Trang chủ</a><span aria-hidden="true">›</span>'
    if page["url"] == "/cai-dat/":
        crumb += '<span aria-current="page">Hướng dẫn cài đặt</span>'
    else:
        crumb += f'<a href="/cai-dat/">Hướng dẫn cài đặt</a><span aria-hidden="true">›</span><span aria-current="page">{page["crumb"]}</span>'
    nav = ""
    if page["prev"]:
        nav += f'<a href="{page["prev"][1]}" rel="prev"><strong>← Trang trước</strong><span>{page["prev"][0]}</span></a>'
    if page["next"]:
        nav += f'<a href="{page["next"][1]}" rel="next"><strong>Trang sau →</strong><span>{page["next"][0]}</span></a>'
    out = HEAD.format(title=html.escape(page["title"]), description=html.escape(page["description"]), url=BASE + page["url"],
                      crumb=page["crumb"], jsonld=jsonld(page, version), breadcrumb=crumb, version=version,
                      sidebar=sidebar(page["url"]), content=content.rstrip(), page_nav=nav, symbols=symbols, **versions)
    out = apply_chrome(out, "install")
    path = os.path.join(OUT, page["out"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(os.path.relpath(path, SITE))


if __name__ == "__main__":
    version = release_version()
    versions = {"css_v": asset_version("style.css"), "js_v": asset_version("main.js"), "config_v": asset_version("config.js")}
    snippets = home_snippets()
    for page in PAGES:
        build(page, version, versions, snippets)
