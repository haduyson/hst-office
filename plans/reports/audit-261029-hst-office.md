# Audit report — Phase 00 (2026-10-29)

Executor: Claude. Môi trường: Ubuntu 24.04.4, 32 vCPU, 47 GiB RAM, ~56 GB trống, `gh` auth user haduyson.

## Lệnh & kết quả

| Lệnh | Kết quả |
|---|---|
| `gh api repos/ONLYOFFICE/DesktopEditors/releases/latest` | `v10.0.0 2026-10-13T10:18:58Z` |
| `gh api repos/ONLYOFFICE/DesktopEditors/git/ref/tags/v10.0.0` | `daf8c694…` commit |
| `gh api repos/ONLYOFFICE/DesktopEditors/contents/<sub>?ref=v10.0.0` | gitlink SHA 6 submodule (xem lock) |
| `gh api repos/ONLYOFFICE/<r>/git/ref/tags/v10.0.0` | 404 cho mọi repo phụ thuộc → không có tag v10 riêng |
| `gh api repos/ONLYOFFICE/<r>/commits?sha=master&until=2026-10-22T17:54:33Z&per_page=1` | SHA best-effort cho build_tools, sdkjs-plugins, document-templates |
| `gh api …/contents/LICENSE?ref=<sha> -H Accept: raw` | 8 file vào `LICENSES/upstream/`; hash: 6×`3a9b4b6a…`, 2×`c71d239d…` |
| `gh release download v10.0.0 -p onlyoffice-desktopeditors-x64.tar.xz` | SHA-256 `b44158be…5da9a`, giải nén 1.2 GB |
| `sha256sum editors/sdkjs-plugins/v1/*` (binary) | plugins.js `1bc0bd71…`, plugins-ui.js `4896dd85…`, plugins.css `d0fabc8d…` |
| Chạy `DesktopEditors` dưới root + Xvfb | exit 133, Gtk-ERROR (không phải lỗi display) |
| Chạy dưới `nobody` + `--remote-debugging-port=9333` | OK; CDP liệt kê `api/documents/index.html`; iframe editor truy cập được; `Asc.editor.GetVersion()` = `10.0.0` |
| `AscDesktopEditor.GetInstallPlugins()` | 2 root: thư mục cài (9 plugin hệ thống) và `~/.local/share/onlyoffice/desktopeditors/data/sdkjs-plugins/` |
| Tải PDF NĐ30 từ datafiles.chinhphu.vn | SHA-256 `be251446…9178`, 76 trang scan; đọc Phụ lục I trang 21–28 |
| `WebFetch onlyoffice.com/trademark-policy` | Không có nội dung policy (JS) → LEG-02 |

## Giới hạn

- SHA best-effort cho 3 repo không phải gitlink: không chứng minh upstream dùng đúng commit đó.
- Không kiểm `3DPARTYLICENSE` chi tiết, `desktop-sdk`, `dictionaries` (LEG-04).
- Không có ý kiến pháp lý; không đánh dấu legal approved.

## Deliverables

`docs/UPSTREAM_BASELINE.md`, `docs/LICENSE_AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_MATRIX.md`, `docs/BLOCKERS.md`, `docs/ADR/0001-plugin-first-unmodified-upstream.md`, `docs/PLUGIN_CONTRACT.md`, `docs/VIETNAMESE_OFFICE_SPEC.md`, `upstream/upstream-lock.json`, `LICENSES/upstream/*`, `LICENSE` (AGPLv3, gnu.org).

## Unresolved questions

- Trademark policy nguyên văn (LEG-02).
- Trạng thái hiệu lực NĐ30 năm 2026 (LEG-05).
