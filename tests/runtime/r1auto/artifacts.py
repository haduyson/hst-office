# SPDX-License-Identifier: AGPL-3.0-only
"""Final gate checks actual PNG evidence, not merely a pathname in JSON."""
from pathlib import Path, PureWindowsPath


def verify(out, report):
    from PIL import Image
    out = Path(out).resolve()
    for result in report["results"]:
        if result["status"] == "FAIL":
            continue
        paths = [result["screenshot"]] if result["screenshot"] else []
        paths += [review["screenshot"] for review in report["owner_review"] if review["item"] == result["item"]]
        for name in paths:
            try:
                path = (out / name).resolve()
                if PureWindowsPath(name).drive or not path.is_relative_to(out):
                    raise ValueError("Ảnh nằm ngoài thư mục hiện vật")
                with Image.open(path) as image:
                    if image.format != "PNG" or min(image.size) < 10:
                        raise ValueError("Không phải ảnh PNG đầy đủ")
                    image.verify()
            except Exception as error:
                original = result["detail"]
                result.update(status="FAIL", detail=dict(message="Ảnh bằng chứng không đọc được: " + str(name),
                                                         original=original, error=type(error).__name__))
                break
