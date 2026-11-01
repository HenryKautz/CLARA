#!/usr/bin/env python3
"""run-plans.py --stage general|goals [--limit S] [--solver NAME] [--sizes N...]

Plans the FourPackage problems with planner.sh and the chosen MaxSAT solver, size
by size, stopping a stage after the first size where a run hits the limit.

  --stage general   each problem as posed (the 12-way disjunctive goal, every
                    goal a preference of utility 8), from its shortest horizon
                    (fpcommon.goal_horizon, the closest goal): planner.sh
                    --minslices H.  Keeps general/NAME.{answer,wff,wcnf,map}:
                    the plan and the problem in FiFO and weighted-CNF form.
  --stage goals     for each problem and each of its 12 goal literals (at P D):
                    goals/NAME-P-D.pddl, the problem with the hard goal clamped to
                    that literal (the preferences kept), planned at exactly its
                    shortest horizon (--numslices); then the plan's first K
                    actions, K = 2, 4, 8 where the plan is that long, as evidence:
                    evidence/NAME-P-D-obsK.txt (pinned to time steps, for
                    recognize.sh --evidence-kind fifo) and -ordK.txt (an ordering
                    only).

Every run is bounded as a whole (--limit, default 1200 s, wall clock): FiFO's
instantiation is not a solver run, so planner.sh --timeout alone would not stop
it.  The process group is killed at the limit.  One JSON record per run goes to
results/plans.jsonl; a run already recorded ok (or timed out at >= this limit) is
skipped, so the script resumes.
"""
import argparse, concurrent.futures as cf, glob, json, os, re, shutil, signal, subprocess, sys, threading, time
import fpcommon as F

RESULTS = os.path.join(F.HERE, "results", "plans.jsonl")
# Scratch root; FP_WORK gives a second, concurrent run its own (a timeout kills
# every process whose command line names a run's directory under it).
WORK = os.environ.get("FP_WORK", os.path.join(F.SCRATCH, "fp-plans"))


class Budget:
    """Runs share BUDGET predicted clauses (about 1 GB of SBCL heap per million):
    a run waits until its share is free; one larger than the whole budget runs alone."""
    def __init__(self, total):
        self.total, self.used, self.cv = total, 0, threading.Condition()

    def run(self, cost, fn, *args):
        cost = min(cost, self.total)
        with self.cv:
            self.cv.wait_for(lambda: self.used + cost <= self.total)
            self.used += cost
        try:
            return fn(*args)
        finally:
            with self.cv:
                self.used -= cost
                self.cv.notify_all()


def jobs_for(n):
    """Runs at once, by grid size: the theories grow about as n^4 per slice."""
    return 6 if n <= 8 else 4 if n <= 10 else 2 if n <= 12 else 1


EXACT = {"wmaxcdcl", "EvalMaxSAT_bin", "rc2"}
ENCODING = F.encoding()


def done_before(limit, solver, same_encoding=False):
    """Runs not to repeat: ok ones, and timeouts at >= LIMIT with the same solver.
    With SAME_ENCODING, only runs made with the installed FiFO's encoding count
    (a record without the field predates MUTEX: "pairs")."""
    seen = {}
    if os.path.exists(RESULTS):
        for line in open(RESULTS):
            r = json.loads(line)
            if same_encoding and r.get("encoding", "pairs") != ENCODING:
                continue
            if r["status"] == "ok" or (r["status"] == "timeout" and r["limit_s"] >= limit
                                       and r["solver"] == solver):
                seen[(r["stage"], r["name"])] = r
    return seen


def run(cmd, cwd, limit):
    """(status, wall seconds, output); status ok, failed or timeout."""
    t = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, env=F.env(), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=limit)
        status = "ok" if p.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            out, _ = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            out, _ = p.communicate()
        # FiFO runs each solver in a process group of its own, which the killpg
        # above misses: a solver killed out from under SBCL runs on, orphaned.
        # Every file it reads is in CWD, so its command line names it.
        subprocess.run(["pkill", "-KILL", "-f", cwd + "/"])
        status = "timeout"
    return status, time.time() - t, out


