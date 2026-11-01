#!/usr/bin/env python3
"""run-recognize.py --methods max-term,sharpsat-td --limit 600 [--jobs N]

Run FiFO's recognize.sh over the ThreePackage evidence.  One run = one pinned
evidence file (evidence/<combo>-obsK.txt, --evidence-kind fifo), its problem's
recognition/gridNxN-K.pddl -- the goal as the disjunction of its 8 combinations,
scored as rechyp0..rechyp7 -- at the problem's recognition horizon (--horizon,
from that file's header, so no run searches for it and all of a problem's runs
score one theory), and one --counter method:

  max-term      Ramirez & Geffner's cheapest-plan difference: 2 exact MaxSAT
                solves per hypothesis (EvalMaxSAT_bin), with and without the
                evidence
  sharpsat-td   exact weighted model counting (SharpSAT-TD)

The true goal of evidence/<combo>-obsK.txt is the hypothesis of <combo>.

Sizes go smallest first, and a method STOPS AT THE FIRST SIZE WHERE ONE OF ITS
RUNS TIMES OUT: its other runs at that size still going are KILLED (recorded as
status "killed") and none of its runs at that size or larger is started.  A
method never has runs of two sizes going at once, so killing ends it cleanly.
Each run gets --limit seconds of wall time (its whole process tree is killed at
the limit), and recognize.sh gets --timeout and --planner-timeout LIMIT, so no
solver call or instantiation inside it is cut off before the run is.

Runs go in parallel, up to --jobs at once while at least --reserve-gb of memory
is available.  Every run is single-threaded.  Each finished run is appended to
--results at once, so a sweep can be stopped and resumed: a run with an ok or
error record is not repeated, nor one that timed out at this limit or a longer
one, and a method is stopped at the smallest size holding such a timeout.

Record fields: evidence, problem, size, true_goal, combo, n_obs, method, horizon,
limit_s, status (ok / timeout / killed / error), wall_s, cpu_s (user + system,
from os.wait4), exit_code, posterior {hyp: p}, c_O / c_notO (max-term only),
argmax (list -- ties kept), correct (true goal among the argmax), tie_size,
score (1/tie_size when correct, else 0 -- the expected accuracy of breaking the
tie at random, which accuracy is computed from), started, and for a failure the
tail of the log.
"""
import argparse, glob, json, os, re, shutil, signal, subprocess, sys, time
import tpcommon as T

RECOGNIZE = shutil.which("recognize.sh") or os.path.expanduser("~/bin/recognize.sh")


def available_bytes():
    with open("/proc/meminfo") as f:
        return int(re.search(r"^MemAvailable:\s+(\d+) kB", f.read(), re.M).group(1)) * 1024


def descendants(pid):
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True).stdout
    kids = {}
    for line in out.split("\n"):
        f = line.split()
        if len(f) == 2:
            kids.setdefault(int(f[1]), []).append(int(f[0]))
    found, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            found.append(c)
            todo.append(c)
    return found


def reap(run, block=False):
    if "rusage" in run:
        return True
    pid, status, ru = os.wait4(run["proc"].pid, 0 if block else os.WNOHANG)
    if pid == 0:
        return False
    run["proc"].returncode = os.waitstatus_to_exitcode(status)
    run.update(rusage=ru, t_end=time.monotonic())
    return True


