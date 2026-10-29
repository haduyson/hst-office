# Third-party notices

| Thành phần | Phiên bản / commit | Giấy phép | Dùng ở đâu | Văn bản license |
|---|---|---|---|---|
| ONLYOFFICE plugin SDK bridge (`plugins.js` — chỉ file này) | Desktop Editors v10.0.0 (10.0.0.169) binary; source `sdkjs@9d213886` | AGPL-3.0 + Additional Terms (Ascensio System SIA) | Đóng gói trong mỗi `.plugin` (`vendor/plugins.js`) | `third_party/onlyoffice-plugin-sdk/LICENSE.txt` → `LICENSE-ONLYOFFICE.txt` trong package |
| ONLYOFFICE Desktop Editors (runtime, không phân phối lại) | v10.0.0 | AGPL-3.0 + Additional Terms | Người dùng tự cài từ upstream | `LICENSES/upstream/desktopeditors/LICENSE` |
| esbuild (build-time) | xem `package-lock.json` | MIT | Bundle plugin, không đóng gói | npm package |
| python-docx, openpyxl, python-pptx, lxml (build-time) | xem `requirements-templates.lock` | MIT / MIT / MIT / BSD-3-Clause | Sinh mẫu, không đóng gói | PyPI |

Mẫu DOCX/XLSX/PPTX của HST không chứa font, ảnh hay nội dung của bên thứ ba.
