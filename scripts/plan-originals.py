#!/usr/bin/env python3
"""plan-originals.py --family F [--jobs N] [--solver-limit S] [--plan-limit S]
                    [--check-only]

Plan family F's ORIGINAL problems <F>/gridNxN-K.pddl directly -- their goal is
the disjunction of the hypotheses, so any one hypothesis achieved is a plan --
smallest grid first, with no evidence.  goals/, recognition/, evidence/ and
circuits/ are not touched.

Each problem P is planned twice by planner.sh (domain F/clara-logistics.pddl):

  tt    tt-open-wbo-inc-Glucose4_1 (anytime), --maxslices 200 --longer 4:
        planner.sh searches horizons upward with kissat for the shortest
        feasible one, H0 (no --minslices hint: the originals were never planned
        before), then minimises cost at each of H0..H0+4 and keeps the cheapest
        plan.  A longer horizon can admit a cheaper plan: H0 is set by the
        QUICKEST hypothesis, which need not be the cheapest.
        -> <F>/<P>-tt.answer
  eval  EvalMaxSAT_bin (exact), --numslices H0 --longer 4: phase 1 only
        confirms H0, then cost is minimised at H0..H0+4 and the cheapest plan
        kept.  ok only when EvalMaxSAT PROVED its optimum at EVERY one of those
        horizons (no "stopped after the" anywhere in the output); otherwise the
        run is a timeout, not a plan.  -> <F>/<P>-eval.answer

Each solver call gets --solver-limit seconds (planner.sh --timeout), each
planner.sh run --plan-limit seconds of wall time.  The default plan limit is
24 h, not plan-goals.py's 6 h: a run makes up to five MaxSAT solves (each up to
the 1800 s solver limit) on problems whose horizons are up to 4 slices longer
than a goal's, so 5 x 1800 s of solving plus instantiating five horizons must
fit, with room for the kissat search.

STOP RULE, per solver, as in plan-goals.py: when a run of it fails by timeout
(its own solver limit or the run's wall limit) or memory at some grid size,
its runs still going at that size or larger are killed (status "killed") and
none is started there or larger.

Records (results/originals.jsonl), one per run: stage tt / eval, the fields of
plans.jsonl plus shortest_horizon (H0, from planner.sh's "Cheapest plan over
H0..H0+4 slices" line), longer (4) and true_cost (that line's cost).  A run
recorded ok is not repeated; a stopped solver stays stopped on a rerun (same
or longer limits).  At the end, stage "check" per problem compares the plans
with the goal plans of results/plans.jsonl (any goal plan also solves the
original):
  - H0 must equal the smallest shortest horizon among the problem's goals
    (only "<=" can be checked when some goal has no plan);
  - the eval cost must be <= the cost of every goal plan (tt or eval) whose
    horizon lies in H0..H0+4, and <= the tt cost (same horizons).
Only records made with the current --longer count, for resuming and checking.
--check-only writes just those records (and prints the violations).
"""
import argparse, os, re, shutil, time
import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--family", required=True)
ap.add_argument("--jobs", type=int, default=12)
ap.add_argument("--solver-limit", type=int, default=1800, help="seconds per solver call")
ap.add_argument("--plan-limit", type=int, default=24 * 3600, help="wall seconds per planner.sh run")
ap.add_argument("--max-slices", type=int, default=200)
ap.add_argument("--longer", type=int, default=4)
ap.add_argument("--reserve-gb", type=float, default=24.0,
                help="start no run while less than this is available")
ap.add_argument("--min-free-gb", type=float, default=6.0,
                help="kill the largest run (memout) when less than this is available")
ap.add_argument("--sizes", type=int, nargs="*")
ap.add_argument("--check-only", action="store_true")
A = ap.parse_args()
if A.longer < 1:
    # planner.sh prints the "Cheapest plan over H0..H0+K" line (where H0 is read
    # from) only when K > 0
    ap.error("--longer must be at least 1")

FAM = C.Family(A.family)
OUT = os.path.join(FAM.results, "originals.jsonl")
WORK = os.path.join(FAM.scratch, "originals")
SIZES = A.sizes or FAM.sizes


def record(rec):
    C.append_jsonl(OUT, rec)
    extra = " ".join(f"{k}={rec[k]}" for k in ("shortest_horizon", "horizon", "cost", "actions")
                     if k in rec)
    C.say(f"{rec['stage']:6s} {rec.get('status', ''):9s} {rec['name']} "
          f"{rec.get('wall_s', '')}{'s' if 'wall_s' in rec else ''} {extra}")


class Task:
    def __init__(self, solver, problem, numslices=None):
        self.solver, self.problem, self.numslices = solver, problem, numslices
        self.size = C.size_of(problem)

    def key(self):
        return (self.size, self.problem, self.solver)

    def start(self):
        p = self.problem
        work = os.path.join(WORK, f"{p}-{self.solver}")
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work)
        shutil.copy(FAM.path(p + ".pddl"), work)
        cmd = ["planner.sh", p + ".pddl", "--domain", FAM.domain,
               "--longer", str(A.longer), "--timeout", str(A.solver_limit)]
        if self.solver == "tt":
            cmd += ["--weighted-solver", C.TT, "--maxslices", str(A.max_slices)]
        else:
            cmd += ["--weighted-solver", C.EVAL, "--numslices", str(self.numslices)]
        self.work = work
        self.run = C.Run(self, cmd, work, A.plan_limit)
        return self.run


