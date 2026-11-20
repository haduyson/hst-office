# Báo cáo c3-branding

Đã giảm **2.974 → 1.740 lượt khớp** trên cùng **2.552 tệp** trong bản sao bộ cài. Loại bỏ 1.234 báo động giả: 64 dòng trong giấy phép/thông báo, 669 dòng chú thích bản quyền và 501 khai báo DTD. Kiểm tra vẫn trả mã **1** vì còn mục cần rà soát; đây chưa phải bộ cài sạch thương hiệu.

Các thay đổi chưa commit trên nhánh `codex/c3-branding`:

- [branding/brand-audit-allowlist.json](branding/brand-audit-allowlist.json): thêm tên tệp pháp lý ngay gốc, thư mục `license/` ngay gốc và tên giấy phép viết thường. Thêm regex neo cả hai đầu cho dòng bản quyền XML, launcher, tài nguyên trình hướng dẫn và ba loại khai báo DTD đứng riêng. Mỗi mẫu mới có lý do riêng trong `reason`. Bỏ ngoại lệ trang trợ giúp vì kiểm thử chứng minh nó che mất nội dung giao diện.
- [tests/brand/test-check-branding.py](tests/brand/test-check-branding.py): thêm ba nhóm kiểm thử cho đường dẫn pháp lý, ngoại lệ theo dòng và nội dung giao diện vẫn phải bị phát hiện, kể cả cùng dòng với DTD, trong hộp thoại giấy phép, trợ giúp, bản dịch và thư mục SDK/header/DTD. Các header `.h`/`.hxx`, tệp `.dtd` và công cụ SDK nhị phân vốn không được quét; không thêm ngoại lệ cho cả thư mục.
- [tests/runtime/check-digital-signature.py](tests/runtime/check-digital-signature.py): đổi đúng hai docstring từ “Tập tin” sang “Tệp tin”.
- [docs/BRAND.md](docs/BRAND.md), [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md): cập nhật phạm vi ngoại lệ và giới hạn kiểm tra.
- Báo cáo này ghi kết quả bàn giao. Không sửa mã sản phẩm, danh sách bản vá hoặc tệp `.patch`.

Các lệnh xác minh, chạy từ gốc worktree:

| Lệnh | Kết quả |
|---|---|
| `python3 tests/brand/test-check-branding.py -v` | Ban đầu 10/10 đạt; thêm kiểm thử trước sửa cấu hình ghi nhận 7 thất bại, gồm ca trợ giúp bị bỏ sót; sau sửa 13/13 đạt. |
| `python3 -m unittest tests/unit/test_vi_terms.py -v` | 4/4 đạt cả trước và sau sửa. |
| `python3 tests/brand/test-brand-assets.py -v` | 17/17 đạt; có cảnh báo `ResourceWarning` về tệp chưa đóng trong kiểm thử hiện hữu. |
| `python3 tests/brand/test-hst-icon-theme.py -v` | 6/6 đạt. |
| `PYTHONPATH=tests/unit:. python3 -m unittest discover -s tests/unit -p 'test*.py' -v > /tmp/codex-c3-branding/unit.log 2>&1` | 718 ca trong 142,915 giây; mã 1, 165 thất bại, 59 lỗi, 4 ca bỏ qua. Số thất bại/lỗi gồm cả ca con. |
| `python3 scripts/check-branding.py --install-root /tmp/codex-c3-branding/instdir --max-report 0` | Chạy trước và sau sửa: tài nguyên đều đạt; 2.974 rồi 1.740 lượt khớp; cả hai trả mã 1. |
| `python3 scripts/check-doc-links.py docs/BRAND.md docs/RELEASE_CHECKLIST.md REPORT-c3-branding.md` | Liên kết cục bộ của cả ba tài liệu hợp lệ. |
| `python3 /tmp/codex-c3-branding/review-index.py` | Đối chiếu SHA-1 nội dung 2.173 tệp với Git index: chỉ năm tệp đã nêu thay đổi; mã sản phẩm và bản vá giữ nguyên. |

Chuẩn bị và đối chiếu bản sao:

```bash
mkdir /tmp/codex-c3-branding
cp -a /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir /tmp/codex-c3-branding/instdir
cp -a --no-preserve=ownership /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir/. /tmp/codex-c3-branding/instdir/ > /tmp/codex-c3-branding/copy.log 2>&1
diff -qr /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir /tmp/codex-c3-branding/instdir > /tmp/codex-c3-branding/copy-compare.log 2>&1
```

Lệnh `cp -a` đầu tiên trả mã 1 vì môi trường không cho giữ chủ sở hữu. Lần sao chép bỏ riêng thuộc tính đó và lệnh đối chiếu đều trả mã 0. Không build hoặc khởi chạy ứng dụng/Xvfb; mọi phiên lệnh đã kết thúc. Bản sao, cấu hình trước sửa (`allowlist-before.json`), danh sách lượt khớp trước/sau và nhật ký còn ở `/tmp/codex-c3-branding/` để đối chiếu.

Còn mở:

- 1.740 lượt khớp còn lại gồm chuỗi giao diện thật và định danh XML/metadata chưa được miễn trừ. Ví dụ vẫn bắt được liên kết trong hộp About, hai dòng trong hộp thoại giấy phép và 11 lượt khớp ở catalog `cui.mo`. Không miễn trừ cả README, mô tả phần mở rộng hoặc catalog dịch.
- Bộ kiểm thử đơn vị đầy đủ chưa đạt. Nhật ký ghi 40 khối lỗi liên quan `/dev/null`, 25 khối có `Operation not permitted` và 120 khối báo không có quyền ghi kho chứng thư; còn lỗi phụ thuộc/đầu ra thiếu và timeout. Các nhóm lỗi này cần được kiểm tra lại trong môi trường phù hợp; không sửa ngoài phạm vi công việc.
- `git status --short` và `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false status --short` đều bị chặn khi mở `/dev/null` (mã 128). Đã rà soát diff từ bản chụp trước sửa và đọc Git index để đối chiếu nội dung; chưa chạy được `git diff --check`.
