# Third-party notices

| Thành phần | Phiên bản | Giấy phép | Dùng ở đâu | Văn bản |
|---|---|---|---|---|
| LibreOffice | 26.8.1.1 | MPL-2.0 (+ LGPLv3/GPLv3 cho một số phần, theo header) | Engine của HST Office (build từ source, có patch HST) | `LICENSES/upstream/libreoffice/` |
| Thư viện bên ngoài LibreOffice bundle (ICU, Skia, harfbuzz, …) | theo `download.lst` tại commit pin | nhiều loại | Trong gói cài | `license.xml` / `NOTICE` trong gói cài (`LICENSES/upstream/libreoffice/license.xml`) |
| Từ điển chính tả tiếng Việt | 1.0.45 | GPLv2 | Kiểm tra chính tả `vi` | `LICENSES/upstream/libreoffice-dictionary-vi/` |
| python-docx, openpyxl, python-pptx, lxml, Pillow, PyYAML (build-time) | `requirements-templates.lock` | MIT / MIT / MIT / BSD-3-Clause / HPND / MIT | Sinh asset/kiểm thử, không đóng gói | PyPI |
| Liberation Sans Bold Italic (build-time) | fonts-liberation 2.1.5 | SIL OFL 1.1 | Raster hoá chữ "HST OFFICE" trong logo; font không đóng gói | gói Ubuntu |

Mẫu HST không nhúng font, ảnh hay nội dung của bên thứ ba.