def finish(task, status):
    """The record of a finished or killed run; on success the answer is saved
    beside the problem as <P>-<solver>.answer."""
    run, p = task.run, task.problem
    out = run.output()
    rec = dict(stage=task.solver, name=p, problem=p, size=task.size,
               solver=C.TT if task.solver == "tt" else C.EVAL,
               solver_limit_s=A.solver_limit, longer=A.longer, **run.base_record())
    if task.numslices:
        rec["numslices"] = task.numslices
    stopped = "stopped after the" in out
    if status == "ok":
        status = run.classify()
    answer = os.path.join(task.work, p + ".answer")
    h = re.search(r"SOLVED with (\d+) time slices", out)
    cheap = re.search(r"Cheapest plan over (\d+)\.\.(\d+) slices: cost (\S+) at (\d+) slices", out)
    if status == "ok" and h and cheap and os.path.exists(answer):
        rec["shortest_horizon"] = int(cheap.group(1))
        rec["horizon"] = int(h.group(1))
        m = re.search(r"\(\*OBJECTIVE\* (\S+)\)", open(answer).read())
        rec["cost"] = float(m.group(1)) if m else None
        rec["true_cost"] = float(cheap.group(3))
        rec["actions"] = len(C.plan_actions(answer))
        rec["solver_stopped"] = stopped
        rec["horizon_costs"] = {int(n): (None if c == "(none)" else float(c)) for n, c in
                                re.findall(r"^  (\d+) time slices: cost (\S+)", out, re.M)}
        if rec["cost"] is None:
            status = "failed"            # an answer with no objective is not a costed plan
        elif task.solver == "eval" and stopped:
            status = "timeout"           # EvalMaxSAT did not prove an optimum at some horizon
        if status == "ok":
            shutil.copy(answer, FAM.path(f"{p}-{task.solver}.answer"))
    elif status == "ok":
        status = "failed"
    if status == "failed" and stopped:
        status = "timeout"               # a kissat or MaxSAT call hit the solver limit
    if task.solver == "eval" and "shortest_horizon" in rec and rec["shortest_horizon"] != task.numslices:
        # cannot happen with --numslices; never trust it -- and it is no timeout,
        # so it must not fire the stop rule
        status = "h0-mismatch"
    rec["status"] = status
    if status != "ok":
        rec["log_tail"] = C.log_tail(out)
    shutil.rmtree(task.work, ignore_errors=True)
    return rec


def last_ok(recs, stage, longer=None):
    """{name: last ok record of STAGE}; with LONGER, only records made with that
    --longer (runs with another window are a different experiment)."""
    out = {}
    for r in recs:
        if r["stage"] == stage and r["status"] == "ok" and (longer is None or r.get("longer") == longer):
            out[r["name"]] = r
    return out


def check():
    """One "check" record per problem planned: the originals against the goal
    plans of plans.jsonl.  Returns the violations."""
    recs = C.load_jsonl(OUT)
    tt, ev = last_ok(recs, "tt", A.longer), last_ok(recs, "eval", A.longer)
    goals = C.load_jsonl(os.path.join(FAM.results, "plans.jsonl"))
    gtt, gev = last_ok(goals, "tt"), last_ok(goals, "eval")
    bad = []
    for p in FAM.problems(SIZES):
        if p not in tt:
            continue
        hyps = FAM.hypotheses(p)
        H0 = tt[p]["shortest_horizon"]
        lo, hi = H0, H0 + A.longer
        planned = [gtt[h.goal]["horizon"] for h in hyps if h.goal in gtt]
        complete = len(planned) == len(hyps)
        rec = dict(stage="check", name=p, problem=p, size=C.size_of(p), shortest_horizon=H0,
                   longer=A.longer, goals=len(hyps), goals_planned=len(planned), started=C.now())
        problems = []
        if planned:
            gmin = min(planned)
            rec["goal_min_horizon"] = gmin
            if complete and H0 != gmin:
                problems.append(f"H0 {H0} != smallest goal shortest horizon {gmin}")
            if not complete and H0 > gmin:
                problems.append(f"H0 {H0} > smallest planned goal shortest horizon {gmin}")
        if p in ev:
            if ev[p]["shortest_horizon"] != H0:
                problems.append(f"eval H0 {ev[p]['shortest_horizon']} != tt H0 {H0}")
            c = ev[p]["cost"]
            rec["eval_cost"] = c
            # the anytime plan covers the same horizons H0..H0+longer, so it can
            # never beat the proved optimum
            if tt[p]["cost"] is not None and c > tt[p]["cost"] + 1e-9:
                problems.append(f"eval cost {c} > tt cost {tt[p]['cost']} over the same horizons")
            cmp = []
            for h in hyps:
                for kind, table in (("tt", gtt), ("eval", gev)):
                    g = table.get(h.goal)
                    if g and lo <= g["horizon"] <= hi and g.get("cost") is not None:
                        cmp.append((g["cost"], f"{h.goal}-{kind}", g["horizon"]))
                        if c > g["cost"] + 1e-9:
                            problems.append(f"eval cost {c} > goal plan {h.goal}-{kind} "
                                            f"cost {g['cost']} at horizon {g['horizon']}")
            rec["goal_plans_compared"] = len(cmp)
            if cmp:
                rec["cheapest_goal_plan"] = min(cmp)[1:] + (min(cmp)[0],)
        rec["tt_cost"] = tt[p]["cost"]
        rec["status"] = "violation" if problems else "ok"
        if problems:
            rec["violations"] = problems
            bad.append((p, problems))
        record(rec)
    return bad


