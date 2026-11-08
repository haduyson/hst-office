# SPDX-License-Identifier: AGPL-3.0-only
"""W14's machine-checkable refusal, with a temporary software certificate."""
import hashlib
from pathlib import Path
from support import background, wait
from pdf_viewer_uno import open_viewer, info, signing_props
from pdf_watermark_paths import choose_viewer_certificate
from pdf_signature_fixtures import SIGNER_CN
from signature_dialogs import Dialogs


def run(e, fixtures):
    source = Path(fixtures) / "restricted.pdf"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = (e.out / "khong-duoc-tao.pdf").resolve()
    frame, _ = open_viewer(e.office, source)
    dialogs = Dialogs(e.office, str(e.out), [])
    try:
        e.office.dispatch(frame, ".uno:HSTPdfSignPanel", signing_props(Show=True))
        choose_viewer_certificate(e.office, dialogs, frame, SIGNER_CN)
        done = {}
        def sign():
            done["result"] = e.office.dispatch(frame, ".uno:HSTPdfSign", signing_props(
                TargetURL=target.as_uri(), Visible=True, Page=1, X=40.0, Y=40.0, Width=200.0, Height=70.0)).Result
        thread = background(sign)
        def refusal():
            win, children = dialogs.top()
            return win if {"yes", "close"} <= children else None
        win = wait(refusal, 60)
        label = {p.Name: p.Value for p in win.getChild("yes").getState()}.get("Text", "")
        status = info(e.office, frame).get("StatusText", "")
        e.shot("permission-refusal")
        e.require("không cho phép ký số" in status and label == "Nhập mật khẩu quyền",
                  "Từ chối ký và có nút nhập mật khẩu quyền", status=status, button=label)
        dialogs.later(win.getChild("close")).join(10)
        thread.join(10)
        e.require(not thread.is_alive() and done.get("result") is False and not target.exists(),
                  "Không tạo tệp đã ký", result=done.get("result"), exists=target.exists())
        after = hashlib.sha256(source.read_bytes()).hexdigest()
        e.require(after == digest, "Nguồn không thay đổi", before_sha256=digest, after_sha256=after)
        e.owner.append(dict(item="W14", detail="Ký bằng USB token thật của chủ sở hữu",
                            screenshot=e.shots[-1]))
    finally:
        frame.close(True)
