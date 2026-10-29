# Upstream baseline

> Nguồn máy đọc: [`upstream/upstream-lock.json`](../upstream/upstream-lock.json). Tài liệu này giải thích; khi khác nhau, file lock là chuẩn.
> Xác minh ngày 2026-10-29 bằng GitHub API (`gh api`), không suy diễn.

## Source baseline (mã nguồn)

| Thành phần | Repo | Commit | Cách pin |
|---|---|---|---|
| Desktop Editors (meta) | ONLYOFFICE/DesktopEditors | `daf8c6948148827201b2907ac1134d222fbfa7b4` | tag `v10.0.0` (release 2026-10-13) |
| desktop-apps | ONLYOFFICE/desktop-apps | `332c1905a5361dd4139481827b7ad4f4a9facd85` | gitlink tại tag |
| core | ONLYOFFICE/core | `ed63e94de814ff1d4ea28cddfaba6939bc9df9ed` | gitlink tại tag |
| sdkjs | ONLYOFFICE/sdkjs | `9d2138866d929be32f1d107e8b5bfae36156e097` | gitlink tại tag |
| web-apps | ONLYOFFICE/web-apps-pro | `f79972a400c3a696490094961772d1f86fac1b82` | gitlink tại tag (submodule `web-apps` trỏ `web-apps-pro.git`) |
| build_tools | ONLYOFFICE/build_tools | `0e10c886756300fb86a17b672727824ab48bb67c` | best-effort: commit master cuối trước 2026-10-22T17:54Z |
| sdkjs-plugins | ONLYOFFICE/sdkjs-plugins | `06c4b858e6f1f49b27257c707f0bf71884e141d5` | best-effort như trên |
| document-templates | ONLYOFFICE/document-templates | `0a52fb76fa53fddf7d70da28878537cde3d29421` | best-effort; HST không dùng mẫu upstream |

Gitlink khác chưa audit license: `desktop-sdk@ae6cf2a0…`, `dictionaries@d3223bbb…` (xem BLOCKERS `LEG-04`).

**Khác biệt với brief:** brief không nêu phiên bản; baseline chọn v10.0.0 là release mới nhất tại ngày xác minh. Ba repo build_tools/sdkjs-plugins/document-templates **không có tag v10** và không là gitlink → SHA chỉ là provenance gần đúng, không tuyên bố đã được upstream dùng để build v10.0.0.

## Runtime binary (bản thực cài để kiểm thử)

| Mục | Giá trị |
|---|---|
| Asset | `onlyoffice-desktopeditors-x64.tar.xz` (release v10.0.0) |
| SHA-256 | `b44158be6499c6fb3813b5904d000f72ef4d93c0e8f6ea6696501e575995da9a` |
| Version string trong binary | `10.0.0.169` |
| Vị trí | `upstream/cache/ode/` (gitignored; giải nén, không cài vào hệ thống) |

Tag source ≠ binary: binary là bản build chính thức của Ascensio; HST không build lại.

### Ghi chú chạy trên Linux headless

- DesktopEditors **crash khi chạy bằng root** (`Gtk-ERROR: Can't create a GtkStyleContext without a display connection`, exit 133) dù `DISPLAY` hợp lệ. Chạy bằng user thường (`nobody`) hoạt động bình thường.
- Cờ `--remote-debugging-port=<port>` mở được Chrome DevTools Protocol của CEF → dùng cho kiểm thử runtime tự động (`scripts/runtime/`).
- Cần `LD_LIBRARY_PATH=<app dir>` như launcher upstream `usr/bin/onlyoffice-desktopeditors`.

## Môi trường dev thực tế (2026-10-29)

Ubuntu 24.04.4 LTS · 32 vCPU · 47 GiB RAM · ổ 198 GB, **trống ~56 GB** (brief giả định 8/16/50). Không build engine tại máy này (xem [BUILD_MATRIX](BUILD_MATRIX.md)).

## Cập nhật baseline

1. Chạy lại các lệnh trong [`plans/reports/audit-261029-hst-office.md`](../plans/reports/audit-261029-hst-office.md) với tag mới.
2. Cập nhật lock + `LICENSES/upstream/*` + diff license; nếu Additional Terms đổi → mở lại audit.
3. Chạy lại toàn bộ runtime QA trên binary mới; không tự nâng `minVersion` plugin trước khi pass.
