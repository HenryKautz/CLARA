#!/usr/bin/env python3
"""plan-goals.py --family F [--jobs N] [--solver-limit S] [--plan-limit S]

Plan every goal variant goals/<goal>.pddl of family F (one per hypothesis),
smallest grid first, write the evidence cut from the plans, and, once all of a
problem's goals are planned, its recognition problem.

Each goal is planned twice, both by planner.sh (domain F/clara-logistics.pddl):

  tt    tt-open-wbo-inc-Glucose4_1 (anytime): planner.sh searches horizons
        upward with kissat for the SHORTEST feasible one, H, and minimises cost
        there.  In a family with the same world as its source (SimpleGrid,
        TwoPackage: common.Family.same_world) the search starts at the horizon
        the OldVersions plan of the same goal had, minus one (the feasible
        horizons did not change: the new domain only charges for load/unload
        and drops transfer, which needs two vehicles at one place).  That
        slice count must be UNSAT and the next SAT, which proves H shortest (a
        SatPlan plan stays a plan with an extra idle slice, so feasibility is
        monotone in the horizon).  If the first slice tried is already SAT the
        hint was wrong and the goal is planned again with the full search.  In
        a family whose roads changed (ThreePackage and FourPackage without
        knockout, TwoPackageOneway) the old horizons are no guide, so there is
        no hint and the search is the full one from the start.
        -> goals/<goal>-tt.answer
  eval  EvalMaxSAT_bin (exact) at the same H (--numslices H): ok only when it
        PROVES its optimum within the solver limit.  -> goals/<goal>-eval.answer

The plan the evidence is cut from, goals/<goal>.answer, is EvalMaxSAT's when it
succeeded, else tt-open-wbo's (record field "plan_from").  Each solver call
gets --solver-limit seconds (planner.sh --timeout: every kissat call of the
search and the MaxSAT solve), each planner.sh run --plan-limit seconds of wall
time.

STOP RULE, per solver: when a run of it fails by timeout (its own solver limit
or the run's wall limit) or memory, that solver is stopped at that grid size:
its runs still going at that size or larger are killed (status "killed") and
none is started there or larger.  A goal whose eval run is stopped or killed
uses its tt plan; a goal with no tt plan has no plan, and its problem gets no
recognition problem.

Evidence, pinned to time steps, ONE (and ...) form each (recognize.sh
--evidence-kind fifo):
  evidence/<problem>-none.txt        (and) -- no observations
  evidence/<goal>-obs25.txt          the plan's first ceil(25%) of its actions
  evidence/<goal>-obs100.txt         all of the plan's actions
"Actions", not time steps: the plan's actions sorted by step, the first K taken.

recognition/<problem>.pddl: the goal as the disjunction of the hypotheses, its
RECOGNITION HORIZON in the header: the largest of its goals' shortest horizons.

Records (results/plans.jsonl): stage tt / eval (one per run), goal (the plan
chosen), problem, size (all of a size settled), end.  A run recorded ok is not
repeated; a stopped solver stays stopped on a rerun (same or longer limits).
"""
import argparse, os, re, shutil, time
import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--family", required=True)
ap.add_argument("--jobs", type=int, default=12)
ap.add_argument("--solver-limit", type=int, default=1800, help="seconds per solver call")
ap.add_argument("--plan-limit", type=int, default=6 * 3600, help="wall seconds per planner.sh run")
ap.add_argument("--max-slices", type=int, default=200)
ap.add_argument("--reserve-gb", type=float, default=24.0,
                help="start no run while less than this is available")
ap.add_argument("--min-free-gb", type=float, default=6.0,
                help="kill the largest run (memout) when less than this is available")
ap.add_argument("--sizes", type=int, nargs="*")
A = ap.parse_args()

FAM = C.Family(A.family)
PLANS = os.path.join(FAM.results, "plans.jsonl")
WORK = os.path.join(FAM.scratch, "plans")
SIZES = A.sizes or FAM.sizes


def record(rec):
    C.append_jsonl(PLANS, rec)
    extra = " ".join(f"{k}={rec[k]}" for k in ("horizon", "cost", "actions", "plan_from", "recognition_horizon")
                     if k in rec)
    C.say(f"{rec['stage']:7s} {rec.get('status', ''):8s} {rec['name']} "
          f"{rec.get('wall_s', '')}{'s' if 'wall_s' in rec else ''} {extra}")


def old_horizon(problem, hyp):
    """The shortest horizon of the same goal in OldVersions, if it was planned
    and the family's world is the old one (no hint when the roads changed)."""
    if not FAM.same_world:
        return None
    names = [hyp.goal]
    if FAM.name == "SimpleGrid":            # old name: <problem>-<place>
        names.append(f"{problem}-{hyp.lits[0][1]}")
    for n in names:
        p = os.path.join(FAM.old, "goals", n + ".answer")
        if os.path.exists(p):
            return C.answer_horizon(p)
    return None