def wcnf_size(path):
    """(variables, clauses) of a weighted CNF in the h/weight format FiFO writes."""
    nv = nc = 0
    with open(path) as f:
        for line in f:
            if line.startswith("c"):
                continue
            nc += 1
            for tok in line.split()[1:-1]:
                v = abs(int(tok))
                if v > nv:
                    nv = v
    return nv, nc


def planner_cmd(pddl, solver, limit, horizon_flag):
    """LIMIT is planner.sh --timeout: the cap on each solver run.  An anytime
    solver stopped at it reports its best plan (FiFO SIGTERMs it and reads it)."""
    return ["planner.sh", os.path.basename(pddl), "--domain", F.DOMAIN,
            "--weighted-solver", solver, "--timeout", str(limit)] + horizon_flag


def stopped_early(out):
    """True when planner.sh's MaxSAT run hit its --timeout: the plan is the
    solver's best, not a proven optimum."""
    return "stopped after the" in out and "reporting the best solution" in out


def parse_plan(out, answer):
    h = re.search(r"SOLVED with (\d+) time slices", out)
    cost = None
    if os.path.exists(answer):
        m = re.search(r"\(\*OBJECTIVE\* (\S+)\)", open(answer).read())
        cost = m.group(1) if m else None
    nact = sum(1 for l in open(answer) if l.startswith("(OCCURS ")) if os.path.exists(answer) else None
    return (int(h.group(1)) if h else None), cost, nact


def general(name, solver, limit):
    src = os.path.join(F.HERE, name + ".pddl")
    H = min(F.horizons(src).values())
    work = os.path.join(WORK, "general-" + name)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(src, work)
    status, wall, out = run(planner_cmd(src, solver, limit, ["--minslices", str(H), "--maxslices", str(H + 10)]),
                            work, limit)
    rec = dict(stage="general", name=name, size=F.size_of(name), solver=solver, limit_s=limit,
               status=status, wall_s=round(wall, 2), min_horizon=H, encoding=ENCODING)
    answer = os.path.join(work, name + ".answer")
    if status == "ok":
        rec["horizon"], rec["cost"], rec["actions"] = parse_plan(out, answer)
        if rec["horizon"] is None:
            rec["status"] = "failed"
    if rec["status"] == "ok":
        G = os.path.join(F.HERE, "general")
        os.makedirs(G, exist_ok=True)
        for ext in ("answer", "wff", "wcnf", "map"):
            shutil.copy(os.path.join(work, f"{name}.{ext}"), os.path.join(G, f"{name}.{ext}"))
        rec["wcnf_vars"], rec["wcnf_clauses"] = wcnf_size(os.path.join(G, name + ".wcnf"))
        for ext in ("pddl", "wff", "wcnf"):
            f = src if ext == "pddl" else os.path.join(G, f"{name}.{ext}")
            rec[f"{ext}_bytes"] = os.path.getsize(f)
    else:
        rec["log_tail"] = out[-1500:].splitlines()[-12:]
    shutil.rmtree(work, ignore_errors=True)
    return rec


def single_goal(src, problem, pkg, dest):
    """The problem with its hard goal clamped to (at PKG DEST); preferences kept."""
    text = open(src).read()
    lines = text.splitlines()
    out = [f";; {problem}-{pkg}-{dest}",
           f";; Clamped variant of {problem}.pddl: the hard goal is (at {pkg} {dest}) only;",
           ";; the 12 goal preferences (utility 8 each) are kept.", ""]
    skip = False
    for l in lines:
        if l.startswith(";;"):
            continue
        if l.startswith("(define (problem "):
            l = l[:-1] + f"-{pkg}-{dest})"
        if re.match(r"\s+\(or \(at ", l):
            l = re.sub(r"\(or .*\)$", f"(at {pkg} {dest})", l)
        out.append(l)
    return "\n".join(out).lstrip("\n").replace("\n\n\n", "\n\n") + "\n"


