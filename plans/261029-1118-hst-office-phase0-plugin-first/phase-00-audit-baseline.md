# 00 — Audit, baseline và legal

Status: pending. Owner: Claude audit. Dependencies: không. Priority: P0. Context: [brief §§0–3, 8–14](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md). Gói này chỉ docs/evidence, chưa viết tính năng.

## Requirements

Chọn A theo quyết định owner; trình bày B để ghi rõ chi phí/legal blocker, không mở lại lựa chọn. GitHub license metadata chỉ là chỉ báo: DesktopEditors/desktop-apps/core/sdkjs/web-apps/build_tools AGPL-3.0; sdkjs-plugins/document-templates Apache-2.0. Phải đọc LICENSE, NOTICE, headers/additional terms và asset/font licenses nguyên văn ở SHA cụ thể; không suy ra plugin mới tự động được cấp một license nào.

## Files tạo / ownership

- `docs/UPSTREAM_BASELINE.md`, `docs/LICENSE_AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_MATRIX.md`, `docs/BLOCKERS.md`.
- `docs/ADR/0001-plugin-first-unmodified-upstream.md`, `docs/PLUGIN_CONTRACT.md`, `docs/VIETNAMESE_OFFICE_SPEC.md`.
- `upstream/upstream-lock.json`: 8 repo trên, SHA đầy đủ, quan hệ dependency, license URL/hash; SDK bridge và Linux binary URL/hash/version ghi riêng. Không giả sử mọi repo có cùng tag.
- `LICENSES/upstream/{desktopeditors,desktop-apps,core,sdkjs,web-apps,build-tools,sdkjs-plugins,document-templates}/license.txt` — đúng 8 bản nguyên văn; `terms.txt` trong cùng từng thư mục chỉ khi upstream thật có terms tách riêng. Audit liệt kê đường dẫn gốc và hash từng bản lưu.
- `plans/reports/audit-261029-hst-office.md`: evidence, câu lệnh, thời điểm, giới hạn; không chứa credential.
- Không sửa brief, logo gốc, `.gitignore` hay file phase khác. Không xóa file.

## Steps

1. Kiểm tra git trạng thái/remote và toàn bộ file sẵn có. Repo hiện unborn main; bảo toàn brief/logo/.gitignore chưa tracked. Không tự tạo lịch sử mới trước khi kiểm tra remote main.
2. Revalidate tag pinned, đọc `.gitmodules`/tree/build metadata tại SHA; pin gitlink thật. Repo độc lập không có gitlink: ghi provenance, cách chọn SHA và độ chắc chắn tương thích. Không shallow clone toàn engine.
3. Đọc/lưu các văn bản pháp lý, review attribution/UI notice/source corresponding/trademark, fonts/media và dependency installer. Tách **cho phép spike nội bộ**, **phát hành plugin/mẫu**, **fork/installer blocked**. Blocker có ID, bằng chứng, owner, điều kiện mở; không đánh dấu legal approved thay người có thẩm quyền.
4. So sánh A/B: API được phép, cập nhật upstream, resources, license, phân phối. A không cần đổi executable/Home/About native. Mục ghi nhận tác giả thuộc UI plugin + docs; mô tả chính xác plugin chạy trên engine nguyên bản.
5. Xác minh NĐ30 tại [Cổng Chính phủ](https://chinhphu.vn/default.aspx?docid=199378&pageid=27160) và quan hệ hiệu lực/sửa đổi ở nguồn chính thức; dẫn Phụ lục I/loại mẫu. Thiếu bằng chứng hiệu lực thì chưa gắn nhãn tuân thủ pháp lý.
6. Ghi môi trường thực, disk threshold 10 GiB, không engine build local. Chỉ ghi full-build command sau khi đọc README pinned; nếu chưa xác minh, ghi BLOCKED thay lệnh suy đoán. Kiểm [runner specs](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) và [billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) khi dùng Actions.
7. Chốt contract cho 02–06: Node 22 ESM + node:test; plain JS core; bundle IIFE; Python 3.12 generators với lock hashes; four stable GUIDs; ZIP root; template catalog/ND30 data schema; pipeline commands. Ghi method/API candidates và phép thử spike, chưa tuyên bố supported.

## Validation commands

Chạy ở repo root khi có GitHub network/auth; lỗi DNS/auth là blocker, không phải bằng chứng repo không tồn tại.

```bash
git status --short --branch
git remote -v
git ls-remote --heads origin main
gh api repos/ONLYOFFICE/DesktopEditors/commits/v10.0.0 --jq .sha
gh api repos/ONLYOFFICE/DesktopEditors/contents/.gitmodules?ref=daf8c6948148827201b2907ac1134d222fbfa7b4 --jq .download_url
gh api repos/ONLYOFFICE/DesktopEditors/git/trees/daf8c6948148827201b2907ac1134d222fbfa7b4 --jq '.tree[] | select(.mode == "160000")'
python3 -m json.tool upstream/upstream-lock.json >/dev/null
find LICENSES/upstream -type f -exec sha256sum {} +
df -h /home/office
free -h
nproc
```

## Acceptance / review

- [ ] 8 repo có SHA/license source + terms review; thiếu gì ghi rõ blocker. SHA DesktopEditors khớp owner pin.
- [ ] A/B ADR, footprint, platform availability, runtime download provenance và legal gate rõ. No-code audit được review trước spike.
- [ ] Contract chốt input/output/errors cho logic, catalog, build; chỉ trạng thái dự kiến cho API chưa chạy. `UPSTREAM_BASELINE` không lẫn tag source với bản binary thực cài.

## Parallel, risks, rollback

Không parallel cùng file audit/lock. Sau audit asset xong, 01 được làm; 03–05 chờ spike 02. Network/legal chưa rõ chỉ chặn phần phụ thuộc; vẫn hoàn thành docs có bằng chứng. Quyền mã mới/asset cần owner xác nhận trước public artifact, không đoán license. Rollback bằng revert đúng commit docs/lock; giữ evidence, không xóa upstream/user data.