class Task:
    def __init__(self, solver, problem, hyp, minslices=None, numslices=None):
        self.solver, self.problem, self.hyp = solver, problem, hyp
        self.size = C.size_of(problem)
        self.minslices, self.numslices = minslices, numslices

    def key(self):
        return (self.size, self.problem, self.hyp.index, self.solver)

    def start(self):
        g = self.hyp.goal
        work = os.path.join(WORK, f"{g}-{self.solver}")
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work)
        shutil.copy(FAM.path("goals", g + ".pddl"), work)
        cmd = ["planner.sh", g + ".pddl", "--domain", FAM.domain,
               "--timeout", str(A.solver_limit)]
        if self.solver == "tt":
            cmd += ["--weighted-solver", C.TT, "--maxslices", str(A.max_slices)]
            if self.minslices:
                cmd += ["--minslices", str(self.minslices)]
        else:
            cmd += ["--weighted-solver", C.EVAL, "--numslices", str(self.numslices)]
        self.work = work
        self.run = C.Run(self, cmd, work, A.plan_limit)
        return self.run


def finish(task, status):
    """The record of a finished or killed run; on success the answer is saved."""
    run, g = task.run, task.hyp.goal
    out = run.output()
    rec = dict(stage=task.solver, name=g, problem=task.problem, size=task.size,
               hypothesis=task.hyp.name, index=task.hyp.index,
               solver=C.TT if task.solver == "tt" else C.EVAL,
               solver_limit_s=A.solver_limit, **run.base_record())
    if task.minslices:
        rec["minslices"] = task.minslices
    stopped = "stopped after the" in out
    if status == "ok":
        status = run.classify()
    answer = os.path.join(task.work, g + ".answer")
    h = re.search(r"SOLVED with (\d+) time slices", out)
    if status == "ok" and h and os.path.exists(answer):
        rec["horizon"] = int(h.group(1))
        m = re.search(r"\(\*OBJECTIVE\* (\S+)\)", open(answer).read())
        rec["cost"] = float(m.group(1)) if m else None
        rec["actions"] = len(C.plan_actions(answer))
        rec["solver_stopped"] = stopped
        if task.solver == "eval" and stopped:
            status = "timeout"           # EvalMaxSAT did not prove its optimum
        if task.solver == "tt" and task.minslices and rec["horizon"] == task.minslices:
            status = "hint-sat"          # the hint's H-1 was feasible: search again
        if status == "ok":
            shutil.copy(answer, FAM.path("goals", f"{g}-{task.solver}.answer"))
    elif status == "ok":
        status = "failed"
    if status == "failed" and stopped:
        status = "timeout"               # a kissat call hit the solver limit
    rec["status"] = status
    if status != "ok":
        rec["log_tail"] = C.log_tail(out)
    shutil.rmtree(task.work, ignore_errors=True)
    return rec


def write_evidence(problem, hyp, answer, source):
    os.makedirs(FAM.path("evidence"), exist_ok=True)
    acts = C.plan_actions(answer)
    ks = {}
    for pct in C.EVIDENCE_FRACTIONS:
        k = C.evidence_count(len(acts), pct)
        ks[pct] = k
        head = [f";; {hyp.goal}: {'all' if pct == 100 else f'the first {k}'} of the {len(acts)} actions"
                f" of goals/{hyp.goal}.answer",
                f";; ({pct}%, rounded up), a plan for {hyp.formula()} by {source}.",
                f";; True hypothesis: {hyp.name}.  Each action is pinned to its time step;",
                ";; ONE (and ...) form, for recognize.sh --evidence-kind fifo.",
                ";; Written by scripts/plan-goals.py.", "", "(and"]
        with open(FAM.path("evidence", f"{hyp.goal}-obs{pct}.txt"), "w") as f:
            f.write("\n".join(head) + "\n" + "\n".join(f"  (occurs {a} {s})" for s, a in acts[:k]) + ")\n")
    return len(acts), ks


