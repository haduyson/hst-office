# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded office conversion processes with profiles confined to tests/output."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
from .odf import BASE


class RuntimeBlocked(RuntimeError):
    pass


def socket_probe(directory):
    try:
        with tempfile.TemporaryDirectory(prefix="ipc-", dir=directory) as tmp:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.bind(str(Path(tmp) / "probe.sock"))
                sock.listen(1)
    except PermissionError as error:
        raise RuntimeBlocked("Sandbox denies AF_UNIX bind/listen required by LibreOffice: " + str(error)) from error


def run(command, env, log, timeout=60):
    with log.open("w", encoding="utf-8") as output:
        with subprocess.Popen(command, env=env, stdout=output, stderr=subprocess.STDOUT,
                              start_new_session=True) as process:
            output.write(f"PID={process.pid}; worktree={BASE}; port=none; command={command!r}\n")
            output.flush()
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise RuntimeError("LibreOffice timeout; owned process group stopped: " + str(log))
    return code


def convert(soffice, source, output, extension, filter_name=None):
    output.mkdir(parents=True, exist_ok=True)
    target = output / (source.stem + "." + extension)
    if target.exists():
        raise RuntimeError("Refusing stale conversion artifact: " + str(target))
    profiles = BASE / "tests/output/template-profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lo-", dir=profiles) as tmp:
        env = {**os.environ, "XDG_CACHE_HOME": tmp + "/cache", "XDG_CONFIG_HOME": tmp + "/config",
               "SAL_USE_VCLPLUGIN": "svp", "GSETTINGS_BACKEND": "memory"}
        command = [str(soffice), "-env:UserInstallation=" + Path(tmp).as_uri(), "--headless",
                   "--nologo", "--nodefault", "--nofirststartwizard", "--convert-to",
                   extension + (":" + filter_name if filter_name else ""), "--outdir",
                   str(output), str(source.resolve())]
        log = output / (source.stem + "-" + extension + ".log")
        code = run(command, env, log)
    if code != 0 or not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"Conversion failed (exit {code}): {source.name} -> {extension}; {log}")
    return target


def check_pdf(path, expected_text):
    if path.read_bytes()[:5] != b"%PDF-":
        raise ValueError("Invalid PDF: " + str(path))
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True,
                            capture_output=True, text=True, timeout=30)
    if expected_text not in result.stdout:
        raise ValueError("PDF text lost: " + expected_text)
    return result.stdout.count("\f")
