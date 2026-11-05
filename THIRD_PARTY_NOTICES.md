# Third-party notices

| Thành phần | Phiên bản | Giấy phép | Dùng ở đâu | Văn bản |
|---|---|---|---|---|
| LibreOffice | 26.8.1.1 | MPL-2.0 (+ LGPLv3/GPLv3 cho một số phần, theo header) | Engine của HST Office (build từ source, có patch HST) | `LICENSES/upstream/libreoffice/` |
| Thư viện bên ngoài LibreOffice bundle (ICU, Skia, harfbuzz, …) | theo `download.lst` tại commit pin | nhiều loại | Trong gói cài | `license.xml` / `NOTICE` trong gói cài (`LICENSES/upstream/libreoffice/license.xml`) |
| Từ điển chính tả tiếng Việt | 1.0.45 | GPLv2 | Kiểm tra chính tả `vi` | `LICENSES/upstream/libreoffice-dictionary-vi/` |
| python-docx, openpyxl, python-pptx, lxml, Pillow, PyYAML (build-time) | `requirements-templates.lock` | MIT / MIT / MIT / BSD-3-Clause / HPND / MIT | Sinh asset/kiểm thử, không đóng gói | PyPI |
| Liberation Sans Bold Italic (build-time) | fonts-liberation 2.1.5 | SIL OFL 1.1 | Raster hoá chữ "HST OFFICE" trong logo; font không đóng gói | gói Ubuntu |

| Be Vietnam Pro Regular / SemiBold / Bold | fetched 2026-11-04; hashes in [banner sources](assets/banners/SOURCES.md) | SIL OFL 1.1 | Bundled banner artwork and regeneration | [OFL.txt](extensions/hst-vietnamese-tools/banners/fonts/OFL.txt) |

Solution logos are HASON TECH/product marks; provenance and owner-requested derivative details: [banner sources](assets/banners/SOURCES.md).

Mẫu HST không nhúng font, ảnh hay nội dung của bên thứ ba.

Nền trình chiếu đi cùng LibreOffice giữ giấy phép và tác giả gốc, tên tác giả nằm trong thuộc tính "Người tạo" của mẫu. HST đã sửa tất cả 23 nền: thay ảnh thu nhỏ, bỏ chuỗi tên chương trình tạo tệp; Freshes còn đổi chữ mẫu sang tiếng Việt (`scripts/templates/apply-presnt-vi.py`). Năm nền sau có mô tả được bỏ, giấy phép chuyển sang thuộc tính "License"; mô tả gốc gồm cả nguồn ảnh và biểu tượng giữ nguyên văn ở [LICENSES/presentation-backgrounds.md](LICENSES/presentation-backgrounds.md):

| Nền | Tác giả | Giấy phép |
|---|---|---|
| Candy | Ermin D. Alita, Annisa Aulia Rasyidah, Laila Muhdi, Cahyaning Asih, @li_Orch | CC BY-SA 4.0 |
| Freshes | Risyad Rais | CC BY-SA 4.0 |
| Grey Elegant | Ahmad Bayhaqi Saputra | CC BY-SA 4.0 |
| Growing Liberty | Budi Aryo @tokofoss | CC BY-SA 4.0 |
| Yellow Idea | Dwi Alita @ealita.id | CC BY-SA 4.0 |
