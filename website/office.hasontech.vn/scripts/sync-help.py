#!/usr/bin/env python3
"""Đồng bộ sách hướng dẫn trong ứng dụng (phím F1) lên website: office.hasontech.vn/huong-dan/.

Nguồn: extensions/hst-vietnamese-tools/help/ trong repo hst-office, đọc thẳng từ git theo tag phát hành
để hướng dẫn trên web luôn khớp bản đang phát hành (mặc định: tag trong config.js).

    python3 scripts/sync-help.py                 # dùng tag hiện hành trong config.js
    python3 scripts/sync-help.py --ref v1.0.0-beta.4

Kết quả (ghi đè hoàn toàn): huong-dan/index.html, huong-dan/<trang>/index.html, huong-dan/images/*,
và vùng <!-- huong-dan --> trong sitemap.xml. Chạy lại ở mỗi lần chuyển bản phát hành.
"""
import argparse, datetime, html, io, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_chrome import apply_chrome

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = subprocess.run(["git", "-C", SITE, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
SRC = "extensions/hst-vietnamese-tools/help"
OUT = os.path.join(SITE, "huong-dan")
BASE = "https://office.hasontech.vn"
GA = """  <!-- Google tag (gtag.js): tải sau thao tác đầu tiên hoặc 4 giây sau khi trang tải xong (xem index.html). -->
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-LRLQZ0R9QJ');
    (function () {
      var loaded = false, events = ['scroll', 'pointerdown', 'keydown', 'touchstart'];
      function load() {
        if (loaded) return; loaded = true;
        events.forEach(function (e) { removeEventListener(e, load); });
        var s = document.createElement('script'); s.async = true;
        s.src = 'https://www.googletagmanager.com/gtag/js?id=G-LRLQZ0R9QJ';
        document.head.appendChild(s);
      }
      events.forEach(function (e) { addEventListener(e, load, { once: true, passive: true }); });
      addEventListener('load', function () { setTimeout(load, 4000); });
    })();
  </script>
"""


def git(*args, binary=False):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode("utf-8")


def current_tag():
    m = re.search(r'tag:\s*"([^"]+)"', open(os.path.join(SITE, "config.js"), encoding="utf-8").read())
    return m.group(1)


def asset_version(name):
    m = re.search(name + r"\?v=(\d+)", open(os.path.join(SITE, "index.html"), encoding="utf-8").read())
    return m.group(1) if m else "1"


# Thẻ ứng dụng ở trang mục lục hướng dẫn: gắn biểu tượng HST (dùng chung ảnh với trang chủ) theo trang đích.
APP_ICONS = {"van-ban": ("writer", "Văn bản"), "bang-tinh": ("sheets", "Bảng tính"), "trinh-chieu": ("slides", "Trình chiếu")}


def add_app_icons(fragment):
    def repl(m):
        key = next((k for k in APP_ICONS if m.group(2).startswith(f"/huong-dan/{k}")), None)
        if not key:
            return m.group(0)
        icon, label = APP_ICONS[key]
        pic = (f'<picture class="app-icon"><source srcset="/assets/img/hst-{icon}-128.webp?v=1" type="image/webp">'
               f'<img src="/assets/img/hst-{icon}-128.png?v=1" alt="" width="128" height="128" loading="lazy" decoding="async"></picture>')
        return f'<section class="app app-{icon}">{pic}{m.group(1)}'
    return re.sub(r'<section class="app">(<h2><a href="([^"]+)")', repl, fragment)


def page_url(slug):
    return "/huong-dan/" if slug == "index" else f"/huong-dan/{slug}/"


def text_of(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=None, help="tag/commit nguồn (mặc định: tag trong config.js)")
    a = ap.parse_args()
    ref = a.ref or current_tag()
    version = ref.lstrip("v")
    names = git("ls-tree", "--name-only", f"{ref}:{SRC}").split()
    pages = sorted(n[:-5] for n in names if n.endswith(".html"))
    images = git("ls-tree", "--name-only", f"{ref}:{SRC}/images").split() if "images" in names else []
    slugs = set(pages)

    def fix_links(fragment):
        # Liên kết nội bộ x.html(#a) -> /huong-dan/x/(#a); trang chưa có trong bản này -> chỉ giữ chữ.
        def repl(m):
            attrs, inner = m.group(1), m.group(2)
            h = re.search(r'href="([^"]*)"', attrs)
            href = h.group(1) if h else ""
            if href.startswith(("vnd.sun.star:", "file:", "../")):
                return inner
            mm = re.match(r"^([a-z0-9-]+)\.html(#[^\"]*)?$", href)
            if mm:
                if mm.group(1) not in slugs:
                    return inner
                attrs = attrs.replace(f'href="{href}"', f'href="{page_url(mm.group(1))}{mm.group(2) or ""}"')
            if href.startswith("https://hasontech.vn/"):
                attrs = attrs.replace("utm_source=hst-office&amp;utm_medium=help", "utm_source=office-hasontech-vn&amp;utm_medium=guide")
            return f"<a{attrs}>{inner}</a>"
        fragment = re.sub(r"<a(\s[^>]*)>(.*?)</a>", repl, fragment, flags=re.S)

        def img(m):
            tag = m.group(0)
            src = re.search(r'src="images/([^"]+)\.png"', tag)
            if not src:
                return tag
            base = src.group(1)
            tag = tag.replace(f'src="images/{base}.png"', f'src="/huong-dan/images/{base}.png"')
            if "decoding=" not in tag:
                tag = tag.replace("<img ", '<img decoding="async" ', 1)
            return f'<picture><source type="image/webp" srcset="/huong-dan/images/{base}.webp">{tag}</picture>'
        return re.sub(r"<img\s[^>]*>", img, fragment)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "images"))
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for name in images:
        data = git("show", f"{ref}:{SRC}/images/{name}", binary=True)
        open(os.path.join(OUT, "images", name), "wb").write(data)
        if name.endswith(".png") and Image:
            Image.open(io.BytesIO(data)).save(os.path.join(OUT, "images", name[:-4] + ".webp"), "WEBP", quality=82, method=6)

    css_v, js_v = asset_version("style.css"), asset_version("main.js")
    today = datetime.date.today().isoformat()
    for slug in pages:
        src = git("show", f"{ref}:{SRC}/{slug}.html")
        title = re.sub(r"\s*·\s*Hướng dẫn HST Office\s*$", "", text_of(re.search(r"<title>(.*?)</title>", src, re.S).group(1)))
        sidebar = re.search(r'<nav class="sidebar".*?</nav>', src, re.S).group(0)
        article = re.search(r"<article>.*?</article>", src, re.S).group(0)
        pnav = re.search(r'<nav class="page-nav".*?</nav>', src, re.S)
        pnav = pnav.group(0) if pnav else ""
        lead = re.search(r'<p class="lead">(.*?)</p>', article, re.S) or re.search(r"<p>(.*?)</p>", article, re.S)
        desc = text_of(lead.group(1)) if lead else title
        if len(desc) > 158:
            desc = desc[:155].rsplit(" ", 1)[0] + "…"
        sidebar = fix_links(sidebar).replace('class="sidebar"', 'class="guide-sidebar"')
        sidebar = re.sub(r"\saria-current=\"page\"", "", sidebar)
        sidebar = sidebar.replace(f'href="{page_url(slug)}"', f'href="{page_url(slug)}" aria-current="page"')
        sidebar = re.sub(r'<a href="([^"]*)" >', r'<a href="\1">', sidebar)
        mobile_toc = '<details class="guide-toc-mobile"><summary>Các trang hướng dẫn</summary>' + sidebar.replace('class="guide-sidebar"', 'class="guide-sidebar-list"').replace('<nav ', '<div ').replace("</nav>", "</div>") + "</details>"
        full_title = "Hướng dẫn sử dụng HST Office – Bộ Office miễn phí tiếng Việt" if slug == "index" else f"{title} – Hướng dẫn HST Office"
        url = BASE + page_url(slug)
        crumbs = [{"@type": "ListItem", "position": 1, "name": "HST Office", "item": BASE + "/"},
                  {"@type": "ListItem", "position": 2, "name": "Hướng dẫn", "item": BASE + "/huong-dan/"}]
        if slug != "index":
            crumbs.append({"@type": "ListItem", "position": 3, "name": title, "item": url})
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "TechArticle", "@id": url + "#article", "headline": title, "description": desc, "inLanguage": "vi", "url": url,
             "dateModified": today, "about": {"@id": BASE + "/#software"}, "publisher": {"@id": "https://hasontech.vn/#organization"},
             "isPartOf": {"@id": BASE + "/#website"}, "version": version},
            {"@type": "BreadcrumbList", "itemListElement": crumbs}]}
        crumb_html = '<nav class="guide-breadcrumb" aria-label="Đường dẫn"><a href="/">Trang chủ</a><span aria-hidden="true">›</span>' + (
            '<span aria-current="page">Hướng dẫn</span>' if slug == "index" else f'<a href="/huong-dan/">Hướng dẫn</a><span aria-hidden="true">›</span><span aria-current="page">{html.escape(title)}</span>') + "</nav>"
        page = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
{GA}  <title>{html.escape(full_title)}</title>
  <meta name="description" content="{html.escape(desc)}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <meta name="theme-color" content="#0B6FC1">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="article">
  <meta property="og:locale" content="vi_VN">
  <meta property="og:site_name" content="HST Office">
  <meta property="og:title" content="{html.escape(full_title)}">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{BASE}/assets/img/og-hst-office.jpg?v=2">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/assets/img/favicon.svg?v=1" type="image/svg+xml">
  <link rel="icon" href="/assets/img/favicon-32.png?v=1" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png?v=1" sizes="180x180">
  <script>document.documentElement.classList.add('nav-enhanced')</script>
  <link rel="stylesheet" href="/assets/css/style.css?v={css_v}">
  <script src="/assets/js/main.js?v={js_v}" defer></script>
  <script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=1)}
  </script>
