#!/usr/bin/env python3
"""compare.py BENCH [--sizes N...] [--slack K...] [--jobs N] [--limit S]

Restricted cost minimization (FiFO planner.sh --restrict steps|actions) against
EvalMaxSAT on the whole theory, on the single-goal problems of a CLARA
benchmark (SimpleGrid, TwoPackage, ThreePackage):

  full      planner.sh --numslices H: kissat, then EvalMaxSAT over the whole
            theory -- the optimum at H (proved, unless it hit --limit)
  steps     planner.sh --numslices H --restrict steps: EvalMaxSAT with every
            action atom the SAT plan did not take at that slice forced false
  actions   planner.sh --numslices H --restrict actions: its ground actions
            allowed at any slice
  sat       the SAT plan's own cost, printed by both restricted runs (kissat is
            deterministic, so they restrict the same plan -- checked)

H is the goal's shortest horizon (from its .answer, or ThreePackage's
results/plans.jsonl) plus each --slack K (default 0 and 4): at the shortest
horizon a plan has little room to waste, with slack it has more.

Uses the FiFO CHECKOUT ($FIFO, default ~/Programming/FiFO), not the installed
copy: --restrict is not installed yet.  One JSON record per run goes to
results/<bench>.jsonl; a (problem, slack, method) already recorded is skipped.
"""
import argparse, concurrent.futures as cf, glob, json, os, re, shutil, signal, subprocess, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
CLARA = os.path.dirname(HERE)
FIFO = os.environ.get("FIFO", os.path.expanduser("~/Programming/FiFO"))
PLANNER = os.path.join(FIFO, "bin", "planner.sh")
SCRATCH = os.environ.get("RP_SCRATCH", "/tmp/restricted-planning")
LOCK = threading.Lock()
METHODS = ("full", "steps", "actions")


def goals(bench, sizes):
    """[(name, pddl, domain, H)] of the benchmark's single-goal problems."""
    out = []
    d = os.path.join(CLARA, bench)
    if bench == "ThreePackage":
        recs = {}
        for l in open(os.path.join(d, "results", "plans.jsonl")):
            r = json.loads(l)
            if r["stage"] == "goal" and r["status"] == "ok":
                recs[r["name"]] = r
        for name, r in sorted(recs.items()):
            if not sizes or r["size"] in sizes:
                out.append((name, os.path.join(d, "goals", name + ".pddl"),
                            os.path.join(d, "clara-logistics-handling.pddl"), r["horizon"]))
        return out
    for p in sorted(glob.glob(os.path.join(d, "goals", "*.pddl"))):
        name = os.path.basename(p)[:-5]
        n = int(re.match(r"grid(\d+)x", name).group(1))
        if sizes and n not in sizes:
            continue
        ans = os.path.join(d, "goals", name + ".answer")
        slices = [int(m) for m in re.findall(r"^\(HOLDS .* (\d+)\)$", open(ans).read(), re.M)]
        out.append((name, p, None, max(slices)))
    return out


def run(cmd, cwd, limit):
    t = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, start_new_session=True,
                         env=dict(os.environ, FIFO_LISP=os.path.join(FIFO, "lisp")))
    try:
        out, _ = p.communicate(timeout=limit)
        status = "ok" if p.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        subprocess.run(["pkill", "-KILL", "-f", cwd + "/"])
        status = "timeout"
    return status, round(time.time() - t, 2), out


def one(bench, name, pddl, domain, H, slack, method, a):
    work = os.path.join(SCRATCH, bench, f"{name}-s{slack}-{method}")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(pddl, work)
    cmd = ["bash", PLANNER, os.path.basename(pddl), "--weighted-solver", "EvalMaxSAT_bin",
           "--numslices", str(H + slack), "--timeout", str(a.limit)]
    if domain:
        cmd += ["--domain", domain]
    if method != "full":
        cmd += ["--restrict", method]
    status, wall, out = run(cmd, work, a.limit + 120)
    rec = dict(bench=bench, name=name, size=int(re.match(r"grid(\d+)x", name).group(1)),
               shortest=H, slack=slack, horizon=H + slack, method=method, status=status,
               wall_s=wall, started=time.strftime("%Y-%m-%dT%H:%M:%S"))
    m = re.findall(r"time slices: cost ([0-9.]+)", out)
    if status == "ok" and m:
        rec["cost"] = float(m[-1])
        rec["stopped_early"] = "stopped after the" in out
        s = re.search(r"the SAT plan \((\d+) actions\) as found: cost ([0-9.]+)", out)
        if s:
            rec["sat_actions"], rec["sat_cost"] = int(s.group(1)), float(s.group(2))
        s = re.search(r"(\d+) of (\d+) action atoms allowed", out)
        if s:
            rec["allowed"], rec["action_atoms"] = int(s.group(1)), int(s.group(2))
        sa = os.path.join(work, name + "-restrict-sat.answer")
        if os.path.exists(sa):
            rec["sat_plan"] = sorted(l.strip() for l in open(sa) if l.startswith("(OCCURS "))
        ans = os.path.join(work, name + ".answer")
        rec["actions"] = sum(1 for l in open(ans) if l.startswith("(OCCURS ")) if os.path.exists(ans) else None
    else:
        if status == "ok":
            rec["status"] = "failed"
        rec["log_tail"] = out[-1500:].splitlines()[-10:]
    shutil.rmtree(work, ignore_errors=True)
    with LOCK:
        with open(a.results, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  {name} +{slack} {method:7s} {rec['status']:7s} {wall:7.1f}s "
              f"cost={rec.get('cost', '-')} sat={rec.get('sat_cost', '-')}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", choices=("SimpleGrid", "TwoPackage", "ThreePackage"))
    ap.add_argument("--sizes", type=int, nargs="*")
    ap.add_argument("--slack", type=int, nargs="*", default=[0, 4])
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int, default=1800, help="seconds per MaxSAT solve (and run)")
    ap.add_argument("--results")
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    a.results = a.results or os.path.join(HERE, "results", a.bench + ".jsonl")
    done = set()
    if os.path.exists(a.results):
        for l in open(a.results):
            r = json.loads(l)
            done.add((r["name"], r["slack"], r["method"]))
    jobs = [(a.bench, n, p, d, H, s, m) for n, p, d, H in goals(a.bench, a.sizes)
            for s in a.slack for m in METHODS if (n, s, m) not in done]
    # cheap first: small grids and short horizons
    jobs.sort(key=lambda j: (int(re.match(r"grid(\d+)x", j[1]).group(1)), j[4] + j[5], j[1]))
    print(f"{a.bench}: {len(jobs)} runs, {a.jobs} at a time", flush=True)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(lambda j: one(*j, a), jobs))
    print("done", flush=True)


if __name__ == "__main__":
    main()
