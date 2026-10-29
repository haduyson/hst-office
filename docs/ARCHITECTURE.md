# Kiến trúc HST Office (vòng plugin-first)

Quyết định nền: [ADR 0001](ADR/0001-plugin-first-unmodified-upstream.md). Contract chi tiết: [PLUGIN_CONTRACT](PLUGIN_CONTRACT.md).

```text
┌──────────────── ONLYOFFICE Desktop Editors v10.0.0 (nguyên bản, không sửa) ────────────────┐
│  Writer (word)            Sheets (cell)             Slides (slide)                           │
│     │ iframe plugin          │ iframe plugin           │ iframe plugin                         │
│  ┌──▼─────────────────┐  ┌───▼──────────────────┐  ┌───▼──────────────┐                      │
│  │ vn-admin-documents │  │ vn-spreadsheet-formats│  │ vn-templates     │ (cũng chạy ở word/cell)│
│  │ vn-encoding-tools  │  └──────────────────────┘  └──────────────────┘                      │
│  └────────────────────┘                                                                      │
│        ▲ Asc.plugin.callCommand / executeMethod (Office JS API, sandbox)                    │
└────────┼─────────────────────────────────────────────────────────────────────────────────────┘
         │ cài offline: Plugin Manager → .plugin (ZIP) hoặc thư mục user sdkjs-plugins/{GUID}
┌────────┴──────────────────────────── repo hst-office ───────────────────────────────────────┐
│ extensions/<plugin>/logic/*.js  ← logic thuần, test bằng node:test, không phụ thuộc Asc/DOM  │
│ extensions/<plugin>/*.js        ← UI + adapter gọi API editor                                 │
│ extensions/shared/              ← bridge UI chung, About/attribution                           │
│ vendor/onlyoffice/              ← SDK bridge v1 (nguyên văn từ binary v10, header AGPL)        │
│ templates/*.json → scripts/generate-*.py → dist/templates/*.docx|xlsx|pptx (tái tạo được)    │
│ scripts/build-plugins.js → dist/plugins/*.plugin (ZIP xác định, byte-identical)              │
│ scripts/runtime/ ← điều khiển Desktop thật qua CDP (Xvfb, user không phải root)              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Nguyên tắc

1. **Không sửa engine/binary upstream.** Mọi tính năng đi qua Plugin SDK; tính năng cần fs/DOM nội bộ → blocker, không hack.
2. **Logic tách khỏi editor.** Bảng mã TCVN3/VNI, parser CSV, dữ liệu NĐ30, định dạng VND/ngày là module ESM thuần, test được bằng `node --test`. Adapter editor mỏng.
3. **Một nguồn sự thật.** Dữ liệu NĐ30 và định dạng số dùng chung giữa plugin và generator mẫu (exporter JSON), không chép lại.
4. **Offline.** Plugin không tải gì từ mạng lúc chạy; bridge SDK, icon, About đóng gói trong từng `.plugin`.
5. **An toàn dữ liệu.** Preview trước khi ghi; Cancel không sửa; mỗi thao tác ghi là một bước Undo; lỗi/timeout báo trạng thái chưa xác định, không retry mù.
6. **Tái tạo được.** Build plugin và mẫu cho cùng SHA-256 khi chạy lại cùng toolchain.

## Lớp kiểm thử

| Lớp | Công cụ | Chứng minh |
|---|---|---|
| Unit | `node --test`, Python `unittest` | Logic thuần, cấu trúc OOXML |
| Package | `scripts/check-plugins.js` | ZIP root, GUID, translations, notices, offline |
| Runtime Linux | `scripts/runtime/*` + Desktop v10 thật qua CDP | Cài plugin, chèn/chuyển đổi, Undo, lưu, mở lại |
| Windows/macOS/MS Office | máy thật | **Chưa có máy** → NOT RUN/BLOCKED trong [COMPATIBILITY_MATRIX](COMPATIBILITY_MATRIX.md) |
