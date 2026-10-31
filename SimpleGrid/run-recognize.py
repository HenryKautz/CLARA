#!/usr/bin/env python3
"""run-recognize.py -- run FiFO's recognize.sh over the SimpleGrid problems.

One run = one problem, one pinned evidence file (evidence/*-obsN.txt, with
--evidence-kind fifo) and one --counter method.  Each run gets a time limit on
AWAKE time -- CLOCK_UPTIME_RAW, time.monotonic() on macOS, which stops while the
Mac sleeps, so a suspend neither inflates a time nor times a run out; on expiry
its whole process tree is killed (recognize.sh starts each planner in a process
group of its own, so killing one group is not enough).  Run sweeps under
caffeinate -i to keep the Mac from idling to sleep in the first place.

Runs go in parallel, but a run starts only when
  * fewer than --jobs runs are going (set it to the number of PERFORMANCE cores,
    so no two compute-bound processes share one), and
  * at least --reserve-gb of real memory is available (free + inactive +
    speculative pages), so the machine never swaps.
Every run is single-threaded (user time ~= wall time when measured), so one run
is one busy core.

Each finished run is appended to --results as one JSON line, at once, so a
sweep can be stopped and resumed: a (evidence, method, limit) already recorded
is skipped.  --rerun-timeouts FROM_LIMIT reruns exactly the runs whose record
at FROM_LIMIT seconds timed out.  --rerun-solver-timeouts reruns, at --limit,
the runs whose last record there is an error from FiFO's per-solver-call limit
(*solver-timeout*, 600 s by default) or from SharpSAT-TD's FlowCutter being
killed under load: runs before 2026-10-18 did not pass
recognize.sh --timeout, so one count over 600 s failed a run whose own limit was
longer.  Every run now passes --timeout LIMIT, so no single solver call is cut
off before the run itself would be.  A rerun's record is appended after the
old one; make-tables.py takes the later of two records at the same limit.

Fields: evidence, problem, true_goal, n_obs, method, limit_s, status
(ok / timeout / error), wall_s (awake time), clock_s (wall clock, sleep
included), slept_s, cpu_s (user + system, from os.wait4), timing ("awake";
absent on records made before the clock change, whose wall_s is the wall
clock), solver_timeout_s (the recognize.sh --timeout passed; absent = FiFO's
default 600 s), exit_code, posterior {hyp: p}, c_O / c_notO
(max-term only), argmax (list -- ties are kept), correct (true goal among the
argmax), started, and for a failure the tail of the log.
"""
import argparse, glob, json, os, re, shutil, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
DOMAIN = "clara-logistics-old.pddl"


def available_bytes():
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


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def jobs_for(methods):
    jobs = []
    for ev in sorted(glob.glob(os.path.join(HERE, "evidence", "*-obs*.txt"))):
        name = os.path.basename(ev)[:-len(".txt")]
        m = re.match(r"(grid\d+x\d+-\d+)-(p\d+-\d+)-obs(\d+)$", name)
        problem, goal, n = m.group(1), m.group(2), int(m.group(3))
        for meth in methods:
            jobs.append({"evidence": "evidence/" + os.path.basename(ev),
                         "problem": problem + ".pddl", "true_goal": "at-truck1-" + goal,
                         "n_obs": n, "method": meth})
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
    key = f"{os.path.basename(job['evidence'])[:-4]}--{job['method']}--{limit}"
    out = os.path.join(work, key)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    log = open(out + ".log", "w")
    cmd = ["bash", RECOGNIZE, DOMAIN, os.path.join(HERE, job["problem"]),
           os.path.join(HERE, job["evidence"]),
           "--evidence-kind", "fifo", "--counter", job["method"], "--out", out,
           "--timeout", f"{limit:g}"]
    # Run INSIDE the run's own directory: the counters write scratch files to
    # the working directory, and a run killed at its limit leaves them behind.
    proc = subprocess.Popen(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    return {"job": job, "proc": proc, "t0": time.monotonic(), "t0_wall": time.time(),
            "out": out, "log": log, "limit": limit,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S")}


def finish(run, timed_out):
    run["log"].close()
    job, out = run["job"], run["out"]
    # wall_s: awake time (CLOCK_UPTIME_RAW stops while the Mac sleeps), to the
    # moment the run was reaped (polled every second); clock_s adds any sleep;
    # cpu_s: user + system time of the run's tree (killed orphans are missed)
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
        rec.update(status="ok", posterior=post,
                   argmax=sorted(h for h, p in post.items() if p == top),
                   correct=job["true_goal"] in [h for h, p in post.items() if p == top])
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
    ap.add_argument("--rerun-timeouts", type=float, metavar="FROM_LIMIT",
                    help="rerun only the runs that timed out at this limit")
    ap.add_argument("--rerun-solver-timeouts", action="store_true",
                    help="rerun, at --limit, the runs whose record there failed on "
                         "FiFO's per-solver-call limit")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.results), exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    methods = a.methods.split(",")
    done = load(a.results)
    seen = {(r["evidence"], r["method"], r["limit_s"]) for r in done}
    todo = [j for j in jobs_for(methods) if (j["evidence"], j["method"], a.limit) not in seen
            and re.search(a.match, j["evidence"])]
    if a.rerun_solver_timeouts:
        # the LAST record at this limit decides, so a rerun that succeeded is
        # not run again
        last = {}
        for r in done:
            if r["limit_s"] == a.limit:
                last[(r["evidence"], r["method"])] = r
        # also SharpSAT-TD's tree-decomposition helper killed for ignoring its
        # stop signal, which happens under load and is no property of the problem
        capped = {k for k, r in last.items() if r["status"] == "error"
                  and any("(*solver-timeout*)" in t or "flow_cutter_pace17 failed" in t
                          for t in r.get("log_tail", []))}
        todo = [j for j in jobs_for(methods) if (j["evidence"], j["method"]) in capped
                and re.search(a.match, j["evidence"])]
    if a.rerun_timeouts is not None:
        timedout = {(r["evidence"], r["method"]) for r in done
                    if r["limit_s"] == a.rerun_timeouts and r["status"] == "timeout"}
        todo = [j for j in todo if (j["evidence"], j["method"]) in timedout]
    print(f"{len(todo)} runs to do (limit {a.limit:g}s, {a.jobs} jobs, "
          f"reserve {a.reserve_gb:g} GB)", flush=True)

    running, n = [], 0
    reserve = a.reserve_gb * 2**30
    with open(a.results, "a") as res:
        while todo or running:
            # admit
            while todo and len(running) < a.jobs and \
                    (not running or available_bytes() >= reserve):
                running.append(start(todo.pop(0), a.limit, a.work))
                time.sleep(0.5)   # let its memory show up before the next check
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
    print("done", flush=True)


if __name__ == "__main__":
    main()
