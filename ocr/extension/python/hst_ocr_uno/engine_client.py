# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Run the OCR core as a separate process and exchange JSON with it (no UNO here, unit-tested on its own).

Which program: the HST_OCR_ENGINE environment variable (a JSON array, e.g. ["python3", "-m", "hst_ocr"], for
development), else the engine shipped inside the extension: engine/hst-ocr(.exe) next to python/. The core is
looked up in this order so the same extension works with the prototype Python core and, later, the Rust binary.
"""
import json
import os
import subprocess
import sys

TIMEOUT_S = 300
EXT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class EngineError(Exception):
    """code is the core's stable error code (or a client-side one), used to pick the message shown to the user."""

    def __init__(self, code, message=""):
        super().__init__(message or code)
        self.code = code


def engine_command(env=None, ext_root=EXT_ROOT):
    env = os.environ if env is None else env
    raw = env.get("HST_OCR_ENGINE", "").strip()
    if raw:
        try:
            cmd = json.loads(raw)
        except ValueError as exc:
            raise EngineError("engine-config", "HST_OCR_ENGINE is not a JSON array") from exc
        if not isinstance(cmd, list) or not cmd or not all(isinstance(a, str) and a for a in cmd):
            raise EngineError("engine-config", "HST_OCR_ENGINE must be a non-empty JSON array of strings")
        return cmd
    exe = os.path.join(ext_root, "engine", "hst-ocr.exe" if sys.platform == "win32" else "hst-ocr")
    if os.path.isfile(exe):
        return [exe]
    raise EngineError("engine-missing", "no OCR engine: neither HST_OCR_ENGINE nor %s" % exe)


def recognize(image_path, mode="text", threads=2, env=None, ext_root=EXT_ROOT, timeout=TIMEOUT_S):
    """The core's response dict for one image; raises EngineError for anything but an ok response."""
    request = {"version": 1, "image": os.path.abspath(image_path), "mode": mode, "lang": "vie", "threads": threads}
    cmd = engine_command(env, ext_root)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window flashing up on Windows
    try:
        proc = subprocess.run(cmd, input=json.dumps(request).encode("utf-8"), capture_output=True,
                              timeout=timeout, env=dict(os.environ if env is None else env), creationflags=flags,
                              check=False)
    except subprocess.TimeoutExpired as exc:
        raise EngineError("timeout", "OCR engine did not answer in %d s" % timeout) from exc
    except OSError as exc:
        raise EngineError("engine-missing", "cannot start the OCR engine: %s" % exc) from exc
    try:
        response = json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError, UnicodeDecodeError) as exc:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise EngineError("engine-failed", "exit %d, no JSON answer: %s" % (proc.returncode, tail[0])) from exc
    if not isinstance(response, dict) or response.get("version") != 1:
        raise EngineError("engine-failed", "unexpected answer from the OCR engine")
    if not response.get("ok"):
        err = response.get("error") or {}
        raise EngineError(str(err.get("code", "engine-failed")), str(err.get("message", "")))
    if not isinstance(response.get("blocks"), list):
        raise EngineError("engine-failed", "answer without blocks")
    return response
