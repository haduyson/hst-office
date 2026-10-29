# Build matrix

| Artifact | Nơi build | Công cụ | Tài nguyên đo | Trạng thái |
|---|---|---|---|---|
| 4 plugin `.plugin` | VPS dev, GitHub `ubuntu-latest` | Node 22 (esbuild), Python 3.12 zipfile | **chưa đo** — đo bằng `scripts/measure-job.py`, ghi trong [CI](CI.md) | Làm vòng này |
| 18 mẫu DOCX/XLSX/PPTX + template pack | VPS dev, GitHub `ubuntu-latest` | Python 3.12 + python-docx/openpyxl/python-pptx (lock hash) | như trên | Làm vòng này |
| Runtime QA Linux | VPS dev (Xvfb) | Desktop v10.0.0 binary chính thức, CDP | ~1.2 GB giải nén, RSS editor ghi trong report QA | Làm vòng này |
| Installer HST Linux/Windows/macOS | — | build_tools upstream | build_tools yêu cầu ~100 GB SSD | **BLOCKED** (legal + runner) |
| Engine `core/sdkjs/web-apps` | — | build_tools | như trên | Không làm; dùng binary chính thức |

## Ràng buộc đĩa

- Máy dev trống ~56 GB (2026-10-29). Ngưỡng cảnh báo **10 GiB**: script nặng gọi `measure-job.py --min-free-gib 10` và dừng nếu thấp hơn.
- Upstream binary chỉ một bản trong `upstream/cache/` (gitignored). Không clone toàn bộ engine.
- Không `rm -rf` ngoài `dist/`, `build/`, `tests/output/` do chính script tạo.

## Lệnh full engine build

Chưa ghi lệnh: chưa đọc và thử README build_tools tại commit pin trên runner đủ lớn → **BLOCKED** (`OPS-01`). Không suy diễn lệnh.
