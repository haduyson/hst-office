# SPDX-License-Identifier: AGPL-3.0-only
"""Native toolbar/group geometry and fold ordering; no empty observation can pass."""
import time
import ribbon_os


def run(e, doc):
    window = doc.CurrentController.Frame.ContainerWindow
    observations = []
    # From full screen down to about 1100 px; the runner's screen may be narrower than 1800 logical px.
    area = e.office.service("com.sun.star.awt.Toolkit").getWorkArea().Width
    for width in [area] + [w for w in (1800, 1600, 1450, 1300, 1200, 1100) if w < area - 50]:
        window.setPosSize(0, 35, width, 900, 15)
        time.sleep(2)
        sample = ribbon_os.scan(ribbon_os.read(e, f"ribbon-{width}"))
        sample["method"] = "OS accessibility tree (UIA/AX)"
        sample["requested_width"] = width
        e.shot("ribbon-" + str(width))
        e.require(sample["groups"] and sample["banner"], "Đo được ribbon và banner ở mỗi kích thước", **sample)
        right = sample["banner"][0]
        e.require(all(sample["frame"][0] <= b[0] and b[0] + b[2] <= right + 2 for b in sample["groups"].values()),
                  "Không nhóm nào bị cắt hoặc đè banner", **sample)
        observations.append(sample)
    minimum = {}
    for sample in observations:
        for name, bounds in sample["groups"].items():
            minimum[name] = min(minimum.get(name, bounds[2]), bounds[2])
    shrunk, folded = False, False
    for before, after in zip(observations, observations[1:]):
        for name, bounds in before["groups"].items():
            if name in after["groups"]:
                shrunk |= after["groups"][name][2] < bounds[2] - 1
        missing = set(before["groups"]) - set(after["groups"]) - set(after["buttons"])
        if missing:
            folded = True
            e.require(shrunk and after["chevron"] is not None, "Nhóm thu nhỏ trước khi gập vào dấu »", before=before, after=after)
            shown = list(after["groups"].values()) + list(after["buttons"].values())
            shown = [b for b in shown if b[0] < after["chevron"][0]]
            gap = after["chevron"][0] - max(b[0] + b[2] for b in shown)
            e.require(all(gap < minimum[name] for name in missing), "Chỉ gập nhóm không còn đủ chỗ", gap=gap,
                      minimum={name: minimum[name] for name in missing})
    e.require(shrunk, "Có bước thu nhỏ nhóm", observations=observations)
    wide, small = observations[0]["banner"], observations[-1]["banner"]
    e.require(small[2] < wide[2] and abs(small[2] / small[3] - 160 / 104) < 0.25,
              "Banner đổi bản gọn ở 1100 px", wide=wide, compact=small, folded=folded)
