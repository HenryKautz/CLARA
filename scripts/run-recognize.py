#!/usr/bin/env python3
"""run-recognize.py --family F [--methods max-term,sharpsat-td,mc-sat] [--limit 1800]

Marginal plan recognition over family F's evidence with FiFO's recognize.sh:
the posterior of each HYPOTHESIS only (the disjuncts of the goal of
recognition/gridNxN-K.pddl), at the problem's recognition horizon (--horizon,
from that file's header), with uniform priors and recognize.sh's default
per-hypothesis baseline.  One run = one evidence file and one --counter:

  max-term      Ramirez & Geffner's cheapest-plan difference, 2 MaxSAT solves
                per hypothesis by EvalMaxSAT_bin (exact, as a difference of
                minima needs)
  sharpsat-td   exact weighted model counting (SharpSAT-TD)
  mc-sat        MC-SAT sampling (WalkSAT v58), approximate

Evidence (pinned, --evidence-kind fifo): evidence/<problem>-none.txt (no
observations: one run per problem; under the per-hypothesis baseline its
posterior is the prior), evidence/<goal>-obs25.txt and -obs100.txt (the first
25% / all of the actions of the goal's plan; the true hypothesis is the goal's).

Each run gets --limit seconds of wall time as a whole (its process tree is then
killed), and recognize.sh gets --timeout and --planner-timeout LIMIT.

STOP RULE, per method: sizes go smallest first; when a run of a method times
out or runs out of memory at size s, its runs still going at s or larger are
killed (status "killed") and none is started at s or larger.

Planning runs at the same time (plan-goals.py): a size's runs start once
plans.jsonl says that size is settled; the script ends when planning has ended
and nothing is left.  Records go to results/runs.jsonl; a run recorded ok or
error is not repeated, nor one that timed out at this limit or longer, and the
stop rule is rebuilt from the records.

Record: evidence, problem, size, true_goal (null for none), n_obs, evidence_pct
(0, 25, 100), method, horizon, status (ok / error / timeout / memout / killed /
nomix -- MC-SAT's chain never sampled some hypothesis without the evidence, so
P(h|T) is estimated 0 and the posterior is undefined; FiFO refuses it),
wall_s, cpu_s, peak_rss_mb, posterior {hyp: p}, argmax (ties kept), correct,
tie_size, score (1/tie_size if correct else 0), c_O / c_notO (max-term), the
sampler's diagnostic lines (mc-sat), and the log tail of a failure.
"""
import argparse, glob, json, os, re, shutil, time
import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--family", required=True)
ap.add_argument("--methods", default=",".join(C.METHODS))
ap.add_argument("--limit", type=float, default=1800)
ap.add_argument("--jobs", type=int, default=12)
ap.add_argument("--reserve-gb", type=float, default=24.0)
ap.add_argument("--min-free-gb", type=float, default=6.0)
ap.add_argument("--poll", type=float, default=60, help="seconds between looks at the plans")
A = ap.parse_args()

FAM = C.Family(A.family)
RUNS = os.path.join(FAM.results, "runs.jsonl")
PLANS = os.path.join(FAM.results, "plans.jsonl")
WORK = os.path.join(FAM.scratch, "recognize")
RECOGNIZE = shutil.which("recognize.sh")
METHODS = A.methods.split(",")


def plan_state():
    recs = C.load_jsonl(PLANS)
    settled = {r["size"] for r in recs if r["stage"] == "size"}
    ended = any(r["stage"] == "end" for r in recs)
    return settled, ended


def jobs_for_size(size):
    jobs = []
    for p in FAM.problems([size]):
        if not os.path.exists(FAM.recognition_problem(p)):
            continue
        H = FAM.recognition_horizon(p)
        base = dict(problem=p, size=size, horizon=H)
        evs = [(f"evidence/{p}-none.txt", None, 0, 0)]
        for h in FAM.hypotheses(p):
            for pct in C.EVIDENCE_FRACTIONS:
                ev = f"evidence/{h.goal}-obs{pct}.txt"
                n = len(re.findall(r"\(occurs ", open(FAM.path(ev)).read()))
                evs.append((ev, h.name, pct, n))
        for ev, true, pct, n in evs:
            for m in METHODS:
                jobs.append(dict(base, evidence=ev, true_goal=true, evidence_pct=pct, n_obs=n, method=m))
    return jobs


class Job:
    def __init__(self, d):
        self.d = d
        self.method, self.size = d["method"], d["size"]

    def key(self):
        return (self.size, self.d["evidence_pct"], self.d["evidence"], self.method)

    def start(self):
        name = os.path.basename(self.d["evidence"])[:-4] + "--" + self.method
        self.work = os.path.join(WORK, name)
        shutil.rmtree(self.work, ignore_errors=True)
        os.makedirs(self.work)
        out = os.path.join(self.work, "out")
        cmd = ["bash", RECOGNIZE, FAM.domain, FAM.recognition_problem(self.d["problem"]),
               FAM.path(self.d["evidence"]), "--evidence-kind", "fifo",
               "--counter", self.method, "--out", out, "--horizon", str(self.d["horizon"]),
               "--timeout", f"{A.limit:g}", "--planner-timeout", f"{A.limit:g}",
               "--maxsat-solver", C.EVAL]
        self.run = C.Run(self, cmd, self.work, A.limit, log=self.work + ".log")
        return self.run


