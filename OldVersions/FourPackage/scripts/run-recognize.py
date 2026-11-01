#!/usr/bin/env python3
"""run-recognize.py -- run FiFO's recognize.sh over the FourPackage problems.

(TwoPackage's runner, with three changes: the domain is
clara-logistics-handling.pddl; every run of a problem uses one fixed horizon,
fpcommon.recognition_horizon -- the largest goal horizon, and at least 9 slices
for 8 observed actions -- so recognize.sh does not search for it (n planner runs
per evidence file) and all of a problem's runs score the same theory; and SBCL
runs through shims/sbcl with a larger heap.)

One run = one problem, one pinned evidence file (evidence/*-obsK.txt, with
--evidence-kind fifo) and one --counter method.  The hypotheses are the goal's
twelve literals (at pkgI place), which recognize.sh scores as atoms named
at-pkgI-place; the true goal is the literal whose plan the evidence came from.

Sizes go smallest first, and a METHOD STOPS AT THE SIZE WHERE IT TIMES OUT: once
one of its runs at size N hits --limit, no further run of that method is
started at N or any larger size (runs already going are let finish).  So a
first pass at a short limit and a second at a long one,
    run-recognize.py --methods ... --limit 300
    run-recognize.py --methods ... --limit 1200
measure everything that finishes in 5 minutes, then take each method from the
size where it first timed out -- rerunning there its timed-out runs and those
never started -- on up at 20 minutes, until it times out again.  A run counts
as done once it has a record that is ok or error (at any limit), or a timeout
at this limit or a longer one; a method is stopped at the first size holding
such a timeout.

Each run's time limit is on AWAKE time -- CLOCK_UPTIME_RAW, time.monotonic() on
macOS, which stops while the Mac sleeps -- and on expiry its whole process tree
is killed.  recognize.sh gets --timeout LIMIT, so no single solver call inside
it is cut off before the run itself would be.  Run under caffeinate -i.

Runs go in parallel: a run starts only when fewer than --jobs are going (the
number of PERFORMANCE cores) and at least --reserve-gb of memory is available.
Every run is single-threaded.

Each finished run is appended to --results as one JSON line at once, so a sweep
can be stopped and resumed.  Fields: evidence, problem, size, true_goal, n_obs,
method, limit_s, status (ok / timeout / error), wall_s (awake time), clock_s
(wall clock, sleep included), slept_s, cpu_s (user + system, from os.wait4),
timing ("awake"), solver_timeout_s, exit_code, posterior {hyp: p}, c_O / c_notO
(max-term only), argmax (list -- ties kept), correct (true goal among the
argmax), tie_size (len(argmax)), score (1/tie_size when correct, else 0),
started, and for a failure the tail of the log.

`correct` alone overstates a method that ties (max-term's argmax was a tie in
216 of its 240 TwoPackage runs): a k-way tie containing the true goal counts as
a full success.  `score` is the expected accuracy of breaking the tie at random,
and is what accuracy should be computed from.

On Linux, time.monotonic() is CLOCK_MONOTONIC, which also stops during suspend,
and available memory comes from /proc/meminfo instead of vm_stat.
"""
import argparse, glob, json, os, re, shutil, signal, subprocess, sys, time
import fpcommon as F

HERE = F.HERE
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
DOMAIN = F.DOMAIN


def available_bytes():
    if sys.platform.startswith("linux"):
        with open("/proc/meminfo") as f:
            return int(re.search(r"^MemAvailable:\s+(\d+) kB", f.read(), re.M).group(1)) * 1024
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = int(re.search(r"page size of (\d+)", out).group(1))
    pages = 0
    for key in ("Pages free", "Pages inactive", "Pages speculative"):
        m = re.search(key + r":\s+(\d+)", out)
        if m:
            pages += int(m.group(1))
    return pages * page


