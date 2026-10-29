# Đo độ trễ menu chuột phải (context menu)

Trạng thái: bộ công cụ đo đã viết; **chưa có số liệu từ máy Mac của chủ sở hữu** (không có Mac ở môi trường phát triển). Mọi kết luận về nguyên nhân trên macOS là giả thuyết cho đến khi có kết quả `sample` thật. Phân tích mã nguồn và các giả thuyết xếp hạng nằm trong `plans/reports/opus-04-261029-1342-context-menu-latency.md`.

## 1. Hướng dẫn chạy trên Mac (Apple Silicon)

Mục tiêu: đo thời gian từ lúc nhấn chuột phải đến lúc cửa sổ menu xuất hiện, cho Writer, Calc và Impress, và ghi lại `sample` (ảnh chụp ngăn xếp) để biết máy đang bận gì.

### 1.1. Chuẩn bị

1. Cài công cụ dòng lệnh của Xcode (một lần): `xcode-select --install`. Cần `swiftc` và `python3`.
2. Sao chép thư mục `scripts/perf/` của dự án về Mac (giữ nguyên cấu trúc thư mục), rồi mở Terminal tại thư mục gốc dự án.
3. Biên dịch công cụ Swift:

```bash
mkdir -p build/tools
swiftc -swift-version 5 scripts/perf/macos-context-menu.swift -framework AppKit -framework ApplicationServices -o build/tools/macos-context-menu
```

Nếu `swiftc` báo lỗi, gửi nguyên văn thông báo lỗi cho nhóm phát triển (file Swift chưa từng được biên dịch trên Mac trước đây).

### 1.2. Quyền cần cấp (System Settings > Privacy & Security)

| Quyền | Khi nào cần | Ghi chú |
|---|---|---|
| Accessibility cho **Terminal** (hoặc iTerm) | Chế độ tự động (mặc định), vì công cụ tự phát sự kiện chuột/bàn phím bằng `CGEvent.post` | Cần theo tài liệu của các công cụ tương tự (ví dụ cliclick); chưa kiểm chứng trên máy dự án. Sau khi bật, **thoát hẳn và mở lại Terminal**. Công cụ tự kiểm tra `AXIsProcessTrusted()` và dừng với thông báo rõ nếu thiếu |
| Input Monitoring cho Terminal | Chế độ thủ công `--manual` (chỉ lắng nghe chuột thật của bạn) | Không phát sự kiện nào |
| Screen Recording | **Không cần** | Công cụ chỉ đọc chủ sở hữu, tầng (layer) và kích thước cửa sổ từ `CGWindowListCopyWindowInfo`; không đọc tên cửa sổ, không chụp màn hình. Nếu macOS vẫn hỏi, chọn Không cho phép và báo lại |

Công cụ **không** dùng API Accessibility (AX) để phát hiện menu, vì AX có thể làm thay đổi hành vi của chính menu đang đo.

### 1.3. Chạy

Thay đường dẫn ứng dụng cho đúng (bản đang bị chậm, ví dụ `/Applications/LibreOffice.app`). Không chạm vào chuột và bàn phím trong lúc chạy (khoảng 10-15 phút); để Mac cắm điện.

```bash
python3 scripts/perf/run-context-menu.py --platform macos \
  --app "/Applications/LibreOffice.app" \
  --preset owner-quick --sample \
  --output tests/output/perf/macos-owner
```

Lệnh dùng hồ sơ (profile) LibreOffice **mới** cho mỗi lần chạy nên không đụng đến cấu hình hiện có của bạn; với các ô `profile=user`, nó chỉ **sao chép** `~/Library/Application Support/LibreOffice/4` sang thư mục tạm. Tài liệu mẫu được sinh tự động (văn bản giả, không có dữ liệu riêng tư).

Xem trước danh sách ô sẽ chạy: thêm `--dry-run`. Chỉ chạy một phần: `--only writer`.

### 1.4. Nếu chế độ tự động không chạy được: chế độ thủ công

Mở một tài liệu LibreOffice bất kỳ, rồi:

```bash
build/tools/macos-context-menu --manual --pid "$(pgrep -x soffice | head -1)" --trials 20 --out manual-writer.json
```

Nhấn chuột phải (hoặc Control+nhấn) 20 lần trong cửa sổ tài liệu; nhấn Esc để đóng menu sau mỗi lần. Mỗi lần được đo từ lúc sự kiện chuột xuống (qua event tap chỉ-nghe) đến lúc cửa sổ menu xuất hiện.

### 1.5. Chụp `sample` thủ công (giá trị cao nhất)

Trong lúc bạn thấy menu bị trễ, ở Terminal khác chạy (5 giây) rồi nhấn chuột phải vài lần:

