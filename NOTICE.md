# NOTICE — HST Office

Copyright (C) 2026 Công ty TNHH Công nghệ Hà Sơn (HASON TECH).

- **Mã nguồn mới** của HST Office (plugin, script, generator): GNU Affero General Public License v3.0 — xem `LICENSE`.
- **Nội dung mẫu văn bản** (dữ liệu nguồn `templates/*.json` và file DOCX/XLSX/PPTX sinh ra): Creative Commons Attribution 4.0 International (CC BY 4.0), <https://creativecommons.org/licenses/by/4.0/legalcode>.

## Nguồn mở & ghi nhận tác giả

- HST Office chạy trên **ONLYOFFICE Desktop Editors** — phần mềm gốc của **Ascensio System SIA** (<https://www.onlyoffice.com>), phát hành theo AGPLv3 kèm Additional Terms. Phiên bản kiểm thử: v10.0.0 (commit `daf8c6948148827201b2907ac1134d222fbfa7b4`).
- HST Office **không sửa đổi** engine ONLYOFFICE ở vòng phát hành này; ứng dụng người dùng chạy là bản ONLYOFFICE chính thức.
- Mỗi plugin đóng gói kèm bridge SDK `plugins.js` lấy nguyên văn, không sửa, từ ONLYOFFICE Desktop Editors v10.0.0 (header bản quyền Ascensio System SIA, AGPLv3 + Additional Terms — văn bản đầy đủ trong `LICENSE-ONLYOFFICE.txt` của mỗi package). Source upstream liên quan: `ONLYOFFICE/sdkjs@9d2138866d929be32f1d107e8b5bfae36156e097`, thư mục `common/plugins/` (file ship là bản minified; ánh xạ build chính xác **chưa được tái tạo/xác minh** — xem `third_party/onlyoffice-plugin-sdk/provenance.json`).
- ONLYOFFICE là thương hiệu của Ascensio System SIA. HST Office không được cấp quyền thương hiệu và không dùng logo ONLYOFFICE.

## Thương hiệu HST Office

Tên “HST Office” và logo HASON TECH thuộc HASON TECH; asset logo do chủ dự án cung cấp (`assets/brand/source/`). Giấy phép AGPL không cấp quyền sử dụng thương hiệu HASON TECH.

## Nhận mã nguồn

Mã nguồn HST Office: <https://github.com/haduyson/hst-office>. Mỗi `.plugin` do `scripts/build-plugins.js` tạo ghi commit SHA trong `build-info.json`. Manifest artifact CI (`artifact-manifest.json`) đang được triển khai; chưa có bản phát hành chính thức.
