# SPDX-License-Identifier: AGPL-3.0-only
"""`build-queue.sh train ...`: the build train from the command line.

  train add <branch> [--platform linux|windows|both]   the branch is ready: it rides the next train (default both)
  train remove <branch>                                drop it (a train already building finishes with it)
  train status [<branch>|<train>] [--json]             overview, one branch (its train, builds, result) or one train
  train wait <branch> [--timeout S]                    until the branch has a result: exit 0 passed (prints the
                                                       outputs), 1 ejected/failed, 2 timeout
  train start --integrator                             integrator: build a train at the next tick, below the thresholds
A train starts every train_interval_minutes (90) or as soon as train_min_branches (4) are ready, as
train/<prefix>NNN = the integration branch + the ready branches, with one Linux and one Windows build.
"""
import json
import sys

from .queue_store import QueueError
from .queue_train_ops import add, member_jobs, remove, start, wait
from .queue_train_store import TRAIN_ACTIVE, TrainStore


def add_parser(sub):
    tr = sub.add_parser("train", help="build train: batched builds of ready branches")
    tsub = tr.add_subparsers(dest="train_cmd", required=True)
    a = tsub.add_parser("add")
    a.add_argument("branch")
    a.add_argument("--platform", default="both", choices=("linux", "windows", "both"))
    r = tsub.add_parser("remove")
    r.add_argument("branch")
    s = tsub.add_parser("status")
    s.add_argument("what", nargs="?")
    s.add_argument("--json", action="store_true")
    w = tsub.add_parser("wait")
    w.add_argument("branch")
    w.add_argument("--timeout", type=int)
    st = tsub.add_parser("start")
    st.add_argument("--integrator", action="store_true", required=True, help="reserved for the integrator")


def job_line(platform, job):
    if job is None:
        return f"    {platform:<8} (job record missing)"
    out = ", ".join(job.get("output", [])) if job["state"] == "done" and not job.get("output_deleted") else ""
    return f"    {platform:<8} {job['id']}  {job['state']:<9} {out or job.get('error', '')}"


def print_train(store, rec, out):
    sha = rec.get("sha", "")[:10] or "-"
    print(f"{rec['name']}  {rec['state']:<9} {rec['kind']}{' of ' + rec['parent'] if rec.get('parent') else ''}  "
          f"base {rec['base_ref']}@{rec['base_sha'][:10]}  sha {sha}  created {rec['created_at']}", file=out)
    for m in rec["members"]:
        print(f"    member   {m['branch']}@{m['sha'][:10]} ({','.join(m['platforms'])})", file=out)
    for platform, jid in sorted(rec.get("jobs", {}).items()):
        try:
            job = store.load(jid)
        except QueueError:
            job = None
        print(job_line(platform, job), file=out)
    for branch, files in sorted(rec.get("conflicts", {}).items()):
        print(f"    conflict {branch}: {', '.join(files[:5])}", file=out)
    for branch, reason in sorted(rec.get("deferred", {}).items()):
        print(f"    waiting  {branch}: {reason}", file=out)
    if rec.get("attribution"):
        a = rec["attribution"]
        print(f"    blamed   {', '.join(a['blamed']) or '-'} ({a['method']}: {a['detail']})", file=out)
    if rec.get("children"):
        print(f"    halves   {', '.join(rec['children'])}", file=out)
    if rec.get("last_error") and rec["state"] in TRAIN_ACTIVE:
        print(f"    error    {rec['last_error']}", file=out)


def print_branch(store, cand, out):
    print(f"{cand['branch']}  {cand['state']}  {cand.get('note', '')}", file=out)
    print(f"    platforms {','.join(cand['platforms'])}; added {cand['added_at']}; trains so far "
          f"{cand.get('attempts', 0)}", file=out)
    for platform, job in member_jobs(store, cand):
        print(job_line(platform, job), file=out)


def status(store, what, as_json, out):
    ts = TrainStore(store)
    branches, trains = ts.branches(), ts.trains()
    if what:
        cand = branches.get(what)
        rec = None if cand else ts.load(what)
        if cand is None and rec is None:
            raise QueueError(f"{what} is neither a train candidate nor a train")
        if as_json:
            print(json.dumps(cand or rec, indent=1, sort_keys=True), file=out)
        elif cand:
            print_branch(store, cand, out)
            current = ts.load(cand["train"]) if cand.get("train") else None
            if current:
                print_train(store, current, out)
        else:
            print_train(store, rec, out)
            for when, msg in rec.get("events", [])[-15:]:
                print(f"    {when}  {msg}", file=out)
        return 0
    if as_json:
        print(json.dumps({"branches": branches, "trains": trains[-10:]}, indent=1, sort_keys=True), file=out)
        return 0
    cfg = store.config()
    print(f"train: {'enabled' if cfg['train_enabled'] else 'DISABLED'}; base {cfg['integration_branch']}; starts every "
          f"{cfg['train_interval_minutes']} min or at {cfg['train_min_branches']} ready branches", file=out)
    order = {"in-train": 0, "ready": 1}
    for cand in sorted(branches.values(), key=lambda c: (order.get(c["state"], 2), c["branch"])):
        print(f"  {cand['state']:<9} {cand['branch']}: {cand.get('note', '')}", file=out)
    for rec in trains[-5:]:
        print_train(store, rec, out)
    return 0


def run(store, args, out=sys.stdout):
    if args.train_cmd == "add":
        cand = add(store, args.branch, args.platform)
        print(f"{cand['branch']}: {cand['note']}", file=out)
        return 0
    if args.train_cmd == "remove":
        cand = remove(store, args.branch)
        print(f"{args.branch}: {cand.get('note') if cand.get('removed') else 'removed'}", file=out)
        return 0
    if args.train_cmd == "status":
        return status(store, args.what, args.json, out)
    if args.train_cmd == "wait":
        return wait(store, args.branch, args.timeout, out=out)
    if args.train_cmd == "start":
        if not any(c["state"] == "ready" for c in TrainStore(store).branches().values()):
            raise QueueError("no ready branch: `train add <branch>` first")
        start(store)
        print("a train starts at the next dispatcher tick (unless one is already building)", file=out)
        return 0
    return 2
