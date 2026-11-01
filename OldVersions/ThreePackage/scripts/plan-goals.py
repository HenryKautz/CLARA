#!/usr/bin/env python3
"""plan-goals.py [--jobs N] [--limit S] [--sizes N...]

For each problem gridNxN-K.pddl and each of its 8 goal combinations (tpcommon):

  goals/<combo>.pddl     the problem with the goal (and (at pkg1 a) (at pkg2 c)
                         (at pkg3 e)) -- that combination as a hard goal
  goals/<combo>.answer   an optimal plan for it at its SHORTEST horizon:
                         planner.sh searches horizons upward from its
                         reachability bound with kissat, takes the first
                         satisfiable one, and minimises cost there with an
                         exact MaxSAT solver (--solver, default EvalMaxSAT_bin;
                         the first 26 5x5 goals were planned with WMaxCDCL,
                         which then failed to finish within 1800 s at
                         horizons 24-27 -- see the solver field).  Seven
                         goals at 6x6-7x7 (horizons 31-38) got no plan from
                         EvalMaxSAT within 3600 s; they were then planned
                         with --restrict actions at the horizon found
                         (solver "EvalMaxSAT_bin --restrict actions",
                         proved_optimal false)
  evidence/<combo>-obsK.txt   the plan's first K actions (K = 4, 8), each pinned
                         to its time step, as ONE (and ...) form -- for
                         recognize.sh --evidence-kind fifo
  evidence/<combo>-ordK.txt   the same K actions as ONE
                         (occur-in-nonstrict-order ...) form: their order only,
                         and non-strict because a load and an unload can share a
                         step -- for recognize.sh --evidence-kind pddl

"First K actions" is exact: the plan's actions sorted by time step, the first K
taken, even when the K-th shares its step with an action that is not taken.

Once a problem's 8 goals are planned:

  recognition/gridNxN-K.pddl   the problem with its goal rewritten as the
                         disjunction of the 8 combinations (the same plans), in
                         tpcommon.combos order, so that recognize.sh's hypothesis
                         rechypI is combination I.  Its header records the
                         RECOGNITION HORIZON: the largest of the 8 shortest
                         horizons -- the shortest horizon at which every
                         combination can be achieved, so that no hypothesis is
                         refuted merely by the horizon.  Every recognition run
                         and every circuit of the problem uses it.

One JSON record per goal (stage "goal") and per problem (stage "problem") goes to
results/plans.jsonl; a goal already recorded ok is not planned again.  Each
planner.sh run is bounded as a whole by --limit (wall clock; its process group
and any escaped solver are killed), and each MaxSAT solve by --solver-limit.
"""
import argparse, concurrent.futures as cf, json, os, re, shutil, signal, subprocess, threading, time
import tpcommon as T

PLANS = os.path.join(T.RESULTS, "plans.jsonl")
WORK = os.path.join(T.SCRATCH, "plans")
LOCK = threading.Lock()


def run(cmd, cwd, limit):
    """(status, wall seconds, output); status ok, failed or timeout."""
    t = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, env=T.env(), stdout=subprocess.PIPE,
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
        # a solver FiFO started in a process group of its own outlives the killpg
        subprocess.run(["pkill", "-KILL", "-f", cwd + "/"])
        status = "timeout"
    return status, time.time() - t, out


def with_goal(src, new_name, header, goal_lines):
    """SRC's problem text renamed NEW_NAME, its ppgen header replaced by HEADER,
    and its (:goal ...) by GOAL_LINES."""
    text = open(src).read()
    body = text[text.index("(define (problem "):]
    body = re.sub(r"^\(define \(problem \S+\)", f"(define (problem {new_name})", body, count=1)
    g, m = body.index("  (:goal"), body.index("  (:metric")
    body = body[:g] + "\n".join(goal_lines) + "\n\n" + body[m:]
    return "\n".join(";; " + h if h else ";;" for h in header) + "\n\n" + body


def goal_problem(problem, combo):
    src = os.path.join(T.HERE, problem + ".pddl")
    lits = " ".join(f"(at {p} {d})" for p, d in combo)
    header = [T.combo_name(problem, combo),
              f"Single-goal variant of {problem}.pddl: the goal is the combination",
              f"(and {lits}).",
              "Written by scripts/plan-goals.py."]
    goal = ["  (:goal (and"] + [f"        (at {p} {d})" for p, d in combo[:-1]] + \
           [f"        (at {combo[-1][0]} {combo[-1][1]})))"]
    return with_goal(src, T.combo_name(problem, combo), header, goal)


