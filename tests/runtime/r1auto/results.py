# SPDX-License-Identifier: AGPL-3.0-only
"""Pure result, selection and summary contract; no desktop dependencies."""
import json
import re
from pathlib import Path, PureWindowsPath

ITEMS = {"windows": tuple(f"W{i}" for i in range(1, 16)),
         "macos": tuple(f"M{i}" for i in range(1, 9))}
OWNER_ONLY = {"M4"}


def parse_items(text, platform):
    allowed = ITEMS[platform]
    if not text.strip() or text.strip().lower() == "all":
        return list(allowed)
    chosen = set()
    for token in re.split(r"[,\s]+", text.strip().upper()):
        match = re.fullmatch(r"([WM])(\d+)(?:-([WM])?(\d+))?", token)
        if not match:
            raise ValueError(f"Bộ lọc không hợp lệ: {token}")
        prefix, first, other, last = match.groups()
        start, end = int(first), int(last or first)
        if other and other != prefix or end < start or end > 15:
            raise ValueError(f"Khoảng không hợp lệ: {token}")
        for number in range(start, end + 1):
            item = f"{prefix}{number}"
            if item not in allowed:
                raise ValueError(f"Mục không thuộc nền tảng: {item}")
            chosen.add(item)
    return [item for item in allowed if item in chosen]


def row(item, status, detail, screenshot=None):
    value = dict(item=item, status=status, detail=detail, screenshot=screenshot)
    validate_row(value)
    return value


def validate_row(value):
    if set(value) != {"item", "status", "detail", "screenshot"}:
        raise ValueError("Sai trường kết quả")
    if value["item"] not in ITEMS["windows"] + ITEMS["macos"]:
        raise ValueError("Mục không xác định")
    if value["status"] not in {"PASS", "FAIL", "SKIP"}:
        raise ValueError("Trạng thái không xác định")
    if not isinstance(value["detail"], (dict, str)) or not value["detail"]:
        raise ValueError("Thiếu bằng chứng")
    shot = value["screenshot"]
    if shot is not None and (not isinstance(shot, str) or not shot or
                             Path(shot).is_absolute() or PureWindowsPath(shot).drive or ".." in Path(shot).parts or "\\" in shot):
        raise ValueError("Đường dẫn ảnh phải nằm trong hiện vật")
    if value["status"] == "PASS" and not shot:
        raise ValueError("PASS cần ảnh bằng chứng")


def gate(rows):
    return bool(rows) and all(r["status"] == "PASS" or
                             r["item"] in OWNER_ONLY and r["status"] == "SKIP" and r["screenshot"]
                             for r in rows)


def summary(report):
    lines = ["## Kiểm tra R1", "", f"Bản dựng: {report['run_id']} · {report['platform']}", ""]
    for result in report["results"]:
        detail = result["detail"]
        text = detail if isinstance(detail, str) else detail.get("message", "Xem số đo trong results.json")
        text = str(text).replace("\n", " ").replace("\r", " ").replace("|", "\\|")
        lines.append(f"- {result['item']}: **{result['status']}** — {text}")
    lines += ["", "## Chủ sở hữu duyệt", ""]
    for review in report.get("owner_review", []):
        lines.append(f"- {review['item']}: {review['detail']} — `{review['screenshot']}`")
    return "\n".join(lines) + "\n"


class Results:
    def __init__(self, out, platform, run_id, items):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.report = dict(platform=platform, run_id=run_id, owner_review=[], results=[
            row(item, "FAIL", "Chưa chạy: chuẩn bị hoặc tiến trình bị gián đoạn") for item in items])
        self.save()

    def put(self, value):
        validate_row(value)
        for index, existing in enumerate(self.report["results"]):
            if existing["item"] == value["item"]:
                self.report["results"][index] = value
                self.save()
                return
        raise ValueError("Mục ngoài bộ lọc")

    def save(self):
        path = self.out / "results.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        (self.out / "summary.md").write_text(summary(self.report), encoding="utf-8")
