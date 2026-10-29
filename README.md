# HST Office

Bộ công cụ văn phòng miễn phí, offline cho người Việt — **HST Writer**, **HST Sheets**, **HST Slides** — do Công ty TNHH Công nghệ Hà Sơn (**HASON TECH**) phát triển/tùy biến.

> **Trạng thái: đang phát triển — chưa có bản phát hành.** Vòng plugin-first: HST Office xây dựng **plugin và bộ mẫu tiếng Việt** chạy trên **ONLYOFFICE Desktop Editors v10.0.0 nguyên bản** (phần mềm gốc của Ascensio System SIA). Chưa có bộ cài “HST Office” riêng — việc fork/đổi thương hiệu đang chờ duyệt pháp lý (xem [docs/BLOCKERS.md](docs/BLOCKERS.md)).

## Thành phần (đang triển khai)

| Plugin | Ứng dụng | Chức năng |
|---|---|---|
| Văn bản hành chính (NĐ30) | Writer | Chèn công văn, quyết định, tờ trình… theo thể thức Phụ lục I NĐ 30/2020; áp lề A4 |
| Chuyển mã tiếng Việt | Writer | TCVN3 (ABC) / VNI → Unicode có xem trước và Undo |
| Định dạng & CSV Việt | Sheets | Định dạng VND, `dd/mm/yyyy`, %; nhập CSV UTF-8 an toàn |
| Mẫu tiếng Việt | Writer/Sheets/Slides | Thư viện 18 mẫu văn phòng offline |

## Cài đặt nhanh

1. Cài ONLYOFFICE Desktop Editors từ <https://github.com/ONLYOFFICE/DesktopEditors/releases>.
2. Tải các file `.plugin` của HST Office, mở trình biên tập → **Plugins → Plugin Manager → Install plugin manually** → chọn file.

Chi tiết: [docs/PLUGIN_INSTALLATION.md](docs/PLUGIN_INSTALLATION.md). Tài liệu đầy đủ: [docs/README.md](docs/README.md).

## Phát triển

```bash
npm ci && npm test && npm run build:plugins
```

Xem [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Giấy phép & ghi nhận

- Mã nguồn HST Office: [GNU AGPL-3.0](LICENSE). Nội dung mẫu văn bản: CC BY 4.0.
- HST Office **không** sở hữu engine. ONLYOFFICE là thương hiệu và phần mềm gốc của Ascensio System SIA. Xem [NOTICE.md](NOTICE.md) và [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Liên hệ

HASON TECH — 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, TP. Đà Nẵng · <https://hasontech.vn> · 0236 3.507.507 · lienhe@hasontech.vn