def recognition_text(problem, horizon, horizons):
    src = os.path.join(T.HERE, problem + ".pddl")
    cs = T.combos(src)
    header = [f"{problem}: the recognition problem",
              f"{problem}.pddl with its goal -- one destination for each package -- written",
              "as the disjunction of its 8 combinations (the same set of plans).",
              "recognize.sh scores disjunct I through the derived atom rechypI:"]
    for i, c in enumerate(cs):
        header.append(f"  {T.hypothesis(i)}  " + " ".join(f"(at {p} {d})" for p, d in c)
                      + f"   shortest horizon {horizons[T.combo_name(problem, c)]}")
    header += [f"Recognition horizon: {horizon}",
               "  (the largest shortest horizon: every combination is achievable at it)",
               "Written by scripts/plan-goals.py."]
    goal = ["  (:goal (or"]
    for i, c in enumerate(cs):
        conj = "(and " + " ".join(f"(at {p} {d})" for p, d in c) + ")"
        goal.append("        " + conj + ("))" if i == len(cs) - 1 else ""))
    return with_goal(src, problem, header, goal)


def plan_actions(answer):
    """[(slice, action text)] of an answer file's OCCURS lines, in time order
    (ties in file order), the action in lower case."""
    acts = []
    for line in open(answer):
        m = re.match(r"\(OCCURS (\(.*\)) (\d+)\)\s*$", line)
        if m:
            acts.append((int(m.group(2)), m.group(1).lower()))
    return sorted(acts, key=lambda a: a[0])    # sorted() is stable


def write_evidence(g, combo_text, acts):
    """evidence/G-obsK.txt and -ordK.txt for each K <= len(ACTS); returns the Ks."""
    os.makedirs(os.path.join(T.HERE, "evidence"), exist_ok=True)
    ks = [k for k in T.KS if k <= len(acts)]
    for k in ks:
        first = acts[:k]
        head = [f";; The first {k} actions of goals/{g}.answer, an optimal plan for",
                f";; {combo_text}.  Written by scripts/plan-goals.py."]
        with open(os.path.join(T.HERE, "evidence", f"{g}-obs{k}.txt"), "w") as f:
            f.write("\n".join(head + [";; Each action is pinned to its time step; ONE (and ...) form,",
                                      ";; for recognize.sh --evidence-kind fifo.", "", "(and"]))
            f.write("\n" + "\n".join(f"  (occurs {a} {s})" for s, a in first) + ")\n")
        with open(os.path.join(T.HERE, "evidence", f"{g}-ord{k}.txt"), "w") as f:
            f.write("\n".join(head + [";; Their order only, non-strict (two may share a step); ONE form,",
                                      ";; for recognize.sh --evidence-kind pddl.", "",
                                      "(occur-in-nonstrict-order"]))
            f.write("\n" + "\n".join(f"  {a}" for _, a in first) + ")\n")
    return ks


def record(rec):
    with LOCK:
        with open(PLANS, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  {rec['name']}: {rec['status']} {rec.get('wall_s', 0):.1f}s"
              f" H={rec.get('horizon', '-')} cost={rec.get('cost', '-')}"
              f" actions={rec.get('actions', '-')}", flush=True)