def main():
    os.makedirs(FAM.results, exist_ok=True)
    os.makedirs(FAM.path("recognition"), exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    recs = C.load_jsonl(PLANS)
    ok = {(r["stage"], r["name"]): r for r in recs if r["stage"] in ("tt", "eval") and r["status"] == "ok"}
    settled_eval = {r["name"] for r in recs if r["stage"] == "eval"
                    and r["status"] in ("ok", "timeout", "memout", "failed", "killed")}
    stopped = {}                  # solver -> smallest size where it failed
    for r in recs:
        if r["stage"] in ("tt", "eval") and r["status"] in ("timeout", "memout") \
                and r["solver_limit_s"] >= A.solver_limit and r["limit_s"] >= A.plan_limit:
            stopped[r["stage"]] = min(stopped.get(r["stage"], 99), r["size"])

    problems = FAM.problems(SIZES)
    hyps = {p: FAM.hypotheses(p) for p in problems}
    pending = []
    for p in problems:
        for h in hyps[p]:
            if ("tt", h.goal) not in ok:
                oh = old_horizon(p, h)
                pending.append(Task("tt", p, h, minslices=oh - 1 if oh and oh > 1 else None))
            elif h.goal not in settled_eval:
                pending.append(Task("eval", p, h, numslices=ok[("tt", h.goal)]["horizon"]))
    running = []
    reserve, min_free = A.reserve_gb * 2**30, A.min_free_gb * 2**30
    C.say(f"{FAM.name}: {len(problems)} problems, {sum(map(len, hyps.values()))} goals, "
          f"{len(pending)} runs to do, {A.jobs} at a time; stopped: {stopped}")
    done_problems = {r["name"] for r in recs if r["stage"] == "problem"}
    done_sizes = {r["size"] for r in recs if r["stage"] == "size"}

    def allowed(t):
        return t.size < stopped.get(t.solver, 99)

    def settle():
        """Choose plans, write evidence and recognition problems, and mark
        sizes settled, for whatever has become final."""
        busy = {(t.problem) for t in running} | {t.problem for t in pending if allowed(t)}
        for p in problems:
            if p in done_problems or p in busy:
                continue
            chosen, horizons = {}, {}
            for h in hyps[p]:
                tt, ev = ok.get(("tt", h.goal)), ok.get(("eval", h.goal))
                if not tt:
                    continue
                src = "eval" if ev else "tt"
                rec = ev or tt
                shutil.copy(FAM.path("goals", f"{h.goal}-{src}.answer"), FAM.path("goals", h.goal + ".answer"))
                n, ks = write_evidence(p, h, FAM.path("goals", h.goal + ".answer"),
                                       C.EVAL if ev else C.TT + " (EvalMaxSAT_bin did not prove an optimum)")
                record(dict(stage="goal", name=h.goal, problem=p, size=C.size_of(p),
                            hypothesis=h.name, plan_from=src, horizon=rec["horizon"], cost=rec["cost"],
                            tt_cost=tt["cost"], eval_cost=ev["cost"] if ev else None,
                            actions=n, evidence_k=ks, started=C.now()))
                chosen[h.goal], horizons[h.goal] = rec, rec["horizon"]
            prec = dict(stage="problem", name=p, size=C.size_of(p), started=C.now())
            if len(chosen) == len(hyps[p]):
                H = max(horizons.values())
                open(FAM.recognition_problem(p), "w").write(
                    C.recognition_text(FAM, p, H, horizons, hyps[p]))
                open(FAM.path("evidence", p + "-none.txt"), "w").write(
                    f";; {p}: no observations.  Written by scripts/plan-goals.py.\n\n(and)\n")
                prec.update(status="ok", recognition_horizon=H, horizons=[horizons[h.goal] for h in hyps[p]],
                            plans_from=[("eval" if ("eval", h.goal) in ok else "tt") for h in hyps[p]])
            else:
                prec.update(status="incomplete", missing=[h.goal for h in hyps[p] if h.goal not in chosen])
            record(prec)
            done_problems.add(p)
        for s in SIZES:
            if s not in done_sizes and all(problem in done_problems for problem in problems
                                           if C.size_of(problem) == s):
                record(dict(stage="size", name=f"{s}x{s}", size=s, status="settled", started=C.now()))
                done_sizes.add(s)

    def stop(solver, size):
        if size >= stopped.get(solver, 99):
            return
        stopped[solver] = size
        victims = [t for t in running if t.solver == solver and t.size >= size]
        C.say(f"    {solver} stopped at {size}x{size}: killing {len(victims)} run(s) at that size or larger")
        for v in victims:
            v.run.kill()
            running.remove(v)
            r = finish(v, "killed")
            record(r)
        for t in [t for t in pending if t.solver == solver and t.size >= size]:
            pending.remove(t)

    settle()
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
                ok[(t.solver, t.hyp.goal)] = rec
                if t.solver == "tt":
                    pending.append(Task("eval", t.problem, t.hyp, numslices=rec["horizon"]))
            elif rec["status"] == "hint-sat":
                pending.append(Task("tt", t.problem, t.hyp))
            elif rec["status"] in ("timeout", "memout"):
                stop(t.solver, t.size)
        settle()
    settle()
    record(dict(stage="end", name=FAM.name, stopped=stopped, started=C.now()))


if __name__ == "__main__":
    main()