def descendants(pid):
    """All descendant pids of PID, from one ps snapshot."""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True).stdout
    kids = {}
    for line in out.split("\n"):
        f = line.split()
        if len(f) == 2:
            kids.setdefault(int(f[1]), []).append(int(f[0]))
    found, todo = [], [pid]
    while todo:
        p = todo.pop()
        for c in kids.get(p, []):
            found.append(c)
            todo.append(c)
    return found


def reap(run, block=False):
    """Collect RUN's process if it has ended (or, with BLOCK, wait for it):
    records its exit code, CPU time (os.wait4's rusage: the process and every
    descendant it waited for) and the awake and wall clocks at that moment.
    Returns whether it has ended."""
    if "rusage" in run:
        return True
    pid, status, ru = os.wait4(run["proc"].pid, 0 if block else os.WNOHANG)
    if pid == 0:
        return False
    run["proc"].returncode = os.waitstatus_to_exitcode(status)
    run.update(rusage=ru, t_end=time.monotonic(), t_end_wall=time.time())
    return True


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def kill_tree(proc):
    pids = [proc.pid] + descendants(proc.pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(3)
            pids = [p for p in pids if alive(p)] + descendants(proc.pid)


def size_of(name):
    return int(re.match(r"grid(\d+)x", name).group(1))


def jobs_for(methods):
    jobs = []
    for ev in glob.glob(os.path.join(HERE, "evidence", "*-obs*.txt")):
        name = os.path.basename(ev)[:-len(".txt")]
        m = re.match(r"(grid\d+x\d+-\d+)-(pkg\d+-p\d+-\d+)-obs(\d+)$", name)
        problem, goal, n = m.group(1), m.group(2), int(m.group(3))
        H = F.recognition_horizon(os.path.join(HERE, problem + ".pddl"))
        for meth in methods:
            jobs.append({"evidence": "evidence/" + os.path.basename(ev),
                         "problem": problem + ".pddl", "size": size_of(problem),
                         "true_goal": "at-" + goal, "n_obs": n, "method": meth,
                         "horizon": H})
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
    key = f"{os.path.basename(job['evidence'])[:-4]}--{job['method']}--{limit:g}"
    out = os.path.join(work, key)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    log = open(out + ".log", "w")
    cmd = ["bash", RECOGNIZE, DOMAIN, os.path.join(HERE, job["problem"]),
           os.path.join(HERE, job["evidence"]),
           "--evidence-kind", "fifo", "--counter", job["method"], "--out", out,
           "--timeout", f"{limit:g}", "--horizon", str(job["horizon"]),
           # Exact, as R&G's differences of minima need.  Not wmaxcdcl: on a 6x6
           # recognition theory (H=22) it found no solution in 16 min, where
           # EvalMaxSAT proved the optimum in 188 s.
           "--maxsat-solver", "EvalMaxSAT_bin"]
    # Run INSIDE the run's own directory: the counters write scratch files to
    # the working directory, and a run killed at its limit leaves them behind.
    proc = subprocess.Popen(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True, env=F.env())
    return {"job": job, "proc": proc, "t0": time.monotonic(), "t0_wall": time.time(),
            "out": out, "log": log, "limit": limit,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S")}


def finish(run, timed_out):
    run["log"].close()
    job, out = run["job"], run["out"]
    awake = run["t_end"] - run["t0"]
    slept = max(0.0, (run["t_end_wall"] - run["t0_wall"]) - awake)
    ru = run["rusage"]
    rec = dict(job, limit_s=run["limit"], wall_s=round(awake, 2),
               clock_s=round(awake + slept, 2), slept_s=round(slept, 2),
               cpu_s=round(ru.ru_utime + ru.ru_stime, 2), timing="awake",
               solver_timeout_s=run["limit"],
               exit_code=run["proc"].returncode, started=run["started"])
    summary = os.path.join(out, "summary.tsv")
    if timed_out:
        rec["status"] = "timeout"
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
            rec["log_tail"] = f.read().strip().split("\n")[-6:]
    shutil.rmtree(out, ignore_errors=True)
    os.remove(out + ".log")
    # marginals.sh writes its scratch files BESIDE the output directory
    # (<out>-hyp.wcnf, <out>-hypev.scnf, ...), not inside it
    for f in glob.glob(glob.escape(out) + "-*"):
        try:
            os.remove(f)
        except OSError:
            shutil.rmtree(f, ignore_errors=True)
    return rec


def load(results):
    recs = []
    if os.path.exists(results):
        with open(results) as f:
            recs = [json.loads(l) for l in f if l.strip()]
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", required=True, help="comma separated --counter names")
    ap.add_argument("--limit", type=float, required=True, help="seconds per run")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--reserve-gb", type=float, default=2.0)
    ap.add_argument("--results", default=os.path.join(HERE, "results", "runs.jsonl"))
    ap.add_argument("--work", required=True, help="scratch directory on a local disk")
    ap.add_argument("--match", default="", help="only evidence files matching this regex")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.results), exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    methods = a.methods.split(",")
    recs = load(a.results)
    finished = {(r["evidence"], r["method"]) for r in recs if r["status"] in ("ok", "error")}
    long_timeouts = [r for r in recs if r["status"] == "timeout" and r["limit_s"] >= a.limit]
    timed = {(r["evidence"], r["method"]) for r in long_timeouts}
    # stopped[m]: the smallest size where m already timed out at >= this limit
    stopped = {}
    for r in long_timeouts:
        s = size_of(r["problem"])
        stopped[r["method"]] = min(stopped.get(r["method"], s), s)
    todo = [j for j in jobs_for(methods) if re.search(a.match, j["evidence"])
            and (j["evidence"], j["method"]) not in finished
            and (j["evidence"], j["method"]) not in timed]

    def allowed(j):
        return j["size"] < stopped.get(j["method"], 10**9)

    print(f"{sum(map(allowed, todo))} runs to do (limit {a.limit:g}s, {a.jobs} jobs, "
          f"reserve {a.reserve_gb:g} GB); stopped already: "
          f"{ {m: f'{s}x{s}' for m, s in stopped.items()} }", flush=True)

    running, n = [], 0
    reserve = a.reserve_gb * 2**30
    with open(a.results, "a") as res:
        while True:
            todo = [j for j in todo if allowed(j)]
            # admit -- never a size above one still running for the same method,
            # so a timeout at size N stops the method before N+1 is started
            while todo and len(running) < a.jobs and \
                    (not running or available_bytes() >= reserve):
                low = {}
                for r in running:
                    m = r["job"]["method"]
                    low[m] = min(low.get(m, 10**9), r["job"]["size"])
                pick = next((j for j in todo if j["size"] <= low.get(j["method"], 10**9)), None)
                if pick is None:
                    break
                todo.remove(pick)
                running.append(start(pick, a.limit, a.work))
                time.sleep(0.5)   # let its memory show up before the next check
            if not running and not todo:
                break
            time.sleep(1)
            for run in list(running):
                # the limit is on awake time, so a sleep does not time a run out
                over = time.monotonic() - run["t0"] > run["limit"]
                if reap(run):
                    rec = finish(run, False)
                elif over:
                    kill_tree(run["proc"])
                    reap(run, block=True)
                    rec = finish(run, True)
                else:
                    continue
                running.remove(run)
                res.write(json.dumps(rec) + "\n")
                res.flush()
                n += 1
                print(f"[{n}] {rec['status']:7s} {rec['wall_s']:7.1f}s  {rec['method']:11s} "
                      f"{os.path.basename(rec['evidence'])}", flush=True)
                if rec["status"] == "timeout":
                    m, s = rec["method"], rec["size"]
                    if s < stopped.get(m, 10**9):
                        stopped[m] = s
                        print(f"    {m} stopped at {s}x{s}: no more {m} runs at "
                              f"{s}x{s} or larger at this limit", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
