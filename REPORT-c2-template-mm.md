# Báo cáo c2-template-mm

**Trạng thái: bị chặn; chưa sửa hoặc xác nhận ba sai lệch bố cục.** Môi trường không cho mở `/dev/null` để ghi và không cho tạo socket cục bộ. Xvfb và các bộ kiểm tra trên ứng dụng không khởi động được. Không có kết quả toàn bộ mẫu đạt trên ứng dụng.

## Thay đổi

Chỉ thêm báo cáo này trong phần nguồn của worktree; không sửa mã sản phẩm, tài nguyên mẫu, dung sai, `requirements.json`, `nd30_party.py`, `nd30_page.py`, danh sách hoặc tệp bản vá. Không tạo commit. Mẫu sinh thử nằm dưới `/tmp/codex-c2-template-mm/templates`; kết quả kiểm tra bị chặn nằm dưới `tests/output/c2-template-mm/`.

## Bằng chứng và phạm vi cần giải quyết

- Đã đọc hai báo cáo được giao, đặc biệt mục “Final RC”, tài liệu `docs/TEMPLATES.md`, bộ sinh và ba bộ kiểm tra liên quan.
- **20,61 mm:** `template_layout_measure.py:38` đo đỉnh hộp chữ PDF, không đo trực tiếp khung thân trang. Bộ sinh `writer_styles.py:114` và `nd30_page.py:49` đều cấu hình lề trên 10 mm cộng dải đầu trang 10 mm. Cần đo lại hộp chữ và khung trang trên cùng tài liệu trước khi chọn cách sửa; chưa chứng minh nguyên nhân của phần lệch 0,61 mm.
- **282,7 mm:** bộ đo `template_layout_measure.py:33–41` tính mọi chữ ngoài số trang vào thân trang, bao gồm dòng liên hệ. Trong khi đó, `templates_multipage_measure.py:70–73` loại dòng liên hệ ở chân trang đầu khỏi phép đo thân trang. Bộ sinh đặt dòng này trong dải chân trang 10 mm thuộc lề dưới, đúng quyết định đã ghi trong báo cáo rà soát. Đây là khác biệt có thật giữa hai phép đo, chưa phải bằng chứng rằng thân văn bản tràn lề. Nếu chọn thay đổi hình học chân trang của cả mẫu và trình hướng dẫn, phần tương ứng thuộc `nd30_page.py:53–55`, nằm ngoài quyền sửa của tác vụ này.
- **Bản ODT danh mục hồ sơ lệch 1,3 mm:** chưa tái hiện được. Bộ kiểm tra nhiều trang dừng trước khi sinh tài liệu vì `/dev/null` bị từ chối. Không sửa phỏng đoán hoặc thay ngưỡng so sánh.

## Các lệnh kiểm chứng đã chạy

Các lệnh dưới đây chạy từ `/home/wt-codex-c2-template-mm`.

```bash
git status --short
```

Thoát 128: không mở được `/dev/null` để đọc và ghi; không kiểm tra được trạng thái bằng Git.

```bash
mkdir -p /tmp/codex-c2-template-mm && cp -a /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir /tmp/codex-c2-template-mm/instdir
timeout 10s Xvfb :160 -screen 0 2400x1200x24 -nolisten tcp > /tmp/codex-c2-template-mm/xvfb.log 2>&1
```

Sao chép thoát 1 vì không giữ được chủ sở hữu (`Invalid argument`); thư mục đích đã được tạo nhưng không coi đây là bản sao đã kiểm chứng. Xvfb thoát 1 vì không tạo được socket lắng nghe. Nhật ký nằm tại đường dẫn trong lệnh.

```bash
SOURCE_DATE_EPOCH=1767225600 PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate-templates.py --out /tmp/codex-c2-template-mm/templates
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-templates.py /tmp/codex-c2-template-mm/templates --rebuild-check
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_templates_multipage.py -v
```

Sinh 84 mẫu thành công, thoát 0. Kiểm tra cấu trúc đủ 84 mẫu đạt, tái sinh giống từng byte, thoát 0. Kiểm tra đơn vị thoát 1: 5 phép kiểm tra `PortableBlocks` đạt; `GeneratedTemplates.setUpClass` lỗi `PermissionError` khi mở `/dev/null`, nên các phép kiểm tra của lớp đó chưa chạy.

```bash
DISPLAY=:160 PYTHONDONTWRITEBYTECODE=1 python3 tests/runtime/check-templates.py --soffice /tmp/codex-c2-template-mm/instdir/program/soffice --catalog /tmp/codex-c2-template-mm/templates/manifest.json --output tests/output/c2-template-mm
DISPLAY=:160 PYTHONDONTWRITEBYTECODE=1 python3 tests/runtime/check-template-layout.py --templates /tmp/codex-c2-template-mm/templates --instdir /tmp/codex-c2-template-mm/instdir --out /tmp/codex-c2-template-mm/layout --port 22160 --only cong-van,danh-muc-ho-so
DISPLAY=:160 PYTHONDONTWRITEBYTECODE=1 python3 tests/runtime/check-templates-multipage.py --instdir /tmp/codex-c2-template-mm/instdir --out /tmp/codex-c2-template-mm/multipage --only danh-muc-ho-so --pages 1 2 3 5 --no-sweep
```

Bộ kiểm tra mẫu thoát 2, trạng thái `BLOCKED`, do `AF_UNIX bind/listen` bị từ chối; báo cáo: `tests/output/c2-template-mm/run-jt2xvhgd/runtime.json`. Hai lệnh sau thoát 1 do `/dev/null` bị từ chối trước khi ứng dụng khởi động. Chưa có số đo PDF/ODT mới.

```bash
ps -eo pid,ppid,comm
```

Sau các lệnh kiểm tra, không còn tiến trình nền do tác vụ khởi chạy; Xvfb đã thoát và không có tiến trình ứng dụng đang chạy trong phiên. Không xây dựng cây nguồn dùng chung.

## Phần còn mở

Cần môi trường cho phép thiết bị chuẩn và socket cục bộ để tái hiện, sửa và chạy lại đủ bộ kiểm tra. Cần làm rõ phép đo đáy Công văn đối với dòng liên hệ ở chân trang đầu trước khi thay đổi bố cục đã được duyệt. Nếu cần sửa hình học trang dùng chung, phải chuyển phần đó cho luồng sở hữu `nd30_page.py`.
