# Kết quả c1-stale-tests

Đã sửa sáu giả định lỗi thời trong tám tệp kiểm thử/hỗ trợ kiểm thử. Chưa commit. Phần kiểm tra tĩnh đạt; **chưa xác nhận runtime đạt** vì sandbox chặn socket, chuyển nhóm người dùng và ghi `/dev/null`. Không sửa mã sản phẩm, danh sách bản vá hoặc tệp bản vá đã commit.

| Bài thử và tệp thay đổi | Giả định cũ, bằng chứng và sửa đổi |
|---|---|
| `tests/runtime/check-feature-search.py`, `feature_search_gui.py` | Giả định nhóm Trang đầu luôn thu gọn; riêng Slides còn dùng kiểm tra XML thay cho nút đang hiển thị. Các `notebookbar.ui` trong bộ cài đặt nút `Home-HstFeatureSearch` trong `gdHomeHstTools`; đối chiếu bản vá `hst-ribbon-home-fit.patch`. Nay tìm đúng nút qua AT-SPI và bấm mở hộp tìm kiếm ở cả ba ứng dụng, cả hai ngôn ngữ. Giữ các kiểm tra tìm kiếm, phím tắt và gửi lệnh NĐ 30. |
| `tests/runtime/check-nd30-entry.py`, `nd30_entry_gui.py` | Giả định vị trí nút trong hàng cuối của popup cũ. Nút `Home-HstNd30Wizard` hiện nằm trong `bxHomeHstToolsNd30`, thuộc nhóm Công cụ. Nay tìm nút đang hiển thị, bấm theo tọa độ trợ năng, vẫn yêu cầu mở đúng trình hướng dẫn. Khung đánh dấu ảnh dùng cùng tọa độ thực. Xóa các helper chỉ phục vụ bố cục cũ. |
| `tests/runtime/check-vi-intro.py` | Khẩu hiệu cũ là “Trợ lý số cá nhân của người Việt”. `data/hst/solutions.json`, bảng `aHstSolutions` của `backingwindow.cxx` và bộ cài đều dùng “Trợ lý AI cá nhân, như một trợ lý thực thụ”. Cập nhật đúng chuỗi UTF-16 cần tìm trong binary. |
| `tests/fixtures/vietnamese/runtime/scenarios_registration.py` | Giả định 12 mục gồm 11 lệnh và một menu con. `Addons.xcu` nguồn và bản cài có 13 mục, thêm “Tiện ích tiếng Việt”. Vẫn kiểm đủ 11 URL theo thứ tự; yêu cầu đúng hai menu con có nội dung và tên “Ngôn ngữ giao diện”, “Tiện ích tiếng Việt”. Đây là helper của `check-extensions.py`. |
| `scripts/templates/runtime_checks.py` | `_workbook` yêu cầu `Print_Area` cho mọi bảng. `sheets_register.py:39` chủ ý bỏ vùng in cố định; cả năm `.ots` đã cài không có vùng này và có hai hàng tiêu đề lặp. Nay sổ đăng ký phải **không có** `Print_Area`; bảng thông thường vẫn phải có; mọi bảng vẫn phải có `Print_Titles`. Giữ kiểm tra tiêu đề cột, bìa, A4, hướng giấy, công thức và ngăn cố định. Đây là helper của `check-templates.py`. |
| `tests/runtime/check_ribbon_banner_extra.py` | Bài thử thay ảnh AIOS nhưng so tên và URL với `catalogue[0]`, hiện là HASON TECH. `HstRibbonBanner.cxx::fromBundled` sắp theo `(order, id)` và lấy tên/URL theo mục đang vẽ; AIOS hiện ở vị trí 1. Nay chọn mục bằng `id == "aios"`; giữ kiểm tra ảnh 2000×600, tỷ lệ, kích thước ô, tên trợ năng và URL có UTM. |

Bằng chứng ban đầu: [báo cáo RC, mục Final RC](/home/office/plans/reports/release-261106-0025-beta5-rc.md:207), [báo cáo tiện ích tiếng Việt](/home/office/plans/reports/fullstack-developer-261106-1134-vietnamese-utilities.md:31). Các giả định trên đều có bằng chứng từ nguồn hoặc bộ cài; chưa phát hiện bằng chứng lỗi sản phẩm mới trong phạm vi này.