def main():
    os.makedirs(FAM.results, exist_ok=True)
    if A.check_only:
        bad = check()
        C.say(f"{FAM.name}: {len(bad)} problem(s) with violations")
        for p, v in bad:
            C.say(f"  VIOLATION {p}: " + "; ".join(v))
        return
    os.makedirs(WORK, exist_ok=True)
    # only records made with this --longer count: another window is another experiment
    recs = [r for r in C.load_jsonl(OUT) if r["stage"] not in ("tt", "eval") or r.get("longer") == A.longer]
    ok = {(r["stage"], r["name"]): r for r in recs if r["stage"] in ("tt", "eval") and r["status"] == "ok"}
    # an ok eval is never repeated; a failed one is, if the limits are now larger
    settled_eval = {r["name"] for r in recs if r["stage"] == "eval" and
                    (r["status"] == "ok" or
                     (r["status"] in ("timeout", "memout", "failed", "killed", "h0-mismatch")
                      and r["solver_limit_s"] >= A.solver_limit and r["limit_s"] >= A.plan_limit))}
    stopped = {}                  # solver -> smallest size where it failed
    for r in recs:
        if r["stage"] in ("tt", "eval") and r["status"] in ("timeout", "memout") \
                and r["solver_limit_s"] >= A.solver_limit and r["limit_s"] >= A.plan_limit:
            stopped[r["stage"]] = min(stopped.get(r["stage"], 99), r["size"])

    problems = FAM.problems(SIZES)
    pending = []
    for p in problems:
        if ("tt", p) not in ok:
            pending.append(Task("tt", p))
        elif p not in settled_eval:
            pending.append(Task("eval", p, numslices=ok[("tt", p)]["shortest_horizon"]))
    running = []
    reserve, min_free = A.reserve_gb * 2**30, A.min_free_gb * 2**30
    C.say(f"{FAM.name}: {len(problems)} problems, {len(pending)} runs to do, {A.jobs} at a time, "
          f"--longer {A.longer}, solver limit {A.solver_limit} s, plan limit {A.plan_limit} s; "
          f"stopped: {stopped}")

    def allowed(t):
        return t.size < stopped.get(t.solver, 99)

    def stop(solver, size):
        if size >= stopped.get(solver, 99):
            return
        stopped[solver] = size
        victims = [t for t in running if t.solver == solver and t.size >= size]
        C.say(f"    {solver} stopped at {size}x{size}: killing {len(victims)} run(s) at that size or larger")
        for v in victims:
            v.run.kill()
            running.remove(v)
            record(finish(v, "killed"))
        for t in [t for t in pending if t.solver == solver and t.size >= size]:
            pending.remove(t)

    while pending or running:
        pending[:] = [t for t in pending if allowed(t)]
        pending.sort(key=Task.key)
        while pending and len(running) < A.jobs and (not running or C.available_bytes() >= reserve):
            t = pending.pop(0)
            t.start()
            running.append(t)
            time.sleep(1)
        time.sleep(5)
        table = C.process_table()
        for t in running:
            t.run.peak_kb = max(t.run.peak_kb, C.tree_rss_kb(t.run.proc.pid, table))
        victim = None
        if running and C.available_bytes() < min_free:
            victim = max(running, key=lambda t: C.tree_rss_kb(t.run.proc.pid, table))
        for t in list(running):
            if t not in running:
                continue
            if t.run.poll():
                rec = finish(t, "ok")
            elif t.run.over() or t is victim:
                t.run.kill()
                rec = finish(t, "timeout" if t is not victim else "memout")
            else:
                continue
            running.remove(t)
            record(rec)
            if rec["status"] == "ok":
                ok[(t.solver, t.problem)] = rec
                if t.solver == "tt":
                    pending.append(Task("eval", t.problem, numslices=rec["shortest_horizon"]))
            elif rec["status"] in ("timeout", "memout"):
                stop(t.solver, t.size)
    bad = check()
    record(dict(stage="end", name=FAM.name, stopped=stopped, violations=len(bad), started=C.now()))
    for p, v in bad:
        C.say(f"  VIOLATION {p}: " + "; ".join(v))


if __name__ == "__main__":
    main()
