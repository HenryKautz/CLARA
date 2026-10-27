#!/usr/bin/env python3
"""compare-encodings.py [--sizes N...] [--encodings E...] [--limit S] [--solver NAME]

SatPlan's interfering-action mutexes three ways, on the FourPackage general
problems (the 12-way disjunctive goal, as run-plans.py --stage general poses it):

  original   the installed FiFO (~/bin/planner.sh) and its satplan.wff: one
             clause per interfering pair, quantified out by hand.
  pairwise   the FiFO checkout's planner with satplan.wff's MUTEX forms and
             (option *mutex-pairwise* 1), via shims-pairwise/sbcl: the same
             pairs, each written once.
  linear     the checkout's planner with MUTEX's default: the smaller of the
             pairs and the linear prefix/suffix encoding.

Each problem is planned at exactly the horizon its general plan was found at
(results/plans.jsonl; for a problem with no general plan, its shortest goal
horizon), with the same exact MaxSAT solver, so every encoding must report the
SAME optimal cost: the script records a mismatch as status "cost-mismatch".
Per run it records wall time, the planner's peak memory (the largest resident
set of any process it waited for, from /usr/bin/time -l) and the size of the
weighted CNF it solved.  One JSON record per run in results/encodings.jsonl; a
run already recorded (any status but timeout below this limit) is skipped.
Runs go one at a time, largest last.
"""
import argparse, json, os, re, shutil, sys
import fpcommon as F
from importlib import import_module

RP = import_module("run-plans")
RESULTS = os.path.join(F.HERE, "results", "encodings.jsonl")
WORK = os.path.join(F.SCRATCH, "fp-encodings")
FIFO = os.environ.get("FIFO_CHECKOUT", os.path.expanduser("~/Programming/FiFO"))
PLANNER = {"original": "planner.sh",
           "pairwise": os.path.join(FIFO, "bin", "planner.sh"),
           "linear": os.path.join(FIFO, "bin", "planner.sh")}


def env(encoding):
    e = F.env()
    if encoding == "pairwise":
        e["PATH"] = os.path.join(F.SCRIPTS, "shims-pairwise") + ":" + e["PATH"]
    return e


def general_records():
    out = {}
    for line in open(os.path.join(F.HERE, "results", "plans.jsonl")):
        r = json.loads(line)
        if r["stage"] == "general" and r["status"] == "ok":
            out[r["name"]] = r
    return out


def done_before(limit):
    seen = {}
    if os.path.exists(RESULTS):
        for line in open(RESULTS):
            r = json.loads(line)
            if r["status"] != "timeout" or r["limit_s"] >= limit:
                seen[(r["encoding"], r["name"])] = r
    return seen


def peak_rss(out):
    m = re.search(r"(\d+)\s+maximum resident set size", out)
    return int(m.group(1)) if m else None


def one(encoding, name, H, solver, limit, want_cost):
    work = os.path.join(WORK, f"{encoding}-{name}")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    src = os.path.join(F.HERE, name + ".pddl")
    shutil.copy(src, work)
    cmd = ["/usr/bin/time", "-l", PLANNER[encoding], name + ".pddl", "--domain", F.DOMAIN,
           "--weighted-solver", solver, "--timeout", str(limit), "--numslices", str(H)]
    status, wall, out = run(cmd, work, limit, env(encoding))
    rec = dict(encoding=encoding, name=name, size=F.size_of(name), horizon=H, solver=solver,
               limit_s=limit, status=status, wall_s=round(wall, 2), peak_rss_mb=None)
    rss = peak_rss(out)
    if rss:
        rec["peak_rss_mb"] = round(rss / 2**20)
    answer = os.path.join(work, name + ".answer")
    wcnf = os.path.join(work, name + ".wcnf")
    if status == "ok":
        h, rec["cost"], rec["actions"] = RP.parse_plan(out, answer)
        if h != H or rec["cost"] is None:
            rec["status"] = "failed"
        elif want_cost is not None and rec["cost"] != want_cost:
            rec["status"] = "cost-mismatch"
            rec["expected_cost"] = want_cost
        if RP.stopped_early(out):
            rec["status"] = "not-optimal"
    if os.path.exists(wcnf):
        rec["wcnf_vars"], rec["wcnf_clauses"] = RP.wcnf_size(wcnf)
        rec["wcnf_bytes"] = os.path.getsize(wcnf)
    if rec["status"] != "ok":
        rec["log_tail"] = out[-1500:].splitlines()[-12:]
    shutil.rmtree(work, ignore_errors=True)
    return rec


def run(cmd, cwd, limit, environment):
    """run-plans.run with a chosen environment."""
    saved = F.env
    F.env = lambda: environment
    try:
        return RP.run(cmd, cwd, limit)
    finally:
        F.env = saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="*", default=[6, 7, 8, 9, 10, 11])
    ap.add_argument("--encodings", nargs="*", default=["original", "pairwise", "linear"])
    ap.add_argument("--solver", default="wmaxcdcl")
    ap.add_argument("--limit", type=int, default=1800)
    a = ap.parse_args()
    general = general_records()
    seen = done_before(a.limit)
    os.makedirs(WORK, exist_ok=True)
    for name in F.problems(a.sizes):
        g = general.get(name)
        H = g["horizon"] if g else min(F.horizons(os.path.join(F.HERE, name + ".pddl")).values())
        want = g["cost"] if g and g["solver"] in RP.EXACT else None
        for enc in a.encodings:
            if (enc, name) in seen:
                continue
            rec = one(enc, name, H, a.solver, a.limit, want)
            with open(RESULTS, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"  {enc:8s} {name}: {rec['status']} {rec['wall_s']}s H={H} "
                  f"cost {rec.get('cost')} clauses {rec.get('wcnf_clauses')} "
                  f"rss {rec['peak_rss_mb']} MB", flush=True)


if __name__ == "__main__":
    main()
