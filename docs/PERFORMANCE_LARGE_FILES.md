# Mở tệp lớn: bộ đo và các bản vá

Bộ đo thời gian mở tài liệu lớn (bảng tính, văn bản, tệp văn bản thuần) của một bản build HST Office, dùng
được với đầu ra của [hàng đợi build](BUILD_MATRIX.md#hàng-đợi-build-cục-bộ-agent-tự-dùng) trên máy Linux
và trên máy thử Windows (HST4, HST5). Mọi tệp thử đều là dữ liệu tổng hợp, không đọc tệp của người dùng.

## Chạy

```bash
# Linux: .deb của một job trong hàng đợi (hoặc đường dẫn .deb); không cài gì, chạy dưới Xvfb riêng (:73)
scripts/perf/large-file-open-local.sh linux <job-id|.deb> /data/hst-agents/<việc>/runs/after --label after
# Windows: MSI được bung thành ảnh quản trị (msiexec /a) trong D:\hst-test\large-open, chạy trong phiên SSH
scripts/perf/large-file-open-local.sh hst4 <job-id|.msi> /data/hst-agents/<việc>/runs/win-after \
  --label win-after --mode cli --cpus 4
```

- Tuỳ chọn chuyển cho [`large-file-open.py`](../scripts/perf/large-file-open.py): `--only a,b` (chỉ một số
  tệp), `--mode gui|cli|headless` (cửa sổ thường / mở như nhấp đúp / ẩn), `--seed spell` (bật kiểm tra chính tả
  tự động), `--seed norowheight|nothreads|toolbar|tabbed`, `--cpus N` (chỉ dùng N bộ xử lý logic, như máy 4 nhân),
  `--repeat N`, `--timeout S`, `--save` (đo thêm lưu lại và bản sao ODF của AutoRecovery), `--full-layout` (Writer:
  thời gian tới khi toàn bộ văn bản được dàn trang), `--probe S` (độ trễ một lệnh cần khoá chính trong S giây sau khi mở).
- Mở nhiều bảng tính cùng lúc trên Windows và đo thời gian cửa sổ "Not responding":
  [`large-file-open-multi.py`](../scripts/perf/large-file-open-multi.py) (chạy bằng Python của bản cài, trong phiên
  có màn hình: `remote.py hst5 ui ...`; phiên SSH không có cửa sổ hiển thị).
- Tệp thử: [`large_file_fixtures.py`](../scripts/perf/large_file_fixtures.py) ghi một lần vào
  `$LFO_FIXTURES` (mặc định `<out>/../fixtures`); `FIXTURE_ARGS="--rows 60000"` đổi kích thước.
- Kết quả: `<out>/<label>.jsonl` (mỗi lần mở một dòng: `load` = tải xong, `idle` = văn phòng rảnh sau đó,
  `peak_mb`, `office_exit` khi văn phòng thoát với mã lỗi, `error: timeout`) và `<out>/summary.md`
  ([`large-file-open-summary.py`](../scripts/perf/large-file-open-summary.py), nhiều nhãn trong một thư mục thì
  thành nhiều cột: trước/sau).
- Trên Windows phiên SSH không có màn hình: dùng `--mode headless` hoặc `cli`; không dùng phiên của Admin.
  `HST_REMOTE` trỏ tới `remote.py` của bộ thử máy Windows thật.

## Nguyên nhân đã tìm và bản vá (1.0.2)

| Bản vá | Triệu chứng | Nguyên nhân |
|---|---|---|
| `hst-calc-xlsx-shared-formula-results.patch` | `.xlsx` nhiều cột công thức kéo xuống (SUMIF, VLOOKUP…) mở rất lâu, máy 4 nhân như treo | Kết quả lưu sẵn của công thức dùng chung bị để "bẩn", bước tính chiều cao dòng cuối lúc nhập đọc mọi ô nên tính lại cả bảng |
| `hst-threadpool-no-timeout-abort.patch` | Sau 10 phút tính toán, HST Sheets tự thoát (Windows: mã 0xC0000409) | Bản phát hành ném ngoại lệ khi chờ nhóm luồng quá 10 phút, trong khi các luồng còn dùng dữ liệu của khung đang chờ; nay chờ tiếp và ghi cảnh báo |
| `hst-calc-pattern-registry-hash-index.patch` | Bảng tính có hàng nghìn định dạng ô mở mất vài phút | Mỗi lần đăng ký định dạng quét tuyến tính mọi định dạng cùng kiểu ô; nay tra bằng chỉ mục băm |
| `hst-writer-layout-nexts-only-with-objects.patch` | Tệp `.txt` 50 MB tải xong nhưng văn phòng bận 100 % CPU hơn 15 phút ("mở mãi không xong") | Lần dàn trang đầu gom mọi đoạn phía sau cho từng đoạn (bậc hai theo số đoạn); nay chỉ gom khi trang có đối tượng neo |

Còn lại (gốc LibreOffice, chưa sửa): tệp văn bản thuần rất lớn không có bộ nhớ đệm dàn trang, nên mọi đoạn ban đầu
nằm ở trang 1 và mỗi lần chuyển phần còn lại sang trang sau tốn thời gian tỉ lệ với số đoạn còn lại. Văn bản 50 MB
(~550 000 đoạn, ~11 500 trang) vẫn cần khoảng 20 phút để dàn trang hết trên máy chủ Linux (trước bản vá: hơn 25 phút
chưa xong); tệp 10 MB từ 190 s xuống 61 s.

Kiểm thử: `tests/unit/test_large_file_open_patches.py`, `tests/unit/test_large_file_open_harness.py`; các
CppunitTest `sc_subsequent_filters_test5` (`testXlsxSharedFormulaCachedResults`) và `sc_ucalc`
(`testCellAttributeRegistryManyFormats`) nằm trong chính bản vá.
