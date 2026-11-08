# SPDX-License-Identifier: AGPL-3.0-only
"""Own a normal-profile listener so shell association checks observe the correct desktop."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DRIVER_ONLY = ("PYTHONPATH", "PYTHONHOME", "URE_BOOTSTRAP", "PYTHONNOUSERSITE")


def processes(install):
    """Tooling-Python operation: identify this installed application's processes only."""
    import psutil
    root = Path(install).resolve()
    found = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        if not (proc.info["name"] or "").lower().startswith(("soffice", "oosplash")):
            continue
        paths = [proc.info["exe"]] + (proc.info["cmdline"] or [])[:1]
        if any(path and Path(path).resolve().is_relative_to(root) for path in paths):
            found.append(proc)
    return found


def stop_recorded(pidfile):
    """Only stop recorded PIDs that still belong to the recorded installation."""
    import psutil
    pidfile = Path(pidfile)
    if not pidfile.exists():
        return []
    install = pidfile.with_name("default-install.txt").read_text(encoding="utf-8")
    pids = {int(value) for value in pidfile.read_text().split()}
    owned = [proc for proc in processes(install) if proc.pid in pids]
    for proc in owned:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=5)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    _, remaining = psutil.wait_procs(alive, timeout=5)
    if remaining:
        raise RuntimeError("Không dừng được tiến trình mặc định của lượt kiểm tra")
    return [proc.pid for proc in owned]


class DefaultSession:
    def __init__(self, office, out):
        self.office, self.out = office, Path(out)
        self.pidfile = Path(office.workdir) / "default-pids.txt"
        self.env = {key: value for key, value in os.environ.items() if key not in DRIVER_ONLY}
        self.pids, self.proc, self.log = set(), None, None

    def _tool(self, action, value):
        command = [os.environ.get("R1_TOOLS_PYTHON", sys.executable), str(Path(__file__).resolve()), action, str(value)]
        done = subprocess.run(command, env=self.env, capture_output=True, text=True,
                              encoding="utf-8", check=True, timeout=20)
        return json.loads(done.stdout)

    def _record(self):
        self.pids.update(self._tool("list", self.office.install))
        temporary = self.pidfile.with_suffix(".tmp")
        temporary.write_text("\n".join(map(str, sorted(self.pids))), encoding="utf-8")
        temporary.replace(self.pidfile)

    def __enter__(self):
        from support import background
        if self._tool("list", self.office.install):
            raise RuntimeError("Đã có tiến trình HST mặc định; không thể nhận quyền quản lý")
        from support import claim_port
        claim_port(self.office.port)
        self.pidfile.with_name("default-install.txt").write_text(str(self.office.install), encoding="utf-8")
        self.log = (self.out / "default-office.log").open("w", encoding="utf-8")
        try:
            command = [str(self.office.binary), "--nologo", "--norestore", "--nodefault",
                       f"--accept=socket,host=127.0.0.1,port={self.office.port};urp;"]
            self.proc = subprocess.Popen(command, env=self.env, stdout=self.log, stderr=self.log)
            self.pids.add(self.proc.pid)
            self.pidfile.write_text(str(self.proc.pid), encoding="utf-8")
            self._record()
            connected = {}
            def connect():
                try:
                    connected["ctx"] = self.office._connect(timeout=90)
                except Exception as error:
                    connected["error"] = error
            thread = background(connect)
            end = time.monotonic() + 100
            while thread.is_alive() and time.monotonic() < end:
                self._record()
                thread.join(0.3)
            if "ctx" not in connected:
                raise RuntimeError("Không kết nối được profile mặc định") from connected.get("error")
            self.office.ctx = connected["ctx"]
            self._record()
            self._welcome_seen()
            return self
        except Exception:
            self.stop()
            raise

    def _welcome_seen(self):
        """The owner opens Writer (W2) before double-clicking a file (W3), so the default profile has shown its
        welcome by then; an unseen modal welcome would hold the shell-opened document behind it."""
        from pdf_viewer_uno import signing_props
        access = self.office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", signing_props(nodepath="/org.hasontech.hstoffice.Welcome"))
        access.setPropertyValue("Shown", True)
        access.commitChanges()

    def stop(self):
        from support import background
        try:
            if self.office.ctx is not None:
                background(self.office._terminate).join(5)
            if self.proc is not None:
                try:
                    self._record()
                finally:
                    try:
                        self._tool("stop", self.pidfile)
                    finally:
                        if self.proc.poll() is None:
                            self.proc.terminate()
                            try:
                                self.proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                self.proc.kill()
                                self.proc.wait(timeout=5)
        finally:
            self.office.ctx = None
            if self.log:
                self.log.close()

    def __exit__(self, *_error):
        self.stop()


if __name__ == "__main__":
    action, value = sys.argv[1:]
    print(json.dumps([proc.pid for proc in processes(value)] if action == "list" else stop_recorded(value)))