Các lệnh kiểm chứng đã chạy từ worktree:

```sh
cp -a /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir /tmp/codex-c1-stale-tests/instdir
cp -a --no-preserve=ownership /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir/. /tmp/codex-c1-stale-tests/instdir/
timeout 8s Xvfb :160 -screen 0 2400x1200x24 -nolisten tcp -ac -noreset
python3 tests/runtime/check-vi-intro.py --instdir /tmp/codex-c1-stale-tests/instdir --out /tmp/codex-c1-stale-tests/vi-intro-before --shots /tmp/codex-c1-stale-tests/vi-intro-before/shots --no-gui
python3 tests/runtime/check-vi-intro.py --instdir /tmp/codex-c1-stale-tests/instdir --out /tmp/codex-c1-stale-tests/vi-intro-after --shots /tmp/codex-c1-stale-tests/vi-intro-after/shots --no-gui
python3 -m unittest discover -s tests/unit -p test_hst_menu_order.py -v
python3 -m unittest discover -s tests/unit -p test_ribbon_home_tools.py -v
python3 /tmp/codex-c1-stale-tests/check-installed-contracts.py
python3 /tmp/codex-c1-stale-tests/check-syntax.py
python3 /tmp/codex-c1-stale-tests/run-runtime-checks.py
python3 tests/runtime/check-templates.py --soffice /tmp/codex-c1-stale-tests/instdir/program/soffice --catalog /home/office/dist/templates/manifest.json --output /home/wt-codex-c1-stale-tests/tests/output/c1-templates --only so-van-ban-di so-gui-buu-dien so-su-dung-ban-luu so-van-ban-den so-theo-doi-giai-quyet
```

- Lần `cp -a` đầu trả 1 do không bảo toàn được chủ sở hữu trong sandbox; lần dùng `--no-preserve=ownership` trả 0. Chỉ dùng bản sao riêng; không build cây dùng chung.
- Xvfb trả 1: không tạo được socket lắng nghe. Kiểm tra riêng cả AF_UNIX và AF_INET đều nhận `Operation not permitted`; không có display `:160` chạy sẵn.
- `vi-intro --no-gui`: trước sửa đạt 8/9, sau sửa đạt 9/9 (mã thoát 0). Đây là kiểm tra binary/tài nguyên, không phải xác nhận GUI.
- Hai bộ unit đạt lần lượt 3/3 và 5/5. Kiểm tra cấu trúc bộ cài đạt 10/10; kiểm tra cú pháp và khoảng trắng đạt 8/8 tệp. Đã tự rà soát diff với quy tắc `ak-code-review`.
- Wrapper runtime đã thử đủ sáu lệnh; [JSON nhật ký](/tmp/codex-c1-stale-tests/runtime-attempts.json) lưu nguyên văn lệnh, PID, worktree, mã thoát và đường dẫn log. `feature-search`, `nd30-entry`, `ribbon-banner` trả 1 vì `runuser` không đổi được nhóm. GUI `vi-intro` lỗi `chown`, được dừng sau giới hạn 18 giây. `extensions` dừng trước khi chạy kịch bản do `/dev/null` bị từ chối. `templates` trả 2 do socket; lệnh cuối ở trên đã thử lại với đúng năm ID sổ và vẫn trả 2. Không có kết quả runtime nào được ghi nhận là đạt.
- Bài `extensions` đã gỡ phần mở rộng thử nghiệm trong bản sao; sau đó khôi phục phần mở rộng gốc bằng `cp -a --no-preserve=ownership /tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/rc-inst/instdir/share/extensions/hst-vietnamese-tools /tmp/codex-c1-stale-tests/instdir/share/extensions/`. Không còn tiến trình do công việc này khởi chạy. Git cũng bị chặn bởi `/dev/null`; diff được đối chiếu với bản sao trước sửa tại `/tmp/codex-c1-stale-tests/changes.diff`.

Còn mở: coordinator cần chạy lại sáu bài trên bản sao bộ cài với Xvfb riêng, trong môi trường cho phép socket và tài khoản chạy kiểm thử. Chưa thể kết luận các bài GUI, đăng ký phần mở rộng hoặc xuất XLSX đạt trên runtime mới.
