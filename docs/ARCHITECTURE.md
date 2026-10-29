# Kiến trúc HST Office

Quyết định nền: [ADR 0002](ADR/0002-libreoffice-standalone.md). Plan: [plans/261029-1234-hst-office-libreoffice-standalone](../plans/261029-1234-hst-office-libreoffice-standalone/plan.md).

```text
                    repo hst-office (git)                                   máy build Linux
┌──────────────────────────────────────────────────────────┐      ┌───────────────────────────────────────────┐
│ upstream/libreoffice-lock.json  (tarball + GPG + commit) │ ───► │ upstream/libreoffice/  (LibreOffice 26.8.1.1)│
│ build-config/linux-x86_64.conf  (configure options)      │ ───► │   + patches/libreoffice/series (MPL-2.0)    │
│ patches/libreoffice/*.patch     (About, defaults, menu)  │ ───► │   + --with-branding=build/branding-staging   │
│ branding/ + assets/brand/       (splash, About, icons)   │ ───► │   make build → instdir/ (HST Office)         │
│ config/*.xcu                    (Tabbed UI, vi, A4…)     │ ───► │   make → workdir/installation/*.deb          │
│ extensions/hst-vietnamese-tools (Python-UNO .oxt)        │ ───► │ bundled extension + templates + dict vi      │
│ templates/*.json → scripts/generate-templates.py → .ott/.ots/.otp                                   │
└──────────────────────────────────────────────────────────┘      └───────────────────────────────────────────┘
                                                                              │
                                    dist/linux/*.deb ── QA runtime (Xvfb, headless UNO) ── docs/qa-evidence/
```

## Lớp

| Lớp | Nội dung | Giấy phép |
|---|---|---|
| Engine | LibreOffice 26.8.1.1 không fork lịch sử; chỉ áp patch tối thiểu có ghi lý do | MPL-2.0 (file gốc) |
| Nhận diện | Tên `HST Office`, vendor `HASON TECH`, splash/About/Start Center/icon/desktop file | Asset HST (thương hiệu) |
| Cấu hình mặc định | Tabbed UI, giao diện vi-VN khi OS tiếng Việt, A4, Times New Roman, tắt update/donate TDF, không telemetry | HST |
| Tính năng Việt | Extension `hst-vietnamese-tools` (NĐ30, TCVN3/VNI→Unicode, VND/ngày/%, CSV UTF-8), 18 mẫu, từ điển `vi` | AGPL-3.0 / CC BY 4.0 / GPLv2 |
| Đóng gói | `.deb` từ hệ thống EPM upstream; Windows `.msi`/macOS `.dmg` sau (blocked) | — |

## Nguyên tắc

1. **Patch tối thiểu, có lý do.** Mỗi patch trong `patches/libreoffice/series` có header mô tả vấn đề, file upstream bị sửa và cách kiểm thử; ưu tiên tuỳ chọn configure và cấu hình `.xcu` trước khi sửa mã.
2. **Logic Việt tách khỏi UNO.** Module Python thuần test bằng `unittest`; lớp UNO mỏng.
3. **Một nguồn sự thật.** `data/vietnamese/*.json` dùng chung cho extension và generator mẫu.
4. **Bằng chứng trước khẳng định.** Mọi tuyên bố về hiệu năng/tương thích có số đo hoặc file evidence; macOS chưa có máy → BLOCKED.
5. **Tài nguyên có giới hạn.** Build chạy dưới `scripts/measure-job.py` (giữ ≥10 GiB trống, tự dừng ở 12 GiB).
