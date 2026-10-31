"""Khung dùng chung (menu đầu trang + chân trang) cho mọi trang office.hasontech.vn.

Mỗi trang HTML chứa hai vùng đánh dấu:
    <!-- site-header -->…<!-- /site-header -->   và   <!-- site-footer -->…<!-- /site-footer -->
`apply_chrome()` thay nội dung hai vùng này bằng bản dựng từ NAV bên dưới, nên menu và chân trang
không thể lệch nhau giữa các trang. Sửa menu: sửa NAV rồi chạy scripts/apply-chrome.py.
"""
import re

# (nhãn, đường dẫn, khóa mục đang mở). Khóa so với `active` của trang để gắn aria-current.
NAV = [
    ("Trang chủ", "/", "home"),
    ("Tính năng", "/#tinh-nang", None),
    ("Hướng dẫn", "/huong-dan/", "guide"),
    ("Điểm mới", "/diem-moi/", "whats-new"),
    ("Liên hệ", "#lien-he", None),
]
CTA = ("Tải miễn phí", "/#tai-ve")
FOOTER_NAV = [("Trang chủ", "/", "home"), ("Tính năng", "/#tinh-nang", None), ("Tải về", "/#tai-ve", None),
              ("Hướng dẫn", "/huong-dan/", "guide"), ("Điểm mới", "/diem-moi/", "whats-new")]

LOGO = ('<picture><source srcset="/assets/img/hst-office-logo-400.webp?v=1" type="image/webp">'
        '<img src="/assets/img/hst-office-logo-400.png?v=1" width="400" height="105" alt="HST Office" decoding="async"></picture>')


def _link(label, href, key, active, cls=""):
    current = ' aria-current="page"' if key and key == active else ""
    cls_attr = f' class="{cls}"' if cls else ""
    return f'<a{cls_attr} href="{href}"{current}>{label}</a>'


def render_header(active):
    links = "\n        ".join(_link(l, h, k, active) for l, h, k in NAV)
    return f"""<header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="/" aria-label="HST Office — Trang chủ">
        {LOGO}
      </a>
      <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="main-nav" hidden><span>Menu</span><span class="menu-lines" aria-hidden="true"></span></button>
      <nav class="main-nav" id="main-nav" aria-label="Điều hướng chính">
        {links}
        <a class="button button-small" href="{CTA[1]}">{CTA[0]} <svg class="icon" aria-hidden="true"><use href="#i-download"/></svg></a>
      </nav>
    </div>
  </header>"""


FOOTER_TEMPLATE = '<footer class="site-footer">\n    <div class="container">\n      <div class="footer-main"><div class="footer-brand"><a class="brand" href="/" aria-label="HST Office — Trang chủ"><picture><source srcset="/assets/img/hst-office-logo-400.webp?v=1" type="image/webp"><img src="/assets/img/hst-office-logo-400.png?v=1" width="400" height="105" alt="HST Office" loading="lazy" decoding="async"></picture></a><p>Bộ ứng dụng văn phòng dành cho người Việt.<br> Miễn phí vĩnh viễn. Đồng hành mỗi ngày.</p><span class="product-by">Sản phẩm của <strong>HASON TECH</strong></span>{FOOTER_NAV}</div><div class="footer-contact" id="lien-he"><a class="company-logo" href="https://hasontech.vn/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" aria-label="HASON TECH — hasontech.vn"><picture><source srcset="/assets/img/hasontech-logo-240.webp?v=1" type="image/webp"><img src="/assets/img/hasontech-logo-240.png?v=1" width="240" height="187" alt="Logo HASON TECH" loading="lazy" decoding="async"></picture></a><div class="company-info"><h2>Công ty TNHH Công&nbsp;nghệ Hà&nbsp;Sơn <span>(HASON TECH)</span></h2><address>300 Xô&nbsp;Viết Nghệ&nbsp;Tĩnh, phường Cẩm&nbsp;Lệ, <span class="nowrap">TP. Đà Nẵng</span></address><div class="contact-links"><a href="tel:+842363507507">(0236) 3.507.507</a><a href="mailto:lienhe@hasontech.vn">lienhe@hasontech.vn</a><a href="https://hasontech.vn/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0">hasontech.vn <span aria-hidden="true">↗</span></a></div></div></div></div>\n      <div class="ecosystem"><p>KHÁM PHÁ GIẢI PHÁP HASON TECH</p><nav aria-label="Giải pháp HASON TECH"><a href="https://aios.hasontech.vn/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" rel="nofollow">AIOS <span aria-hidden="true">↗</span></a><a href="https://echatbot.vn/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" rel="nofollow">eChatbot <span aria-hidden="true">↗</span></a><a href="https://espace.vn/zaloapp?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" rel="nofollow">Zalo Mini App <span aria-hidden="true">↗</span></a><a href="https://seo.hasontech.vn/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" rel="nofollow">HST SEO <span aria-hidden="true">↗</span></a><a href="https://post.hasontech.vn/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" rel="nofollow">HST Post <span aria-hidden="true">↗</span></a><a href="https://aidelam.com/?utm_source=office-hasontech-vn&amp;utm_medium=landing&amp;utm_campaign=hst-office-1-0" rel="nofollow">AI Dễ Lắm <span aria-hidden="true">↗</span></a></nav></div>\n      <div class="footer-legal"><p>© 2026 HASON TECH · © 2000–2026 The Document Foundation và các tác giả LibreOffice</p><p>HST Office được phát triển từ mã nguồn mở LibreOffice. Trân trọng cảm ơn The Document&nbsp;Foundation và cộng đồng LibreOffice. Phát hành theo giấy phép MPL&#8209;2.0.</p></div>\n    </div>\n  </footer>'


def render_footer(active):
    nav = '<nav class="footer-nav" aria-label="Liên kết trang">' + "".join(_link(l, h, k, active) for l, h, k in FOOTER_NAV) + "</nav>"
    return FOOTER_TEMPLATE.replace("{FOOTER_NAV}", nav)


def apply_chrome(html, active):
    """Thay vùng header/footer đã đánh dấu; trả về HTML mới. Báo lỗi nếu thiếu dấu."""
    for name, block in (("site-header", render_header(active)), ("site-footer", render_footer(active))):
        pattern = re.compile(r"<!-- %s -->.*?<!-- /%s -->" % (name, name), re.S)
        if not pattern.search(html):
            raise ValueError(f"thiếu vùng <!-- {name} --> trong trang")
        html = pattern.sub(lambda _m, b=block, n=name: f"<!-- {n} -->\n  {b}\n  <!-- /{n} -->", html, count=1)
    return html
