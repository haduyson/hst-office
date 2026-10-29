# License & trademark audit

> Trạng thái: **bằng chứng kỹ thuật đã thu thập; CHƯA được người có thẩm quyền pháp lý duyệt.** Tài liệu này không phải ý kiến pháp lý.
> Ngày: 2026-10-29. Commit: xem [UPSTREAM_BASELINE](UPSTREAM_BASELINE.md).

## 1. Văn bản đã lưu nguyên văn

| Repo @ commit | File lưu | SHA-256 |
|---|---|---|
| DesktopEditors, desktop-apps, core, sdkjs, web-apps-pro, build_tools | `LICENSES/upstream/<id>/LICENSE` | `3a9b4b6ab698d668dcedcda1c2da598f4ca9789a0d8b4aefb90e00e2cb425040` (6 file **giống hệt**) |
| sdkjs-plugins, document-templates | `LICENSES/upstream/<id>/LICENSE` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` (Apache-2.0, giống hệt) |
| Binary v10.0.0 Linux | `opt/onlyoffice/desktopeditors/LICENSE.txt`, `3DPARTYLICENSE` trong tarball | không phân phối lại |

Không repo nào trong 8 repo có file NOTICE/TERMS tách riêng tại commit pin (kiểm bằng liệt kê thư mục gốc).

## 2. Nội dung chính — AGPLv3 + Additional Terms (Section 7)

File AGPL của 6 repo gồm toàn văn GNU AGPLv3 và phần **Additional Terms** (trích nguyên văn ý chính):

1. **Retention of Notices and Attribution** — giữ mọi copyright/license/disclaimer/attribution notice.
2. **Modification Notice Requirement** — bản sửa đổi phải có thông báo rõ đã sửa đổi, **kèm ngày sửa đổi**, và ghi rõ dựa trên phần mềm ONLYOFFICE gốc của Ascensio System SIA.
3. **Appropriate Legal Notices in UI** — UI phải cho người dùng (i) biết ONLYOFFICE là nhà phát triển gốc, (ii) biết bản đang dùng có thể đã sửa đổi, (iii) truy cập thông tin license.
4. **No Trademark License** — không cấp quyền dùng trademark/logo/branding; theo Trademark Policy <https://www.onlyoffice.com/trademark-policy>.
5. **Non-Code Content** — minh họa, icon set, tài liệu kỹ thuật theo **CC BY-SA 4.0**.

Header file nguồn (vd. `plugins.js`) còn ghi: *“Pursuant to Section 7(b) … you must retain the original Product logo when distributing the program.”* — điều khoản này **xung đột tiềm năng** với rebrand shell (đường B) → blocker `LEG-01`.

## 3. Phát hiện quan trọng

| ID | Phát hiện | Hệ quả |
|---|---|---|
| F1 | Metadata GitHub `sdkjs-plugins` = Apache-2.0, nhưng bridge `v1/plugins.js` thực ship trong binary mang **header AGPL** (build từ `sdkjs/common/plugins/plugin_base*.js`, ánh xạ build chưa tái tạo — UNVERIFIED). | Plugin HST vendor **chỉ** `plugins.js` → mỗi package kèm `LICENSE-ONLYOFFICE.txt` (AGPL + Additional Terms nguyên văn) và giữ header. |
| F1b | `v1/plugins-ui.js` nhúng **PerfectScrollbar**; `v1/plugins.css` nhúng **ảnh UI ONLYOFFICE** (Additional Terms 5: CC BY-SA 4.0). | **Không** phân phối lại hai file này; plugin HST dùng CSS/UI tự viết. |
| F2 | 6 repo AGPL dùng cùng một file license (hash trùng). | Áp dụng đồng nhất Additional Terms 1–5. |
| F3 | Trademark Policy chỉ render bằng JavaScript, không trích được nội dung qua fetch tự động. | Blocker `LEG-02`: cần người đọc và lưu bản chính sách. |
| F4 | Mã mới HST: chủ dự án chọn **AGPL-3.0** (2026-10-29); nội dung mẫu văn bản **CC BY 4.0**. | `LICENSE` gốc repo = AGPLv3 nguyên văn từ gnu.org (SHA-256 `0d96a4ff…abcb0`). |

## 4. Kết luận theo phạm vi

| Phạm vi | Trạng thái | Điều kiện |
|---|---|---|
| Spike nội bộ: chạy binary upstream nguyên trạng, cài plugin HST vào profile thử | **Cho phép** | Không phân phối lại binary. |
| Phát hành plugin `.plugin` + gói mẫu HST (đường A) | **Có thể, chờ duyệt** | Giữ header AGPL của bridge, kèm `LICENSE`, NOTICE, link source; plugin không dùng logo/tên ONLYOFFICE làm nhãn; About plugin ghi rõ chạy trên ONLYOFFICE gốc (chưa sửa đổi). Cần owner/legal ký duyệt `LEG-03`. |
| Fork/rebrand shell, installer “HST Office” (đường B) | **BLOCKED** | `LEG-01`, `LEG-02`, `LEG-04`; cần ý kiến pháp lý về điều 7(b) logo + trademark, và notice sửa đổi có ngày trong UI. |

## 5. Fonts & assets

- HST **không đóng gói font**. Mẫu khai báo Times New Roman/Arial; dùng font có sẵn trên máy, thiếu thì engine thay thế và tài liệu ghi rõ.
- Logo HASON TECH: asset do chủ dự án cung cấp trực tiếp (không lấy từ web), SHA-256 `2f77a5fc…d2ef`; dẫn xuất xem [BRAND](BRAND.md).
- Không dùng icon/illustration ONLYOFFICE (CC BY-SA 4.0 + trademark) trong plugin HST.

## 6. Nghĩa vụ source tương ứng (đường A)

Dự kiến: repo public `github.com/haduyson/hst-office` chứa toàn bộ mã nguồn plugin/script/mẫu; mỗi artifact ghi commit SHA trong `build-info.json`/manifest (thực hiện ở Phase 02/06). Bridge vendor có provenance tại `third_party/onlyoffice-plugin-sdk/provenance.json`; ánh xạ minified → source chưa tái tạo, giữ trong release gate `LEG-03`.
