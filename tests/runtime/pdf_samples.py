# SPDX-License-Identifier: AGPL-3.0-only
"""Sample PDFs for the HST PDF viewer checks, made by HST Office itself.

Writes a flat ODF text document with Vietnamese text (one numbered page per page: heading
"Trang N", a contract-like paragraph and the marker HSTPDF-<N>), then converts it with
`soffice --headless --convert-to pdf` from the given install. Nothing is downloaded.
"""
import os
import shutil
import subprocess
import tempfile
from xml.sax.saxutils import escape

BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")
PARAGRAPH = ("Hôm nay, ngày 04 tháng 11 năm 2026, tại Đà Nẵng, chúng tôi gồm: Bên A là Công ty TNHH "
             "Công nghệ Hà Sơn; Bên B là khách hàng sử dụng dịch vụ. Hai bên thống nhất ký kết hợp đồng "
             "dịch vụ với các điều khoản sau đây: điều khoản thanh toán, nghĩa vụ bảo mật thông tin, "
             "thời hạn hiệu lực và giải quyết tranh chấp theo pháp luật Việt Nam.")


def _fodt(pages):
    body = []
    for n in range(1, pages + 1):
        style = "PB" if n > 1 else "P"
        body.append('<text:h text:style-name="%s" text:outline-level="1">Trang %d — HỢP ĐỒNG DỊCH VỤ</text:h>'
                    % (style, n))
        body.append("<text:p>%s</text:p>" % escape(PARAGRAPH))
        body.append("<text:p>Mã kiểm tra: HSTPDF-%d. Chữ ký số của bên A ở cuối hợp đồng.</text:p>" % n)
        for _ in range(4):
            body.append("<text:p>%s</text:p>" % escape(PARAGRAPH))
    return """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:automatic-styles>
  <style:style style:name="P" style:family="paragraph"/>
  <style:style style:name="PB" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/></style:style>
 </office:automatic-styles>
 <office:body><office:text>%s</office:text></office:body>
</office:document>
""" % "\n".join(body)


def make(instdir, target, pages):
    """Create `target` (a PDF with `pages` pages); returns the path. Reuses an existing file."""
    target = os.path.abspath(target)
    if os.path.exists(target):
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    work = tempfile.mkdtemp(prefix="hstpdf-samples-")
    try:
        stem = os.path.splitext(os.path.basename(target))[0]
        src = os.path.join(work, stem + ".fodt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(_fodt(pages))
        prefix = []
        if os.geteuid() == 0:
            subprocess.run(["chown", "-R", BUILD_USER, work], check=True)
            prefix = ["runuser", "-u", BUILD_USER, "--"]
        env = {k: v for k, v in os.environ.items() if k not in ("URE_BOOTSTRAP", "SAL_USE_VCLPLUGIN", "DISPLAY")}
        env.update(HOME=work, LANG="C.UTF-8")
        subprocess.run(prefix + [os.path.join(instdir, "program", "soffice"), "--headless", "--norestore",
                                 "-env:UserInstallation=file://%s/profile" % work, "--convert-to", "pdf",
                                 "--outdir", work, src], check=True, env=env, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.copyfile(os.path.join(work, stem + ".pdf"), target)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return target
