# HST Office

Bộ ứng dụng văn phòng miễn phí, offline cho người Việt — **HST Writer** (văn bản), **HST Sheets** (bảng tính), **HST Slides** (trình chiếu) — do Công ty TNHH Công nghệ Hà Sơn (**HASON TECH**) phát triển, **dựa trên LibreOffice**.

> **Trạng thái: đang phát triển — chưa có bản phát hành.** Bản đầu tiên nhắm Ubuntu/Debian x86_64 (`.deb`). Windows/macOS chờ máy build (xem [docs/BLOCKERS.md](docs/BLOCKERS.md)).

## Điểm khác so với LibreOffice gốc

- Nhận diện HST Office (splash, About, icon, launcher), giao diện **Tabbed** (giống Ribbon) mặc định.
- Tiếng Việt: giao diện tiếng Việt khi hệ điều hành dùng tiếng Việt; từ điển chính tả `vi`; khổ A4 và Times New Roman mặc định.
- Công cụ tích hợp: soạn văn bản hành chính theo **NĐ 30/2020/NĐ-CP**, chuyển mã **TCVN3/VNI → Unicode**, định dạng **VND / dd/mm/yyyy**, nhập **CSV UTF-8** an toàn, 18 mẫu văn phòng.
- Không telemetry, không cần tài khoản hay Internet.
- Điều tra và xử lý độ trễ menu chuột phải trên macOS ([docs/CONTEXT_MENU_PERFORMANCE.md](docs/CONTEXT_MENU_PERFORMANCE.md)).

## Build (Linux)

```bash
python3 scripts/stage-branding.py
sudo scripts/build-linux.sh --configure
sudo python3 scripts/measure-job.py --json build/metrics/linux-build.json -- scripts/build-linux.sh --build
sudo scripts/build-linux.sh --package
```

Chi tiết: [docs/UPSTREAM_BASELINE.md](docs/UPSTREAM_BASELINE.md), [docs/BUILD_MATRIX.md](docs/BUILD_MATRIX.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Giấy phép & ghi nhận

HST Office dựa trên LibreOffice (MPL-2.0) của The Document Foundation; mã HST mới theo [AGPL-3.0](LICENSE); mẫu văn bản CC BY 4.0. Xem [NOTICE.md](NOTICE.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).

## Liên hệ

HASON TECH — 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, TP. Đà Nẵng · <https://hasontech.vn> · 0236 3.507.507 · lienhe@hasontech.vn
