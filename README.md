# HST Office

Bộ ứng dụng văn phòng miễn phí, offline cho người Việt: 
**HST Writer** (văn bản); 
**HST Sheets** (bảng tính); 
**HST Slides** (trình chiếu); 
Do Công ty TNHH Công nghệ Hà Sơn (**HASON TECH**) phát triển.

> **Trạng thái: đang phát triển — chưa có bản phát hành.** Bản đầu tiên nhắm Ubuntu/Debian x86_64 (`.deb`). Windows/macOS chờ máy build (xem [docs/BLOCKERS.md](docs/BLOCKERS.md)).

## Điểm khác so với LibreOffice gốc

- Nhận diện HST Office (splash, About, icon, launcher).
- Tiếng Việt: giao diện tiếng Việt khi hệ điều hành dùng tiếng Việt; từ điển chính tả `vi`; khổ A4 và Times New Roman mặc định.
- Công cụ tích hợp: soạn văn bản hành chính theo **NĐ 30/2020/NĐ-CP**, chuyển mã **TCVN3/VNI → Unicode**, định dạng **VND / dd/mm/yyyy**, nhập **CSV UTF-8** an toàn, 18 mẫu văn phòng.
- Không telemetry, không cần tài khoản hay Internet.
- Extension chỉ cài từ tệp `.oxt` do người dùng tự chọn (có hộp thoại xác nhận, người dùng tự chịu trách nhiệm); không có đường dẫn tới kho extension trực tuyến, không kiểm tra cập nhật extension qua mạng.
- Điều tra và xử lý độ trễ menu chuột phải trên macOS ([docs/CONTEXT_MENU_PERFORMANCE.md](docs/CONTEXT_MENU_PERFORMANCE.md)).

## Build (Linux)

```bash
python3 scripts/stage-branding.py
sudo scripts/build-linux.sh --configure
sudo python3 scripts/measure-job.py --json build/metrics/linux-build.json -- scripts/build-linux.sh --build
sudo scripts/build-linux.sh --package
```

### Phiên bản

Phiên bản sản phẩm HST Office nằm ở **một tệp duy nhất**: [`VERSION`](VERSION) (hiện `1.0.0`). Muốn phát hành `1.0.1` chỉ sửa tệp này rồi build lại: `scripts/write-hst-version.py` sinh `include/hst_version.h` (About, `soffice --version`), `scripts/build-linux.sh` truyền `HST_VERSION_*` cho tên gói/thư mục cài (`hst-office1.0*`, `/opt/hst-office1.0`) và tên tệp tải `HSTOffice_1.0.0_*`. Phiên bản lõi LibreOffice (26.8.1.1) **giữ nguyên bên trong** (tương thích extension, metadata tài liệu, PDF) và chỉ hiện trong "Sao chép thông tin phiên bản" (dòng `Engine:`), không hiện trên mặt About.

Chi tiết: [docs/UPSTREAM_BASELINE.md](docs/UPSTREAM_BASELINE.md), [docs/BUILD_MATRIX.md](docs/BUILD_MATRIX.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Giấy phép & ghi nhận

HST Office dựa trên LibreOffice (MPL-2.0) của The Document Foundation; mã HST mới theo [AGPL-3.0](LICENSE); mẫu văn bản CC BY 4.0. Xem [NOTICE.md](NOTICE.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).

## Liên hệ

HASON TECH — 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, TP. Đà Nẵng · <https://hasontech.vn> · 0236 3.507.507 · lienhe@hasontech.vn
