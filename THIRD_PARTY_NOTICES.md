# Third-party notices

HST Office là phần mềm độc quyền của HASON TECH theo [Điều khoản sử dụng phần mềm HST Office](LICENSE). Các thành phần bên thứ ba dưới đây theo giấy phép riêng của chúng; Điều khoản sử dụng không hạn chế quyền của người dùng theo các giấy phép đó. Mã nguồn tương ứng của các thành phần theo MPL-2.0, LGPL hoặc GPL trong một bản phát hành: gửi yêu cầu tới lienhe@hasontech.vn.

HST Office is proprietary software of HASON TECH under the [HST Office Software Terms of Use](LICENSE). The third-party components below are under their own licences; the Terms of Use do not restrict the user's rights under them. Corresponding source of the MPL-2.0, LGPL and GPL components of a release: on request to lienhe@hasontech.vn.

| Thành phần | Phiên bản | Giấy phép | Dùng ở đâu | Văn bản |
|---|---|---|---|---|
| LibreOffice | theo `upstream/libreoffice-lock.json` | MPL-2.0 (+ LGPLv3/GPLv3 cho một số phần, theo header) | Engine của HST Office (build từ source; tệp LibreOffice HST sửa giữ giấy phép của tệp) | `LICENSES/upstream/libreoffice/` |
| Thư viện bên ngoài LibreOffice bundle (ICU, Skia, harfbuzz, …) | theo `download.lst` tại commit pin | nhiều loại | Trong gói cài | `license.xml` / `NOTICE` trong gói cài (`LICENSES/upstream/libreoffice/license.xml`) |
| Từ điển chính tả tiếng Việt | 1.0.45 | GPLv2 | Kiểm tra chính tả `vi` | `LICENSES/upstream/libreoffice-dictionary-vi/` |
| python-docx, openpyxl, python-pptx, lxml, Pillow, PyYAML, NumPy (build-time) | `requirements-templates.lock` | MIT / MIT / MIT / BSD-3-Clause / HPND / MIT / BSD-3-Clause | Sinh asset/kiểm thử, không đóng gói | PyPI |
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