def write_evidence(g, actions):
    """Evidence from goals/G.answer's first K actions, K in F.KS up to the plan's
    length: obsK pinned to its slices, ordK their order only -- non-strict, since
    the two trucks act in parallel and a strict order would invent one.
    (ks, None) or (ks, error lines)."""
    ks = [k for k in F.KS if k <= actions]
    for k in ks:
        base = os.path.join("evidence", f"{g}-")
        for args in (["--recognition", "1", "--evidence", f"{base}obs{k}.txt"],
                     ["--ordering-evidence", f"{base}ord{k}.txt", "--nonstrict-ordering", "1"]):
            r = subprocess.run(["evgen.sh", "--problem", f"goals/{g}.pddl", "--domain",
                                os.path.basename(F.DOMAIN), "--slices", f"1-{k}",
                                "--observe", "drive,load,unload"] + args,
                               cwd=F.HERE, env=F.env(), capture_output=True, text=True)
            if r.returncode != 0:
                return ks, (r.stdout + r.stderr).splitlines()[-12:]
    return ks, None


predicted_clauses = F.predicted_clauses


def goal(name, pkg, dest, solver, limit, solver_limit, max_clauses):
    src = os.path.join(F.HERE, name + ".pddl")
    g = F.goal_name(name, pkg, dest)
    roads, at, _ = F.parse(src)
    H = F.goal_horizon(roads, at, pkg, dest)
    gp = os.path.join(F.HERE, "goals", g + ".pddl")
    os.makedirs(os.path.dirname(gp), exist_ok=True)
    open(gp, "w").write(single_goal(src, name, pkg, dest))
    n = F.size_of(name)
    if max_clauses and predicted_clauses(n, H) > max_clauses:
        # The problem file is written; planning it would only exhaust the heap.
        return dict(stage="goals", name=g, problem=name, size=n, goal=f"at-{pkg}-{dest}",
                    solver=solver, limit_s=limit, status="too-big", wall_s=0.0, horizon=H,
                    predicted_clauses=round(predicted_clauses(n, H)), encoding=ENCODING)
    work = os.path.join(WORK, "goal-" + g)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(gp, work)
    status, wall, out = run(planner_cmd(gp, solver, solver_limit, ["--numslices", str(H)]), work, limit)
    rec = dict(stage="goals", name=g, problem=name, size=F.size_of(name), goal=f"at-{pkg}-{dest}",
               solver=solver, limit_s=limit, solver_limit_s=solver_limit, status=status,
               wall_s=round(wall, 2), horizon=H, encoding=ENCODING)
    answer = os.path.join(work, g + ".answer")
    if status == "ok":
        h, rec["cost"], rec["actions"] = parse_plan(out, answer)
        rec["proved_optimal"] = solver in EXACT and not stopped_early(out)
        if h is None:
            rec["status"] = "failed"
    if rec["status"] == "ok":
        shutil.copy(answer, os.path.join(F.HERE, "goals", g + ".answer"))
        rec["evidence_k"], err = write_evidence(g, rec["actions"])
        if err:
            rec["status"], rec["log_tail"] = "failed", err
    else:
        rec["log_tail"] = out[-1500:].splitlines()[-12:]
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("general", "goals", "evidence"), required=True)
    ap.add_argument("--limit", type=int, default=1200)
    ap.add_argument("--solver-limit", type=int, help="planner.sh --timeout; default --limit")
    ap.add_argument("--solver")
    ap.add_argument("--sizes", type=int, nargs="*")
    ap.add_argument("--keep-going", action="store_true",
                    help="go on to larger sizes after a timeout (default: stop there)")
    ap.add_argument("--max-clauses", type=float,
                    help="goals: skip (status too-big) a goal whose predicted theory is larger")
    ap.add_argument("--budget", type=float, default=12,
                    help="goals: millions of predicted clauses planned at once (default 12)")
    ap.add_argument("--workers", type=int, default=6,
                    help="goals: most runs at once (default 6); each SBCL needs ~2.5 GB "
                         "plus ~1 GB per million clauses")
    ap.add_argument("--redo-other-encoding", action="store_true",
                    help="rerun what was recorded with a different SatPlan mutex encoding "
                         f"than the installed FiFO's ({ENCODING})")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    if a.stage == "evidence":
        # Rewrite the evidence of every goal planned ok, from its saved answer.
        recs = {}
        for line in open(RESULTS):
            r = json.loads(line)
            if r["stage"] == "goals" and r["status"] == "ok" and (not a.sizes or r["size"] in a.sizes):
                recs[r["name"]] = r
        for g, r in sorted(recs.items()):
            ks, err = write_evidence(g, r["actions"])
            print(f"  {g}: K={ks} {'failed: ' + ' | '.join(err[-2:]) if err else 'ok'}", flush=True)
        return
    if not a.solver:
        ap.error("--solver is required for --stage general|goals")
    solver_limit = a.solver_limit or a.limit
    seen = done_before(a.limit, a.solver, a.redo_other_encoding)
    for n in sorted({F.size_of(p) for p in F.problems(a.sizes)}):
        todo = []
        for p in F.problems([n]):
            if a.stage == "general":
                if ("general", p) not in seen:
                    todo.append((general, (p, a.solver, a.limit)))
            else:
                roads, at, goals = F.parse(os.path.join(F.HERE, p + ".pddl"))
                for pkg, dest in goals:
                    if ("goals", F.goal_name(p, pkg, dest)) not in seen:
                        cost = predicted_clauses(n, F.goal_horizon(roads, at, pkg, dest)) / 1e6
                        todo.append((goal, (p, pkg, dest, a.solver, a.limit, solver_limit,
                                            a.max_clauses), cost))
        # Largest first, so a big run is not starved of budget by a stream of small ones.
        todo.sort(key=lambda t: -t[2] if len(t) > 2 else 0)
        workers = a.workers if a.stage == "goals" else jobs_for(n)
        print(f"=== {time.strftime('%H:%M:%S')} {n}x{n}: {len(todo)} {a.stage} runs, "
              f"{workers} at a time" + (f" within {a.budget:g}M predicted clauses"
                                        if a.stage == "goals" else ""), flush=True)
        timeouts = [r for (st, nm), r in seen.items()
                    if st == a.stage and r["size"] == n and r["status"] == "timeout"]
        budget = Budget(a.budget)
        with cf.ThreadPoolExecutor(workers) as ex, open(RESULTS, "a") as log:
            futs = [ex.submit(budget.run, t[2], t[0], *t[1]) if len(t) > 2 else ex.submit(t[0], *t[1])
                    for t in todo]
            for f in cf.as_completed(futs):
                r = f.result()
                log.write(json.dumps(r) + "\n")
                log.flush()
                extra = f"H={r.get('horizon')} cost {r.get('cost')}" if r["status"] == "ok" else \
                        f"H={r['horizon']} ~{r['predicted_clauses'] / 1e6:.0f}M clauses" \
                        if r["status"] == "too-big" else " | ".join(r.get("log_tail", [])[-2:])
                print(f"  {r['name']}: {r['status']} {r['wall_s']:.1f}s {extra}", flush=True)
                if r["status"] == "timeout":
                    timeouts.append(r)
        if timeouts and not a.keep_going:
            print(f"{n}x{n}: {len(timeouts)} run(s) hit the {a.limit} s limit; "
                  "no larger size is tried at this limit", flush=True)
            break
    print("done", flush=True)


if __name__ == "__main__":
    main()
