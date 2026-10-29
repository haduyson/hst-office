# 06 — CI thật; desktop skeleton blocked

Status: pending. Owner: Claude CI. Dependencies: 02; final integration cần 03–05. Priority: P0/P1. Context: [brief §§8–10](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md). Có thể làm song song 03/04, chỉ file dưới đây.

## Requirements

CI kiểm thứ đã triển khai thật trên `ubuntu-latest`, Node 22, Python 3.12. Push main + PR đều chạy quality/plugin builds; owner đã chọn direct main. Không full-engine compile, không installer HST, không secret/certificate trong git, không workflow `echo success`. Workflow desktop manual-only, nêu TODO và **fail rõ nếu được gọi**.

## Files tạo / ownership

- `.github/workflows/{quality.yml,plugins.yml,desktop-linux.yml,desktop-windows.yml,desktop-macos.yml}`.
- `scripts/check-workflows.py`, `scripts/create-artifact-manifest.py`.
- `docs/CI.md`, `docs/RELEASE_CHECKLIST.md`; `plans/reports/ci-261029-hst-office.md`.
- Outputs ignored: `dist/artifact-manifest.json`, `dist/SHA256SUMS`, `tests/output/ci/`.
- Không sửa root package/locks/shared scripts của 02; thiếu command chuyển Codex/07 xử lý. `release.yml` publish thật thuộc backlog later, không tạo placeholder release thành công.

## Steps

1. Pin actions bằng full SHA đã đối chiếu release source, dùng `permissions: contents: read`, timeout, concurrency theo ref và cancel obsolete runs; checkout không giữ credential khi không cần. Không `pull_request_target` chạy code không tin cậy.
2. Quality: npm ci → narrow unit suites → lint/LOC/notices/offline assets/doc links; Python test/OOXML validation khi sources của phase 05 đã có. Điều kiện stage phải dựa trên paths và ghi job chưa có là NOT RUN, không giả PASS cho template coverage. Phase 07 bỏ điều kiện bootstrap và yêu cầu đầy đủ 4 plugins/18 templates.
3. Plugins: khi stage 05 có, export shared data → generate templates/catalog → build mọi plugin → archive/template validators và byte-repro check → manifest → upload. Thiếu/stale staging inputs fail, không dùng output lần trước. Trước 05 chỉ build plugin hiện có, ghi coverage thật. Upload versioned artifacts retention 14 ngày sau legal artifact gate; evidence acceptance tối thiểu được tracked theo 02/07 nên không mất khi artifact hết hạn. Không public release tự động. SDK/runtime test chưa có capability tách trạng thái rõ, không `continue-on-error` làm acceptance xanh.
4. Cài build dependencies trên runner: Node/Python actions pinned; ImageMagick + font từ provenance 01, venv + hashed requirements. Local đã có convert/libreoffice/xvfb; `zip` CLI chưa có, packaging dùng Python stdlib zipfile. LibreOffice chỉ phục vụ render phụ khi job cần, không yêu cầu cho Node tests.
5. Manifest ghi git commit, upstream source/binary/SDK pin, dependency lock hashes, artifact SHA-256, supported/tested OS, notices/source retrieval. Không gọi đây là SBOM hoàn chỉnh nếu chỉ manifest. Không quảng cáo OS chưa test.
6. Mỗi `desktop-*.yml`: chỉ `workflow_dispatch`, runner `ubuntu-latest` cho guard ít tốn phí; một step exit 1 cùng message `BLOCKED/TODO: legal, pinned build procedure, adequate runner, platform QA/signing`. Comment ghi OS runner tương lai. Không upload, không tag/release, không gọi builder giả. CI checker xác minh các guard không thành success.
7. `RELEASE_CHECKLIST` tách plugin/template artifact gate và installer gate. Chưa có chứng chỉ thì không ghi signed/verified; chưa audit license mã mới thì không public artifacts. Gate release v1.0 còn đủ machine/OS, legal, recovery, uninstall và source corresponding.
8. `measure-job.py` bọc build/test: elapsed, peak RSS, CPU time, disk before/after; CPU/RAM của runner phải đo lại, không lấy 32/47 local áp lên Actions. Ghi quota/retention thực, free <10 GiB ngừng bước nặng, không prune ngoài cache được sở hữu.

## Validation commands

```bash
.venv/bin/python scripts/check-workflows.py
npm ci
npm run lint
npm test
node scripts/export-template-data.js --out build/template-data.json
SOURCE_DATE_EPOCH=1767225600 .venv/bin/python scripts/generate-templates.py --out dist/templates
npm run build:plugins
npm run check:plugins
.venv/bin/python scripts/check-templates.py dist/templates
.venv/bin/python scripts/check-reproducibility.py
npm run check:notices
npm run check:offline
python3 scripts/create-artifact-manifest.py --dir dist
gh workflow list
gh run list --branch main --limit 5
```

Block lệnh trên là final integration sau 05; trước đó không chạy command chưa có, chỉ validate workflow và plugin hiện tại theo bước 2/3. Bootstrap venv/hashed lock như 05 trước checker. Workflow checker parse YAML với dependency đã lock tại 02; kiểm trigger/permission/SHA/desktop guard và references. Chạy `gh run view <run-id> --log-failed` với ID thật từ run list khi fail; không lấy local success thay GitHub conclusion. Network/auth thiếu là blocker remote CI.

## Acceptance / review

- [ ] Quality/plugins chạy thật cho HEAD main; logs/artifacts/hash có thể truy xuất, hoặc ghi rõ chưa chạy do remote access.
- [ ] Final pipeline cần 4 plugins/18 templates; thiếu test/file là fail; quyền tối thiểu/action SHA/retention/resources đúng.
- [ ] 3 workflow desktop không tự chạy trên push, manual invocation fail blocked có TODO, không tạo installer. Public release chưa mở.

## Parallel, risks, rollback

Ownership workflow/scripts/docs riêng; không concurrent commit/staging trong shared repo. Runner quota/network/license distribution cần gate thực, không suy miễn phí. Rollback bằng revert workflow commit hoặc disable đúng workflow của dự án; không sửa engine/cache global, không xóa artifact evidence đang review.
