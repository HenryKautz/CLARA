#!/usr/bin/env python3
"""choose-solver.py PROBLEM... -- which MaxSAT solver to plan FourPackage problems with.

For each problem: planner.sh with its defaults finds the smallest feasible horizon
H, then planner.sh --numslices H is run once per weighted (MaxSAT) solver FiFO
knows, one at a time so the timings do not compete.  Instantiation is the same in
every run, so the differences are the solvers'.  Prints and appends to
results/choose-solver.jsonl: problem, H, solver, wall time, cost, and whether the
cost is a proven optimum (exact solvers) or the best found (anytime ones).

Needs FiFO installed (planner.sh on PATH) and shims/sbcl, which this script puts
first on PATH (the default 1 GB SBCL heap is too small for these theories).
"""
import json, os, re, shutil, subprocess, sys, time
import fpcommon as F

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SCRIPTS)    # the FourPackage dataset
DOMAIN = os.path.join(HERE, "clara-logistics-handling.pddl")
SOLVERS = [("tt-open-wbo-inc-Glucose4_1", "anytime"), ("nuwls-c", "anytime"),
           ("wmaxcdcl", "exact"), ("EvalMaxSAT_bin", "exact"), ("rc2-maxsat.py", "exact")]
LIMIT = 600
ENV = dict(os.environ, PATH=os.path.join(SCRIPTS, "shims") + ":" + os.environ["PATH"],
           SBCL_REAL=shutil.which("sbcl"), SBCL_HEAP_MB="12288")


def plan(problem, work, extra):
    t = time.time()
    r = subprocess.run(["planner.sh", os.path.basename(problem), "--domain", DOMAIN,
                        "--timeout", str(LIMIT), "--maxslices", "200"] + extra,
                       cwd=work, env=ENV, capture_output=True, text=True)
    wall = time.time() - t
    out = r.stdout + r.stderr
    h = re.search(r"SOLVED with (\d+) time slices", out)
    c = re.search(r"\(\*OBJECTIVE\* (\S+)\)", out)
    return wall, (int(h.group(1)) if h else None), (c.group(1) if c else None), out


def main():
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    log = open(os.path.join(HERE, "results", "choose-solver.jsonl"), "a")
    for p in sys.argv[1:]:
        problem = os.path.abspath(p)
        name = os.path.basename(problem)[:-5]
        work = os.path.join(F.SCRATCH, "fp-choose", name)
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work)
        shutil.copy(problem, work)
        _, H, _, out = plan(problem, work, [])
        if H is None:
            print(f"{name}: no plan with the default solvers\n{out[-2000:]}", flush=True)
            continue
        for solver, kind in SOLVERS:
            wall, h, cost, out = plan(problem, work, ["--numslices", str(H), "--weighted-solver", solver])
            rec = dict(problem=name, horizon=H, solver=solver, kind=kind, limit_s=LIMIT,
                       wall_s=round(wall, 2), cost=cost, solved=h is not None)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print(f"{name} H={H} {solver:28s} {wall:8.1f}s cost {cost}", flush=True)


if __name__ == "__main__":
    main()