def parse_summary(path):
    post, co, cn = {}, {}, {}
    with open(path) as f:
        next(f)
        for line in f:
            h, c_o, c_n, _d, _l, _pr, p = line.rstrip("\n").split("\t")
            post[h] = float(p)
            if c_o != "-":
                co[h], cn[h] = c_o, c_n
    return post, co, cn


def finish(job, status):
    run = job.run
    rec = dict(job.d, **run.base_record())
    out = run.output()
    summary = os.path.join(job.work, "out", "summary.tsv")
    if status == "ok":
        status = run.classify()
        if status == "ok" and os.path.exists(summary):
            post, co, cn = parse_summary(summary)
            top = max(post.values())
            argmax = sorted(h for h, p in post.items() if p == top)
            rec.update(posterior=post, argmax=argmax, tie_size=len(argmax))
            if job.d["true_goal"] is not None:
                correct = job.d["true_goal"] in argmax
                rec.update(correct=correct, score=1 / len(argmax) if correct else 0.0)
            if co:
                rec.update(c_O=co, c_notO=cn)
        elif status == "ok":
            status = "error"
        elif status == "failed":
            status = "error"
        if status == "error" and ("timed out after" in out or "stopped after the" in out):
            status = "timeout"       # a solver call inside hit --timeout (= the run's limit)
        if status == "error" and "did not mix" in out:
            status = "nomix"         # MC-SAT's chain never reached some hypothesis: a
                                     # sampling failure, not a timeout (no stop)
    rec["status"] = status
    if job.method == "mc-sat":
        rec["sampler"] = [l.strip() for l in out.split("\n")
                          if re.search(r"ESS|mixing|efficien|WARNING|warning", l)][:20]
    if status != "ok":
        rec["log_tail"] = C.log_tail(out, 10)
    shutil.rmtree(job.work, ignore_errors=True)
    try:
        os.remove(job.work + ".log")
    except OSError:
        pass
    for f in glob.glob(glob.escape(job.work) + "-*"):
        shutil.rmtree(f, ignore_errors=True) if os.path.isdir(f) else os.remove(f)
    return rec


def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(FAM.results, exist_ok=True)
    recs = C.load_jsonl(RUNS)
    finished = {(r["evidence"], r["method"]) for r in recs if r["status"] in ("ok", "error", "nomix")}
    finished |= {(r["evidence"], r["method"]) for r in recs
                 if r["status"] in ("timeout", "memout") and r["limit_s"] >= A.limit}
    stopped = {}
    for r in recs:
        if r["status"] in ("timeout", "memout") and r["limit_s"] >= A.limit:
            stopped[r["method"]] = min(stopped.get(r["method"], 99), r["size"])
    C.say(f"{FAM.name}: methods {METHODS}, limit {A.limit:g}s, {A.jobs} jobs; stopped: {stopped}")
    loaded, pending, running = set(), [], []
    reserve, min_free = A.reserve_gb * 2**30, A.min_free_gb * 2**30
    last_look = 0
    ended = False

    def allowed(j):
        return j.size < stopped.get(j.method, 99)

    def record(rec):
        C.append_jsonl(RUNS, rec)
        C.say(f"{rec['status']:7s} {rec['wall_s']:8.1f}s {rec['method']:11s} {os.path.basename(rec['evidence'])}"
              + (f"  score={rec['score']:.2f}" if "score" in rec else ""))

    while True:
        if time.monotonic() - last_look > A.poll or (not pending and not running):
            settled, ended = plan_state()
            for s in sorted(settled - loaded):
                new = [Job(d) for d in jobs_for_size(s) if (d["evidence"], d["method"]) not in finished]
                pending += new
                loaded.add(s)
                C.say(f"size {s}x{s}: {len(new)} runs queued")
            last_look = time.monotonic()
        pending[:] = [j for j in pending if allowed(j)]
        if ended and not pending and not running:
            break
        pending.sort(key=Job.key)
        while pending and len(running) < A.jobs and (not running or C.available_bytes() >= reserve):
            j = pending.pop(0)
            j.start()
            running.append(j)
            time.sleep(0.5)
        time.sleep(2 if running else min(A.poll, 30))
        table = C.process_table()
        for j in running:
            j.run.peak_kb = max(j.run.peak_kb, C.tree_rss_kb(j.run.proc.pid, table))
        victim = None
        if running and C.available_bytes() < min_free:
            victim = max(running, key=lambda j: C.tree_rss_kb(j.run.proc.pid, table))
        for j in list(running):
            if j not in running:
                continue
            if j.run.poll():
                rec = finish(j, "ok")
            elif j.run.over() or j is victim:
                j.run.kill()
                rec = finish(j, "timeout" if j is not victim else "memout")
            else:
                continue
            running.remove(j)
            record(rec)
            if rec["status"] in ("timeout", "memout"):
                m, s = j.method, j.size
                if s < stopped.get(m, 99):
                    stopped[m] = s
                victims = [v for v in running if v.method == m and v.size >= s]
                C.say(f"    {m} stopped at {s}x{s}: killing its {len(victims)} other run(s) there or larger")
                for v in victims:
                    v.run.kill()
                    running.remove(v)
                    record(finish(v, "killed"))
    C.say(f"done; stopped: {stopped}")


if __name__ == "__main__":
    main()
