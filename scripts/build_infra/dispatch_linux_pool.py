# SPDX-License-Identifier: AGPL-3.0-only
"""All Linux build slots of the dispatcher: the dev server's own (LinuxRunner) first, then each remote build host
of `linux_remote_hosts` (RemoteLinuxRunner). A job's `host` says which runner owns it ("local" or the host name);
a job requeued because its host failed carries avoid_hosts and never goes back there.
"""
from .dispatch_linux import LinuxRunner
from .dispatch_remote_linux import RemoteLinuxRunner


class LinuxPool:
    def __init__(self, store, cfg, local=None, remotes=None):
        self.store = store
        self.local = local or LinuxRunner(store, cfg)
        self.remotes = remotes if remotes is not None else [
            RemoteLinuxRunner(store, cfg, h) for h in cfg.get("linux_remote_hosts", []) if h.get("enabled", True)]
        self._cfg = cfg

    @property
    def cfg(self):
        return self._cfg

    @cfg.setter
    def cfg(self, cfg):
        """The dispatcher reloads config.json every tick: hosts added, removed or disabled take effect at once."""
        self._cfg = cfg
        self.local.cfg = cfg
        known = {r.name: r for r in self.remotes}
        self.remotes = []
        for h in cfg.get("linux_remote_hosts", []):
            if not h.get("enabled", True):
                continue
            r = known.get(h["name"]) or RemoteLinuxRunner(self.store, cfg, h)
            r.cfg, r.hcfg = cfg, h
            if r.host.address != h["address"]:
                r.host.address = h["address"]   # the address is one config value (VM103 has no fixed IP yet)
            self.remotes.append(r)

    def runner_for(self, job):
        host = job.get("host")
        for r in self.remotes:
            if r.name == host:
                return r
        return self.local

    def want(self, job):
        return self.local.want(job)

    def free_slot(self, jobs, want, job=None):
        if not (job and "local" in job.get("avoid_hosts", [])):
            slot = self.local.free_slot(jobs, want)
            if slot is not None:
                return slot
        for r in self.remotes:
            slot = r.free_slot(jobs, want, job)
            if slot is not None:
                return slot
        return None

    def start(self, job, slot):
        if isinstance(slot, str) and ":" in slot:
            name = slot.split(":", 1)[0]
            for r in self.remotes:
                if r.name == name:
                    return r.start(job, slot)
            raise RuntimeError(f"no remote Linux host {name!r}")
        return self.local.start(job, slot)

    def check(self, job):
        return self.runner_for(job).check(job)

    def cancel(self, job):
        return self.runner_for(job).cancel(job)

    def health(self, jobs):
        for r in self.remotes:
            r.health(jobs)