def kill_tree(run):
    proc = run["proc"]
    pids = [proc.pid] + descendants(proc.pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(3)
            pids += descendants(proc.pid)
    # a solver FiFO started in a process group of its own: its command line
    # names a file in the run's directory
    subprocess.run(["pkill", "-KILL", "-f", run["out"] + "/"])
    reap(run, block=True)


def jobs_for(methods):
    index = {}
    for p in T.problems():
        for i, c in enumerate(T.combos(os.path.join(T.HERE, p + ".pddl"))):
            index[T.combo_name(p, c)] = (p, i, c)
    jobs = []
    for ev in glob.glob(os.path.join(T.HERE, "evidence", "*-obs*.txt")):
        m = re.match(r"(.*)-obs(\d+)\.txt$", os.path.basename(ev))
        p, i, c = index[m.group(1)]
        if not os.path.exists(T.recognition_problem(p)):
            continue
        for meth in methods:
            jobs.append({"evidence": "evidence/" + os.path.basename(ev), "problem": p,
                         "size": T.size_of(p), "true_goal": T.hypothesis(i),
                         "combo": [list(x) for x in c], "n_obs": int(m.group(2)),
                         "method": meth, "horizon": T.recognition_horizon(p)})
    # smallest grid, then fewest observations, then name: the cheap runs first
    jobs.sort(key=lambda j: (j["size"], j["n_obs"], j["evidence"], j["method"]))
    return jobs


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


def start(job, limit, work):
    key = f"{os.path.basename(job['evidence'])[:-4]}--{job['method']}"
    out = os.path.join(work, key)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    log = open(out + ".log", "w")
    cmd = ["bash", RECOGNIZE, T.DOMAIN, T.recognition_problem(job["problem"]),
           os.path.join(T.HERE, job["evidence"]), "--evidence-kind", "fifo",
           "--counter", job["method"], "--out", out, "--horizon", str(job["horizon"]),
           "--timeout", f"{limit:g}", "--planner-timeout", f"{limit:g}",
           # exact, as R&G's differences of minima need (ignored by sharpsat-td)
           "--maxsat-solver", "EvalMaxSAT_bin"]
    # inside the run's own directory: the counters write scratch files to the cwd
    proc = subprocess.Popen(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True, env=T.env())
    return {"job": job, "proc": proc, "t0": time.monotonic(), "out": out, "log": log,
            "limit": limit, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}


def finish(run, status=None):
    run["log"].close()
    job, out = run["job"], run["out"]
    ru = run["rusage"]
    rec = dict(job, limit_s=run["limit"], wall_s=round(run["t_end"] - run["t0"], 2),
               cpu_s=round(ru.ru_utime + ru.ru_stime, 2), exit_code=run["proc"].returncode,
               started=run["started"])
    summary = os.path.join(out, "summary.tsv")
    if status:
        rec["status"] = status
    elif run["proc"].returncode == 0 and os.path.exists(summary):
        post, co, cn = parse_summary(summary)
        top = max(post.values())
        argmax = sorted(h for h, p in post.items() if p == top)
        correct = job["true_goal"] in argmax
        rec.update(status="ok", posterior=post, argmax=argmax, correct=correct,
                   tie_size=len(argmax), score=1 / len(argmax) if correct else 0.0)
        if co:
            rec.update(c_O=co, c_notO=cn)
    else:
        rec["status"] = "error"
    if rec["status"] != "ok":
        with open(out + ".log") as f:
            rec["log_tail"] = f.read().strip().split("\n")[-8:]
        # a solver run inside stopped at recognize.sh --timeout (= LIMIT) a moment
        # before the run itself would have been: an exact count stopped there is
        # reported as an error, but the run timed out
        if rec["status"] == "error" and any("timed out after" in l for l in rec["log_tail"]):
            rec["status"] = "timeout"
    shutil.rmtree(out, ignore_errors=True)
    os.remove(out + ".log")
    # marginals.sh writes scratch files BESIDE the output directory
    for f in glob.glob(glob.escape(out) + "-*"):
        try:
            os.remove(f)
        except OSError:
            shutil.rmtree(f, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", required=True, help="comma separated --counter names")
    ap.add_argument("--limit", type=float, required=True, help="seconds per run")
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--reserve-gb", type=float, default=8.0)
    ap.add_argument("--results", default=os.path.join(T.RESULTS, "runs.jsonl"))
    ap.add_argument("--work", default=os.path.join(T.SCRATCH, "recognize"))
    ap.add_argument("--match", default="", help="only evidence files matching this regex")
    a = ap.parse_args()

    os.makedirs(a.work, exist_ok=True)
    methods = a.methods.split(",")
    recs = []
    if os.path.exists(a.results):
        with open(a.results) as f:
            recs = [json.loads(l) for l in f if l.strip()]
    finished = {(r["evidence"], r["method"]) for r in recs if r["status"] in ("ok", "error")}
    long_timeouts = [r for r in recs if r["status"] == "timeout" and r["limit_s"] >= a.limit]
    timed = {(r["evidence"], r["method"]) for r in long_timeouts}
    stopped = {}       # method -> the smallest size where it timed out
    for r in long_timeouts:
        stopped[r["method"]] = min(stopped.get(r["method"], r["size"]), r["size"])
    todo = [j for j in jobs_for(methods) if re.search(a.match, j["evidence"])
            and (j["evidence"], j["method"]) not in finished
            and (j["evidence"], j["method"]) not in timed]

    def allowed(j):
        return j["size"] < stopped.get(j["method"], 10**9)

    print(f"{sum(map(allowed, todo))} runs to do (limit {a.limit:g}s, {a.jobs} jobs); "
          f"stopped already: { {m: f'{s}x{s}' for m, s in stopped.items()} }", flush=True)
    running, n = [], 0
    reserve = a.reserve_gb * 2**30
    with open(a.results, "a") as res:
        def write(rec):
            nonlocal n
            res.write(json.dumps(rec) + "\n")
            res.flush()
            n += 1
            print(f"[{n}] {rec['status']:7s} {rec['wall_s']:7.1f}s  {rec['method']:11s} "
                  f"{os.path.basename(rec['evidence'])}", flush=True)

        while True:
            todo = [j for j in todo if allowed(j)]
            while todo and len(running) < a.jobs and (not running or available_bytes() >= reserve):
                # never a size above one still running for the same method
                low = {}
                for r in running:
                    m = r["job"]["method"]
                    low[m] = min(low.get(m, 10**9), r["job"]["size"])
                pick = next((j for j in todo if j["size"] <= low.get(j["method"], 10**9)), None)
                if pick is None:
                    break
                todo.remove(pick)
                running.append(start(pick, a.limit, a.work))
                time.sleep(0.5)
            if not running and not todo:
                break
            time.sleep(1)
            for run in list(running):
                if run not in running:
                    continue       # killed below, by an earlier run's timeout
                over = time.monotonic() - run["t0"] > run["limit"]
                if reap(run):
                    rec = finish(run)
                elif over:
                    kill_tree(run)
                    rec = finish(run, "timeout")
                else:
                    continue
                running.remove(run)
                write(rec)
                if rec["status"] == "timeout":
                    m, s = rec["method"], rec["size"]
                    if s < stopped.get(m, 10**9):
                        stopped[m] = s
                    victims = [r for r in running
                               if r["job"]["method"] == m and r["job"]["size"] >= s]
                    print(f"    {m} stopped at {s}x{s}: killing its {len(victims)} other "
                          f"run(s) there; none at {s}x{s} or larger is started", flush=True)
                    for v in victims:
                        kill_tree(v)
                        running.remove(v)
                        write(finish(v, "killed"))
    print("done", flush=True)


if __name__ == "__main__":
    main()