def plan_goal(problem, i, combo, a):
    g = T.combo_name(problem, combo)
    gp = os.path.join(T.HERE, "goals", g + ".pddl")
    open(gp, "w").write(goal_problem(problem, combo))
    work = os.path.join(WORK, g)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(gp, work)
    cmd = [a.planner, g + ".pddl", "--domain", T.DOMAIN, "--weighted-solver", a.solver,
           "--timeout", str(a.solver_limit), "--maxslices", str(a.max_slices)]
    if a.restrict:
        # the horizon is the one an earlier run of this goal found before its
        # MaxSAT solve failed ("failed at N slices"), so the search is skipped
        cmd = cmd[:-2] + ["--numslices", str(a.known_horizons[g]), "--restrict", a.restrict]
    status, wall, out = run(cmd, work, a.limit)
    rec = dict(stage="goal", name=g, problem=problem, size=T.size_of(problem), index=i,
               hypothesis=T.hypothesis(i), combo=[list(c) for c in combo],
               solver=a.solver + (f" --restrict {a.restrict}" if a.restrict else ""),
               limit_s=a.limit, solver_limit_s=a.solver_limit, status=status,
               wall_s=round(wall, 2), started=time.strftime("%Y-%m-%dT%H:%M:%S"))
    answer = os.path.join(work, g + ".answer")
    h = re.search(r"SOLVED with (\d+) time slices", out)
    if status == "ok" and h and os.path.exists(answer):
        rec["horizon"] = int(h.group(1))
        m = re.search(r"\(\*OBJECTIVE\* (\S+)\)", open(answer).read())
        rec["cost"] = float(m.group(1)) if m else None
        # planner.sh says so when the MaxSAT run hit --timeout and reported its best
        rec["proved_optimal"] = not ("stopped after the" in out and "reporting the best" in out) \
            and not a.restrict
        s = re.search(r"the SAT plan \((\d+) actions\) as found: cost ([0-9.]+)", out)
        if s:
            rec["sat_cost"] = float(s.group(2))
        acts = plan_actions(answer)
        rec["actions"] = len(acts)
        shutil.copy(answer, os.path.join(T.HERE, "goals", g + ".answer"))
        rec["evidence_k"] = write_evidence(g, "(and " + " ".join(f"(at {p} {d})" for p, d in combo) + ")",
                                           acts)
    else:
        if rec["status"] == "ok":
            rec["status"] = "failed"
        rec["log_tail"] = out[-2000:].splitlines()[-12:]
    shutil.rmtree(work, ignore_errors=True)
    record(rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int, default=3600, help="wall seconds per planner.sh run")
    ap.add_argument("--solver-limit", type=int, default=1800, help="seconds per MaxSAT solve")
    ap.add_argument("--max-slices", type=int, default=80)
    ap.add_argument("--solver", default="EvalMaxSAT_bin",
                    help="exact MaxSAT solver for the cost minimisation")
    ap.add_argument("--sizes", type=int, nargs="*", default=list(T.SIZES))
    ap.add_argument("--planner", default="planner.sh", help="the planner.sh to run")
    ap.add_argument("--restrict", choices=("steps", "actions"),
                    help="only for goals whose last run FAILED after finding its horizon: "
                         "plan them at that horizon with planner.sh --restrict (fast, not "
                         "proven optimal; recorded as such)")
    a = ap.parse_args()
    a.known_horizons = {}
    if a.restrict:
        for r in T.load("plans.jsonl"):
            m = re.search(r"failed at (\d+) slices", " ".join(r.get("log_tail", [])))
            if r["stage"] == "goal" and r["status"] == "failed" and m:
                a.known_horizons[r["name"]] = int(m.group(1))
    os.makedirs(T.RESULTS, exist_ok=True)
    os.makedirs(os.path.join(T.HERE, "goals"), exist_ok=True)
    os.makedirs(os.path.join(T.HERE, "recognition"), exist_ok=True)
    done = {r["name"]: r for r in T.load("plans.jsonl") if r["stage"] == "goal" and r["status"] == "ok"}
    names = T.problems(a.sizes)
    jobs = [(p, i, c) for p in names for i, c in enumerate(T.combos(os.path.join(T.HERE, p + ".pddl")))]
    todo = [j for j in jobs if T.combo_name(j[0], j[2]) not in done]
    if a.restrict:
        todo = [j for j in todo if T.combo_name(j[0], j[2]) in a.known_horizons]
    print(f"{len(names)} problems, {len(jobs)} goals, {len(todo)} to plan, {a.jobs} at a time", flush=True)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for rec in ex.map(lambda j: plan_goal(*j, a), todo):
            if rec["status"] == "ok":
                done[rec["name"]] = rec
    for p in names:
        cs = T.combos(os.path.join(T.HERE, p + ".pddl"))
        gs = [T.combo_name(p, c) for c in cs]
        rec = dict(stage="problem", name=p, size=T.size_of(p),
                   started=time.strftime("%Y-%m-%dT%H:%M:%S"))
        if all(g in done for g in gs):
            horizons = {g: done[g]["horizon"] for g in gs}
            H = max(horizons.values())
            open(T.recognition_problem(p), "w").write(recognition_text(p, H, horizons))
            rec.update(status="ok", recognition_horizon=H, min_horizon=min(horizons.values()),
                       horizons=[horizons[g] for g in gs],
                       costs=[done[g]["cost"] for g in gs])
        else:
            rec.update(status="incomplete", missing=[g for g in gs if g not in done])
        record(rec)
    print("done", flush=True)


if __name__ == "__main__":
    main()
