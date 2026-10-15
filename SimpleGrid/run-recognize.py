#!/usr/bin/env python3
"""run-recognize.py -- run FiFO's recognize.sh over the SimpleGrid problems.

One run = one problem, one pinned evidence file (evidence/*-obsN.txt, with
--evidence-kind fifo) and one --counter method.  Each run gets a wall-clock time
limit; on expiry its whole process tree is killed (recognize.sh starts each
planner in a process group of its own, so killing one group is not enough).

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
at FROM_LIMIT seconds timed out.

Fields: evidence, problem, true_goal, n_obs, method, limit_s, status
(ok / timeout / error), wall_s, exit_code, posterior {hyp: p}, c_O / c_notO
(max-term only), argmax (list -- ties are kept), correct (true goal among the
argmax), started, and for a failure the tail of the log.
"""
import argparse, glob, json, os, re, shutil, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
DOMAIN = "clara-logistics.pddl"


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
           "--evidence-kind", "fifo", "--counter", job["method"], "--out", out]
    # Run INSIDE the run's own directory: the counters write scratch files to
    # the working directory, and a run killed at its limit leaves them behind.
    proc = subprocess.Popen(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    return {"job": job, "proc": proc, "t0": time.time(), "out": out, "log": log,
            "limit": limit, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}


def finish(run, timed_out):
    run["log"].close()
    job, out = run["job"], run["out"]
    rec = dict(job, limit_s=run["limit"], wall_s=round(time.time() - run["t0"], 2),
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
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.results), exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    methods = a.methods.split(",")
    done = load(a.results)
    seen = {(r["evidence"], r["method"], r["limit_s"]) for r in done}
    todo = [j for j in jobs_for(methods) if (j["evidence"], j["method"], a.limit) not in seen
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
                over = time.time() - run["t0"] > run["limit"]
                if run["proc"].poll() is None and not over:
                    continue
                if over and run["proc"].poll() is None:
                    kill_tree(run["proc"])
                    run["proc"].wait()
                    rec = finish(run, True)
                else:
                    rec = finish(run, False)
                running.remove(run)
                res.write(json.dumps(rec) + "\n")
                res.flush()
                n += 1
                print(f"[{n}] {rec['status']:7s} {rec['wall_s']:7.1f}s  {rec['method']:11s} "
                      f"{os.path.basename(rec['evidence'])}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