</head>
<body class="guide-page">
  <svg class="svg-library" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><symbol id="i-download" viewBox="0 0 24 24"><path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5"/></symbol></svg>
  <a href="#noi-dung" class="skip-link">Đến nội dung chính</a>
  <!-- site-header --><!-- /site-header -->
  <main id="noi-dung" class="guide">
    <div class="container guide-top">
      {crumb_html}
      <p class="guide-version"><span class="status-dot" aria-hidden="true"></span> Hướng dẫn cho HST Office phiên bản {html.escape(version)}</p>
    </div>
    <div class="container guide-layout">
      {sidebar}
      <div class="guide-body">
        {mobile_toc}
        {add_app_icons(fix_links(article))}
        {fix_links(pnav)}
      </div>
    </div>
  </main>
  <!-- site-footer --><!-- /site-footer -->
</body>
</html>
"""
        page = apply_chrome(page, "guide")
        dest = os.path.join(OUT, "index.html") if slug == "index" else os.path.join(OUT, slug, "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "w", encoding="utf-8").write(page)

    # Sitemap: thay vùng hướng dẫn, giữ nguyên các URL khác.
    sm_path = os.path.join(SITE, "sitemap.xml")
    sm = open(sm_path, encoding="utf-8").read()
    block = "  <!-- huong-dan -->\n" + "".join(f"  <url>\n    <loc>{BASE}{page_url(s)}</loc>\n    <lastmod>{today}</lastmod>\n  </url>\n" for s in ["index"] + [p for p in pages if p != "index"]) + "  <!-- /huong-dan -->\n"
    if "<!-- huong-dan -->" in sm:
        sm = re.sub(r"  <!-- huong-dan -->.*?<!-- /huong-dan -->\n", lambda _m: block, sm, flags=re.S)
    else:
        sm = sm.replace("</urlset>", block + "</urlset>")
    open(sm_path, "w", encoding="utf-8").write(sm)
    print(f"Đồng bộ {len(pages)} trang, {len(images)} ảnh từ {ref} → huong-dan/ (phiên bản {version})")


if __name__ == "__main__":
    main()
