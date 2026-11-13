# HST Office

Bộ ứng dụng văn phòng miễn phí, offline cho người Việt: 
**HST Writer** (văn bản); 
**HST Sheets** (bảng tính); 
**HST Slides** (trình chiếu); 
Do Công ty TNHH Công nghệ Hà Sơn (**HASON TECH**) phát triển.

> **Bản chính thức: HST Office 1.0.1** cho Windows 10/11 64-bit (`.msi`), macOS Apple Silicon và Intel (`.dmg`), Ubuntu/Debian/Linux Mint 64-bit (`.deb`). Tải về tại <https://office.hasontech.vn/#tai-ve>; điểm mới: <https://office.hasontech.vn/diem-moi/#v1.0.1> ([ghi chú phát hành](docs/releases/v1.0.1.md)).

## Điểm khác so với LibreOffice gốc

- Nhận diện HST Office (splash, About, icon, launcher).
- Tiếng Việt: giao diện tiếng Việt mặc định trên mọi hệ điều hành (đổi tại Công cụ → Tùy chọn → Ngôn ngữ và Địa phương → Chung → Giao diện người dùng hoặc Xem lại → Ngôn ngữ giao diện; lựa chọn được giữ qua các bản cập nhật); từ điển chính tả `vi`; khổ A4 và Times New Roman mặc định; lưu mặc định `.docx`/`.xlsx`/`.pptx`; [phím tắt theo Microsoft Office](docs/SHORTCUTS-MSOFFICE.md).
- Công cụ tích hợp: soạn văn bản hành chính theo **NĐ 30/2020/NĐ-CP**, chuyển mã **TCVN3/VNI → Unicode**, định dạng **VND / dd/mm/yyyy / ngày … tháng … năm …**, **tiện ích tiếng Việt** (hàm DOCSO, DOCTIEN, BODAU, TACHHO, TACHTEN; đọc số thành chữ; bỏ dấu, tách họ tên, sắp xếp theo tên, xóa dòng trống), nhập **CSV UTF-8** an toàn, 84 mẫu (Tệp tin → Mẫu, các nhóm "HST — Văn bản hành chính / Văn bản quy phạm pháp luật / Văn bản của Đảng / Biểu mẫu văn thư / Bảng tính / Trình chiếu").
- Mở nhiều tài liệu dạng **thẻ** trong một cửa sổ: cửa sổ HST Office nhận mọi loại tài liệu; HST Writer, HST Sheets, HST Slides, HST PDF và tệp nhấp đúp từ trình quản lý tệp dùng cửa sổ riêng của từng ứng dụng (thành thẻ trong cửa sổ ứng dụng đó nếu đã có, khác loại sang cửa sổ ứng dụng của nó); nút đóng trên từng thẻ, nút "+" mở tài liệu mới, chuyển thẻ bằng Ctrl+Alt+. / Ctrl+Alt+, ; kéo thẻ ra ngoài (hoặc chuột phải / Xem → "Tách ra cửa sổ mới", Ctrl+Alt+Shift+N) để tách thành cửa sổ riêng; khôi phục sau sự cố giữ nguyên cửa sổ và thứ tự thẻ; nút đóng cửa sổ đóng mọi thẻ của cửa sổ đó (hỏi lưu từng tài liệu đã sửa); tắt tại Công cụ → Tùy chọn → HST Office → Chung → "Thẻ tài liệu".
- Khôi phục tài liệu: thông tin khôi phục được lưu 3 phút một lần, tài liệu lớn hơn 5 MB 10 phút một lần (không tự lưu đè tệp); **Phiên bản trước** (Tệp tin → Thông tin → Phiên bản trước) giữ các bản đã bị lưu đè trên máy để xem hoặc khôi phục ([docs/PREVIOUS_VERSIONS.md](docs/PREVIOUS_VERSIONS.md)).
- **Trích dẫn và tài liệu tham khảo** trong HST Writer (HST ▸ Trích dẫn): kiểu luận văn Việt Nam, APA 7, IEEE, Vancouver, AMA, Harvard, Chicago, MLA, ISO 690; danh mục tự đánh số, nhóm tiếng Việt trước, tác giả Việt xếp theo tên; chèn lại theo số (`[3` + Alt+Shift+I); thư viện trên máy, nhập/xuất RIS, BibTeX, CSL-JSON, EndNote, PubMed; khứ hồi .docx/.odt ([hướng dẫn](extensions/hst-vietnamese-tools/help/trich-dan.html)).
- Không theo dõi cách dùng, không cần tài khoản hay Internet. Kiểm tra cập nhật gửi kèm phiên bản và hệ điều hành ([docs/PRIVACY.md](docs/PRIVACY.md)). Báo cáo lỗi (Trợ giúp → Báo lỗi cho HASON TECH) chỉ được gửi khi người dùng bấm Gửi và xem trước được toàn bộ nội dung.
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