```bash
sample "$(pgrep -x soffice | head -1)" 5 1 -file ~/Desktop/lo-sample.txt
```

### 1.6. Gửi kết quả

```bash
ditto -c -k --sequesterRsrc tests/output/perf/macos-owner macos-owner.zip
```

Gửi `macos-owner.zip` (chứa `env.json`, các file `*.json` từng ô, `*.sample.txt`) cùng các câu trả lời: phiên bản macOS và chip, phiên bản LibreOffice, trễ xảy ra ở lần nhấn đầu hay mọi lần, có dùng trackpad hay chuột, và các ứng dụng đang chạy (VoiceOver, quản lý cửa sổ, quản lý clipboard, công cụ gõ tắt). Để so sánh A/B, nên chạy lại một lần sau khi thoát các ứng dụng đó.

### 1.7. Phân tích

```bash
python3 scripts/perf/analyze-context-menu.py --candidate tests/output/perf/macos-owner --summary-only
```

In trung vị, p90, p95, lớn nhất và số lần quá hạn cho từng ô, kèm các khung hàm đứng đầu trong `sample` và các nghi phạm đã biết.

## 2. Ma trận kiểm thử

Tệp `scripts/perf/context-menu-matrix.json`: module (writer, calc, impress) x hồ sơ (clean, user) x tự kiểm tra chính tả (on, off) x `SAL_SKIA` (default, raster) x khởi động (warm, cold). Preset `owner-quick` chạy cơ sở rồi đổi từng trục một; `full` chạy toàn bộ tích Descartes; `linux-parity` dùng cho Linux.

- cold: mỗi lần đo là một tiến trình mới, chỉ đo menu đầu tiên (không phải "nguội theo nghĩa bộ nhớ đệm hệ điều hành").
- warm: một tiến trình, một lần đo bỏ đi (khởi động), sau đó N lần.
- Mục tiêu tạm thời của sản phẩm (không phải số đã đo): warm p95 ≤ 150 ms, cold p95 ≤ 400 ms, không có quá hạn 5 giây; coi là hồi quy khi vượt cả 10% và 20 ms so với mốc cơ sở.

## 3. Hạn chế của phép đo

- Cửa sổ menu xuất hiện trong danh sách cửa sổ của hệ thống không đảm bảo các điểm ảnh đã được vẽ xong; đây là cận dưới của độ trễ nhìn thấy.
- Sự kiện giả lập bỏ qua nhận dạng cử chỉ trackpad; chế độ `--manual` đo sự kiện thật. Độ phân giải thăm dò khoảng 2-5 ms.
- Đo `sample` có tốn thêm tài nguyên nên được chạy ở lượt riêng, không nằm trong số liệu thời gian.
- Xvfb (Linux) không có compositor và đồ họa thật, nên Linux chỉ cho biết hồi quy/so sánh tương đối, không chứng minh lỗi trên macOS đã được sửa.

## 4. Bộ đo Linux (đối chiếu)

```bash
python3 scripts/perf/run-context-menu.py --platform linux --app /usr/lib/libreoffice/program/soffice \
  --preset linux-parity --start-xvfb --display :98 --output tests/output/perf/linux-system-24.2
python3 scripts/perf/analyze-context-menu.py --candidate tests/output/perf/linux-system-24.2 --summary-only
```

Dùng XTest để nhấn chuột phải và thăm dò cửa sổ gốc mới xuất hiện (ctypes + libX11). `--start-xvfb` thất bại nếu màn hình đã tồn tại (không tự tăng số). Xem kết quả đã chạy ở mục 5.

## 5. Kết quả đã chạy

Kiểm chứng bộ đo trên Linux (LibreOffice 24.2.7 của hệ thống, bổ sung mô-đun Calc/Impress trong thư mục tạm, plugin VCL `gen`, Xvfb :98, 20 lần warm / 5 lần cold, đơn vị ms). Đây chỉ chứng minh bộ đo hoạt động, **không** phản ánh macOS hay bản 26.8:

| Ô | n | trung vị | p95 | lớn nhất |
|---|---|---|---|---|
| writer warm | 20 | 15.9 | 37.2 | 40.0 |
| calc warm | 20 | 13.8 | 34.8 | 45.6 |
| impress warm | 20 | 19.4 | 32.7 | 52.7 |
| writer cold | 5 | 37.9 | 75.4 | 75.4 |
| calc cold | 5 | 41.0 | 56.4 | 56.4 |
| impress cold | 5 | 335.8 | 402.4 | 402.4 |

Dữ liệu thô: `tests/output/perf/linux-system-24.2/`; phân tích chi tiết trong `plans/reports/opus-04-261029-1342-context-menu-latency.md`. Số liệu Mac: **CHƯA CÓ** (bị chặn, cần máy của chủ sở hữu).
