# SPDX-License-Identifier: AGPL-3.0-only
"""W12/W13/M8: same synthetic PDF through viewer, print, thumbnail and Draw."""
from pathlib import Path
import subprocess
import time
from support import background, native, says
import pdf_watermark_metrics as metrics
import pdf_watermark_paths as paths
from pdf_viewer_uno import info, open_viewer, signing_props, wait_info


def measure(e, reference, candidate, label):
    result = native("measure", reference, candidate, e.out / (label + "-faintness.png"))
    e.require(result["faint"], "Chữ chéo giữ độ mờ", path=label, **result)
    e.require(result["red_pixels"] > 100, "Con dấu giữ màu đỏ", path=label, red_pixels=result["red_pixels"])
    return result


def run(e, fixtures):
    pdf = Path(fixtures) / "signed-watermark.pdf"
    reference = metrics.render(pdf, 1, 96, e.out / "reference")
    office = e.office
    if e.item in {"W12", "M8"}:
        frame, _ = open_viewer(office, pdf)
        try:
            data = wait_info(office, frame, "SignaturesChecked", lambda v: v is True, timeout=60)
            e.require(data.get("SignatureProblems") == ("rewritten",) or data.get("SignatureProblems") == ["rewritten"],
                      "Phát hiện tệp thay đổi sau khi ký", problems=data.get("SignatureProblems"))
            details = str(data.get("SignatureDetails")) + str(data.get("SignatureLines"))
            e.require(says(details, "(chưa xác minh)") and says(details, "đã thay đổi sau khi ký"),
                      "Hiển thị chữ ký chưa xác minh và lý do", text=details)
            target = (e.out / "viewer.png").resolve()
            rendered = info(office, frame, RenderPage=1, RenderDpi=96, RenderFile=target.as_uri())
            e.require(rendered.get("RenderFileWritten"), "Xuất bitmap của trình xem")
            measure(e, reference, target, "viewer")
            e.shot("viewer-screen")
            printed = (e.out / "printed.pdf").resolve()
            task = background(office.dispatch, frame, ".uno:Print")
            try:
                native("print", printed)
            except Exception:
                native("key", "escape")  # a modal print dialog left open would block every later close
                task.join(10)
                raise
            task.join(10)
            e.require(printed.exists() and printed.stat().st_size > 0, "Đường in sinh tệp PDF")
            measure(e, reference, metrics.render(printed, 1, 96, e.out / "print-render"), "print")
            e.shot("after-print")
        finally:
            frame.close(True)
        thumbnail = paths.recent_thumbnail_png(office, pdf, e.out / "recent-thumbnail.png")
        measure(e, reference, thumbnail, "recent-thumbnail")
        e.shot("recent-documents")
    if e.item in {"W13", "M8"}:
        doc = paths.draw_open(office, pdf)
        try:
            doc.CurrentController.Frame.ContainerWindow.setVisible(True)
            doc.CurrentController.Frame.ContainerWindow.toFront()
            candidate = paths.draw_png(office, doc, 1, 96, e.out / "draw.png")
            measure(e, reference, candidate, "draw")
            # Compare the known dark-text band over the stamp: the image must not cover glyphs.
            retained = native("text-band", reference, candidate)
            e.require(retained >= 0.60, "Chữ không bị hình che", retained_dark_share=retained)
            e.shot("draw-screen")
        finally:
            doc.close(True)