Phiên bản sản phẩm HST Office có hai nguồn: [`VERSION`](VERSION) (`MAJOR.MINOR.MICRO`, hiện `1.0.1`) và mã bản phát hành đầy đủ trong [`data/hst/release.json`](data/hst/release.json) (SemVer, hiện `1.0.1`; phần lõi phải bằng `VERSION`; hậu tố `-beta.N` đưa bản cài vào kênh cập nhật beta). Muốn phát hành bản mới (ví dụ `1.0.2`) sửa `VERSION` và `release.json` rồi build lại: `scripts/write-hst-version.py` sinh `include/hst_version.h` (About và `soffice --version` hiện mã bản phát hành đầy đủ; thuộc tính tệp Windows; số build đơn điệu `10000` cho bản chính thức, nhỏ hơn cho beta/rc), `scripts/build-linux.sh` truyền `HST_VERSION_*` cho tên gói/thư mục cài (`hst-office1.0*`, `/opt/hst-office1.0`). Tên tệp tải mang mã đầy đủ: `HSTOffice_1.0.1_Win_x86-64_en-US_vi.msi`, `HSTOffice_1.0.1_Linux_x86-64.deb`, `HSTOffice_1.0.1_macOS_arm64.dmg`, `HSTOffice_1.0.1_macOS_x86_64.dmg`; người dùng chỉ tải qua `https://office.hasontech.vn/tai/...`; chi tiết từng hệ điều hành ở [docs/BUILD_MATRIX.md](docs/BUILD_MATRIX.md#phiên-bản-hiển-thị-theo-hệ-điều-hành). Phiên bản lõi LibreOffice (26.8.1.1) **chỉ dùng bên trong** (tương thích extension, đường dẫn trợ giúp, nhận biết lần chạy đầu) và không hiện ở chỗ nào người dùng thấy: About và "Sao chép thông tin phiên bản", metadata tài liệu (`meta:generator`, `docProps/app.xml` `Application` = `HSTOffice/<release>$<OS>_<ARCH>`), PDF (Producer `HST Office <release>`, Creator `HST Writer`/`HST Sheets`/`HST Slides`), EPS, HTML (`hst-version-everywhere.patch`). Ngoại lệ có chủ đích: `AppVersion` của OOXML giữ giá trị tương thích `15.0000`; báo cáo lỗi (Trợ giúp ▸ Báo lỗi) gửi kèm phiên bản lõi, ghi rõ là "lõi xử lý"/`Engine:`. Kiểm tra: `tests/unit/test_hst_version_everywhere.py`, `tests/runtime/check-hst-version-everywhere.py`, `scripts/check-branding.py --release`.

Chi tiết: [docs/UPSTREAM_BASELINE.md](docs/UPSTREAM_BASELINE.md), [docs/BUILD_MATRIX.md](docs/BUILD_MATRIX.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Giấy phép & ghi nhận

HST Office dựa trên LibreOffice (MPL-2.0) của The Document Foundation; mã HST mới theo [AGPL-3.0](LICENSE); mẫu văn bản CC BY 4.0. Xem [NOTICE.md](NOTICE.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).

## Liên hệ

HASON TECH — 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, TP. Đà Nẵng · <https://hasontech.vn> · 0236 3.507.507 · lienhe@hasontech.vn
