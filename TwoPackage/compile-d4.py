#!/usr/bin/env python3
"""compile-d4.py -- compile each TwoPackage problem to a d-DNNF circuit with d4.

For each problem gridNxN-K.pddl, smallest grid first:

  1. Build the EVIDENCE-FREE recognition theory recognize.sh scores: the problem
     at its recognition horizon H (the largest per-hypothesis feasible horizon),
     with the goal's four literals as hypotheses.  It is the rec-problem.scnf of
     a recognize.sh run (the run's own evidence goes to a separate file and is
     not used); saved as scnf/gridNxN-K.scnf.
  2. Compile it with  marginals.sh --solver d4 --project --save-circuit, which
     projects onto the actions, the final-slice goal atoms and the weighted atoms
     (after checking that they determine every other atom, so the projection is
     exact), runs d4, and saves FiFO's circuit as circuits/gridNxN-K.dnnf.  Any
     pinned observation is a unit literal over those actions, so the saved
     circuit answers every evidence file by conditioning, without recompiling:
         marginals.sh --circuit circuits/gridNxN-K.dnnf --solver d4 \\
                      --evidence-file evidence/...-obsK.txt

The d4 that marginals.sh runs is shims/d4, which records d4's own time, its
input CNF and its circuit dump; its sbcl is shims/sbcl, which gives SBCL an
--sbcl-heap-mb heap.  Each compilation gets --limit seconds of AWAKE time (the
whole marginals.sh run), on CLOCK_UPTIME_RAW -- time.monotonic() on macOS --
which stops while the Mac sleeps.  Each record also has clock_s (wall clock,
sleep included), slept_s and cpu_s (user + system, from os.wait4), and is
appended to --results the moment the run ends.  Run under caffeinate -i.  While
a compilation runs, d4's resident memory is sampled; if available memory runs
low, the largest d4 is killed (status memout) rather than let the machine swap.

Every circuit is checked before it is kept: its model count (all literals 1 in
the smoothed circuit) must equal SharpSAT-TD's exact count of d4's own input CNF
-- the whole theory, which sharpSAT counts over ALL its variables (it ignores
the 'c p show' projection line).  The two agree because the projection is exact:
marginals.sh's Padoa check has proved that the kept atoms determine the rest, so
each projected model extends to exactly one model of the theory.  The check is
independent of FiFO and of d4 (sharpSAT reads the CNF, nothing else), and d4 has
returned wrong circuits before (SimpleGrid, from 8x8 on).  A circuit whose
count differs is discarded (status wrong) and the problem tried again, like a
crash; one whose check does not finish within --verify-limit (120 s) is kept,
recorded as unverified (count_check "timeout") -- query-evidence.py still
compares its conditioned marginals with SharpSAT-TD's.

Sizes go smallest first, and compilation STOPS AFTER THE FIRST SIZE WHERE A
PROBLEM TIMES OUT (or runs out of memory) at this limit.  A problem is skipped
if its last record is ok, or a timeout/memout at this limit or a longer one;
so a second run with a longer --limit retries exactly the problems that timed
out at the shorter one, then carries on to larger sizes until one times out
again.  Problems whose last attempt ended in an error or a wrong circuit are
tried again, up to --attempts in a row.
"""
import argparse, glob, hashlib, json, os, re, shutil, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
MARGINALS = os.path.expanduser("~/bin/marginals.sh")
SHIM = os.path.join(HERE, "shims")
CRASHES = "/tmp/tp-d4-crashes"
DOMAIN = "clara-logistics.pddl"
SIZES = ["3x3", "4x4", "5x5", "6x6", "7x7"]


def theory_path(rel):
    """A record's theory path, absolute.  The theories moved from circuits/ to
    scnf/ (2026-10-20); records written before that still say circuits/."""
    return os.path.join(HERE, re.sub(r"^circuits/(.*\.scnf)$", r"scnf/\1", rel))


def available_bytes():
    if sys.platform.startswith("linux"):
        with open("/proc/meminfo") as f:
            return int(re.search(r"^MemAvailable:\s+(\d+) kB", f.read(), re.M).group(1)) * 1024
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = int(re.search(r"page size of (\d+)", out).group(1))
    pages = sum(int(m.group(1)) for key in ("Pages free", "Pages inactive", "Pages speculative")
                for m in [re.search(key + r":\s+(\d+)", out)] if m)
    return pages * page


def process_table():
    """{pid: (ppid, rss_kb, command name)} from one ps snapshot."""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,comm="],
                         capture_output=True, text=True).stdout
    table = {}
    for line in out.split("\n"):
        f = line.split(None, 3)
        if len(f) == 4:
            table[int(f[0])] = (int(f[1]), int(f[2]), f[3])
    return table


def descendants(pid, table):
    kids = {}
    for p, (pp, _r, _c) in table.items():
        kids.setdefault(pp, []).append(p)
    found, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            found.append(c)
            todo.append(c)
    return found


def d4_rss_kb(pid, table):
    """Resident memory of the real d4 under PID (the shim is a bash script)."""
    return max([table[p][1] for p in descendants(pid, table)
                if os.path.basename(table[p][2]) == "d4"] or [0])


def reap(run, block=False):
    """Collect RUN's process if it has ended (or, with BLOCK, wait for it):
    records its exit code, its CPU time and the awake and wall clocks at that
    moment.  Returns whether it has ended."""
    if "rusage" in run:
        return True
    pid, status, ru = os.wait4(run["proc"].pid, 0 if block else os.WNOHANG)
    if pid == 0:
        return False
    run["proc"].returncode = os.waitstatus_to_exitcode(status)
    run.update(rusage=ru, t_end=time.monotonic(), t_end_wall=time.time())
    return True


def kill_tree(run):
    proc = run["proc"]
    pids = [proc.pid] + descendants(proc.pid, process_table())
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(3)
            pids += descendants(proc.pid, process_table())
    reap(run, block=True)


def prepare(problem, work):
    """Run recognize.sh once to get the problem's evidence-free theory; returns
    (scnf path in scnf/, horizon).  The theory does not depend on the
    evidence (only the horizon could, and one observation at slice 1 never
    raises it), so any obs1 file of the problem will do.  --stop-after scnf
    ends the run once the theory is instantiated, before the 2n MaxSAT solves
    of a full recognition, which this needs none of."""
    name = problem[:-len(".pddl")]
    evs = sorted(glob.glob(os.path.join(HERE, "evidence", name + "-*-obs1.txt")))
    if not evs:
        sys.exit(f"no evidence/{name}-*-obs1.txt: run make-instances.sh first")
    out = os.path.join(work, "rec")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    r = subprocess.run(["bash", RECOGNIZE, DOMAIN, os.path.join(HERE, problem), evs[0],
                        "--evidence-kind", "fifo", "--stop-after", "scnf", "--out", out],
                       cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"recognize.sh failed on {problem}:\n{r.stdout}\n{r.stderr}")
    horizon = int(re.search(r"^Horizon H = (\d+)", r.stdout + r.stderr, re.M).group(1))
    scnf = os.path.join(HERE, "scnf", name + ".scnf")
    shutil.copy(os.path.join(out, "rec-problem.scnf"), scnf)
    shutil.rmtree(out, ignore_errors=True)
    for f in glob.glob(glob.escape(out) + "-*"):
        os.remove(f)
    return scnf, horizon


def start(name, scnf, work, real, heap_mb, d4_options, node_limit, limit):
    log_dir = os.path.join(work, "d4log")
    os.makedirs(log_dir, exist_ok=True)
    env = dict(os.environ, PATH=SHIM + os.pathsep + os.environ["PATH"],
               D4_LOG_DIR=log_dir, D4_REAL=real["d4"], SBCL_REAL=real["sbcl"],
               SBCL_HEAP_MB=str(heap_mb), D4_EXTRA=d4_options)
    log = open(os.path.join(work, "marginals.log"), "w")
    # The run notes the moment it ends, on the awake clock -- time.monotonic(),
    # CLOCK_UPTIME_RAW on macOS and CLOCK_MONOTONIC on Linux, both of which
    # stop during sleep -- so the total time does not depend on how often the
    # loop below polls.  --timeout: FiFO bounds d4 by *solver-timeout*, whose
    # 600 s default would otherwise end a longer compilation first.
    cmd = ["bash", "-c", 'bash "$0" "$@"; rc=$?; '
           'python3 -c \'import time; print("%.3f" % time.monotonic())\''
           ' > "$D4_LOG_DIR/total-end"; exit $rc',
           MARGINALS, scnf, "--solver", "d4", "--project", "--timeout", f"{limit:g}",
           "--save-circuit", os.path.join(work, name + ".dnnf")]
    if node_limit:
        cmd += ["--node-limit", str(node_limit)]
    proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    return {"name": name, "proc": proc, "t0": time.monotonic(), "t0_wall": time.time(),
            "log": log, "work": work, "log_dir": log_dir, "peak_kb": 0}


def cnf_stats(path):
    """(variables, clauses, projected variables) of d4's input DIMACS."""
    v = c = proj = None
    with open(path) as f:
        for line in f:
            if line.startswith("p cnf"):
                _, _, v, c = line.split()
            elif line.startswith("c p show"):
                proj = len(line.split()) - 4      # 'c p show v1 ... vk 0'
            elif not line.startswith("c"):
                break
    return int(v), int(c), proj


def nnf_stats(path):
    """(nodes, edges) of a d4 NNF dump: one line per node ('o|a|t|f id 0'),
    one per arc ('src dst [literals] 0')."""
    nodes = edges = 0
    with open(path) as f:
        for line in f:
            if line[:1].isalpha():
                nodes += 1
            elif line[:1].isdigit():
                edges += 1
    return nodes, edges


def start_check(run):
    """Start SharpSAT-TD counting d4's input CNF over all its variables (it
    ignores the 'c p show' line); its output goes to check.out in the run's
    work directory.  Polled by the main loop like the compilation itself."""
    d = run["work"]
    out = open(os.path.join(d, "check.out"), "w")
    run["check"] = subprocess.Popen(
        ["sharpSAT", "-decot", "1", "-decow", "100", "-tmpdir", d, "-cs", "3500",
         os.path.join(run["log_dir"], "d4-input.cnf")],
        stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    run["check_out"], run["check_t0"] = out, time.monotonic()


def check_result(run, timed_out):
    """(count or None, seconds) of the finished or timed-out check."""
    run["check_out"].close()
    secs = round(time.monotonic() - run["check_t0"], 2)
    if timed_out:
        return None, secs
    text = open(os.path.join(run["work"], "check.out")).read()
    m = re.search(r"^c s exact arb int (\d+)", text, re.M)
    if not m:
        raise RuntimeError(f"sharpSAT gave no exact count for {run['name']}:\n" + text[-2000:])
    return int(m.group(1)), secs


def circuit_count(dnnf):
    """Model count of a saved FiFO circuit (smoothed, so every literal set to 1
    counts models over its atoms); children precede parents in the file."""
    with open(dnnf) as f:
        text = f.read()
    root = int(re.search(r":ROOT (\d+)", text).group(1))
    body = text[text.index(":NODES (") + len(":NODES ("):text.index(" :ATOMS")]
    val = []
    for kind, args in re.findall(r"\(:([FTLAO])([^()]*)\)", body):
        if kind == "F":
            val.append(0)
            continue
        if kind in "TL":              # an L node's argument is its literal, not a child
            val.append(1)
            continue
        kids = [val[int(x)] for x in args.split()]
        if kind == "A":
            p = 1
            for k in kids:
                p *= k
            val.append(p)
        else:
            val.append(sum(kids))
    return val[root]


def compiled(run, status, info):
    """The record of a compilation that has just ended: its times and sizes.
    Leaves the work directory (circuit, d4's input) for the check."""
    run["log"].close()
    d, work, name = run["log_dir"], run["work"], run["name"]
    end_file = os.path.join(d, "total-end")
    end = float(open(end_file).read()) if os.path.exists(end_file) else run["t_end"]
    slept = max(0.0, (run["t_end_wall"] - run["t0_wall"]) - (run["t_end"] - run["t0"]))
    ru = run["rusage"]
    rec = dict(info, status=status, wall_s=round(end - run["t0"], 2),
               clock_s=round(end - run["t0"] + slept, 2), slept_s=round(slept, 2),
               cpu_s=round(ru.ru_utime + ru.ru_stime, 2), timing="awake",
               exit_code=run["proc"].returncode, d4_peak_mb=round(run["peak_kb"] / 1024))
    rd = lambda f: open(os.path.join(d, f)).read().strip()
    if os.path.exists(os.path.join(d, "d4-start")):
        end = float(rd("d4-end")) if os.path.exists(os.path.join(d, "d4-end")) else run["t_end"]
        rec["d4_s"] = round(end - float(rd("d4-start")), 2)
    cnf = os.path.join(d, "d4-input.cnf")
    if os.path.exists(cnf):
        rec["cnf_vars"], rec["cnf_clauses"], rec["projected_vars"] = cnf_stats(cnf)
    if os.path.exists(os.path.join(d, "d4.nnf")):
        rec["nodes"], rec["edges"] = nnf_stats(os.path.join(d, "d4.nnf"))
    dnnf = os.path.join(work, name + ".dnnf")
    if status == "ok" and not (os.path.exists(dnnf) and os.path.exists(cnf)):
        rec["status"] = "error"
    if rec["status"] == "ok":
        rec["circuit_count"] = circuit_count(dnnf)
    return rec


def finish(run, rec, check):
    """Settle REC: with CHECK = (count or None, seconds) from sharpSAT, keep the
    circuit if the counts agree (or the check did not finish -- then it is
    recorded as unverified), else mark it wrong.  Cleans up the work directory."""
    d, work, name = run["log_dir"], run["work"], run["name"]
    cnf = os.path.join(d, "d4-input.cnf")
    dnnf = os.path.join(work, name + ".dnnf")
    dest = os.path.join(HERE, "circuits", name + ".dnnf")
    if check is not None:
        count, rec["count_check_s"] = check
        if count is None:
            rec["count_check"] = "timeout"
        else:
            rec["model_count"] = count
            rec["count_check"] = "agrees" if count == rec["circuit_count"] else "differs"
            if count != rec["circuit_count"]:
                rec["status"] = "wrong"
    if rec["status"] == "ok":
        shutil.move(dnnf, dest)
        rec["circuit"] = "circuits/" + name + ".dnnf"
        rec["circuit_bytes"] = os.path.getsize(dest)
    if rec["status"] != "ok" and os.path.exists(dest):
        os.remove(dest)               # never leave an earlier attempt's circuit behind
    with open(os.path.join(work, "marginals.log")) as f:
        lines = f.read().strip().split("\n")
    proj = [l for l in lines if l.startswith("; projecting onto")]
    if proj:
        rec["projection"] = proj[0][2:]
    if rec["status"] != "ok":
        rec["log_tail"] = [l for l in lines if not l.startswith("(MARGINAL")][-8:]
    if rec["status"] in ("error", "wrong") and os.path.exists(cnf):
        # keep the input so a crash or a wrong circuit can be reproduced
        keep = os.path.join(CRASHES, f"{name}-attempt{rec['attempt']}.cnf")
        os.makedirs(CRASHES, exist_ok=True)
        shutil.copy(cnf, keep)
        rec["kept_cnf"] = keep
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=float, required=True, help="seconds per compilation")
    # The whole-theory count is often far harder for sharpSAT than the projected
    # compilation is for d4 (grid4x4-1: d4 seconds, sharpSAT unfinished after
    # 20 minutes), and a check holds a compile slot, so it is kept short; a
    # circuit it does not finish on is kept as unverified.
    ap.add_argument("--verify-limit", type=float, default=120,
                    help="seconds for sharpSAT's count check of each circuit")
    ap.add_argument("--min-free-gb", type=float, default=1.0,
                    help="kill the largest d4 when available memory falls below this")
    ap.add_argument("--results", default=os.path.join(HERE, "results", "compile-d4.jsonl"))
    ap.add_argument("--work", default="/tmp/tp-d4")
    ap.add_argument("--sizes", default=",".join(SIZES))
    ap.add_argument("--jobs", type=int, default=4, help="compilations at once")
    ap.add_argument("--attempts", type=int, default=3,
                    help="tries in a row per problem whose runs end in an error or a wrong circuit")
    ap.add_argument("--d4-options", default="", help="extra d4 options, via shims/d4")
    ap.add_argument("--node-limit", type=int, default=None,
                    help="marginals.sh --node-limit: cap on the imported circuit "
                         "(FiFO's default 2,000,000 nodes)")
    ap.add_argument("--sbcl-heap-mb", type=int, default=8192,
                    help="SBCL heap for marginals.sh (reserved, not allocated)")
    a = ap.parse_args()

    real = {p: shutil.which(p) for p in ("d4", "sbcl")}
    for p, path in real.items():
        if not path or os.path.dirname(path) == SHIM:
            sys.exit(f"the real {p} must be on PATH (and {SHIM} must not be)")
    if not shutil.which("sharpSAT"):
        sys.exit("sharpSAT must be on PATH: it checks every circuit's count")
    d4_sha = hashlib.sha256(open(real["d4"], "rb").read()).hexdigest()[:12]
    os.makedirs(os.path.join(HERE, "circuits"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "scnf"), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.results)), exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    # last: the latest record of each problem; errors: its failed attempts in a row
    last, errors = {}, {}
    failed = ("error", "wrong")
    if os.path.exists(a.results):
        for r in map(json.loads, open(a.results)):
            last[r["instance"]] = r
            errors[r["instance"]] = errors.get(r["instance"], 0) + 1 if r["status"] in failed else 0

    def settled(name):
        r = last.get(name)
        return r is not None and (r["status"] == "ok" or
                                  (r["status"] in ("timeout", "memout") and r["limit_s"] >= a.limit))

    for size in a.sizes.split(","):
        problems = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, f"grid{size}-*.pddl")))
        names = [p[:-len(".pddl")] for p in problems]
        if not problems:
            print(f"no {size} problems; stopping", flush=True)
            break
        todo = [p for p, n in zip(problems, names)
                if not settled(n) and errors.get(n, 0) < a.attempts]
        print(f"{size}: {len(todo)} of {len(problems)} to compile", flush=True)
        runs = []
        for p in todo:
            name = p[:-len(".pddl")]
            work = os.path.join(a.work, name)
            shutil.rmtree(work, ignore_errors=True)
            os.makedirs(work)
            scnf, horizon = prepare(p, work)
            print(f"  {name}: theory at horizon {horizon}", flush=True)
            runs.append((name, scnf, horizon, work))
        running = []
        with open(a.results, "a") as res:
            while running or runs:
                while runs and len(running) < a.jobs:
                    name, scnf, horizon, work = runs.pop(0)
                    r = start(name, scnf, work, real, a.sbcl_heap_mb, a.d4_options,
                              a.node_limit, a.limit)
                    r["info"] = {"instance": name, "size": size, "horizon": horizon,
                                 "theory": "scnf/" + name + ".scnf", "limit_s": a.limit,
                                 "sbcl_heap_mb": a.sbcl_heap_mb, "jobs": a.jobs,
                                 "d4_options": a.d4_options, "node_limit": a.node_limit,
                                 "fifo_lisp": os.environ.get("FIFO_LISP", "installed"),
                                 "d4_sha": d4_sha,
                                 "attempt": errors.get(name, 0) + 1,
                                 "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
                    running.append(r)
                time.sleep(2)
                table = process_table()
                for r in running:
                    if "rec" not in r:
                        r["peak_kb"] = max(r["peak_kb"], d4_rss_kb(r["proc"].pid, table))
                low = available_bytes() < a.min_free_gb * 2**30
                tree_kb = lambda r: sum(table[p][1] for p in descendants(r["proc"].pid, table))
                compiling = [r for r in running if "rec" not in r]
                victim = max(compiling, key=tree_kb) if low and compiling else None
                for r in list(running):
                    if "rec" in r:
                        # phase 2: sharpSAT's count check of a finished circuit
                        if r["check"].poll() is not None:
                            check = check_result(r, False)
                        elif time.monotonic() - r["check_t0"] > a.verify_limit:
                            os.killpg(r["check"].pid, signal.SIGKILL)
                            r["check"].wait()
                            check = check_result(r, True)
                        else:
                            continue
                        rec = finish(r, r["rec"], check)
                    else:
                        # phase 1: the compilation
                        over = time.monotonic() - r["t0"] > a.limit
                        if reap(r):
                            status = "ok" if r["proc"].returncode == 0 else "error"
                        elif over or r is victim:
                            kill_tree(r)
                            status = "timeout" if over else "memout"
                        else:
                            continue
                        rec = compiled(r, status, r["info"])
                        if rec["status"] == "ok":
                            r["rec"] = rec
                            start_check(r)
                            continue
                        rec = finish(r, rec, None)
                    running.remove(r)
                    name = rec["instance"]
                    last[name] = rec
                    errors[name] = errors.get(name, 0) + 1 if rec["status"] in failed else 0
                    res.write(json.dumps(rec) + "\n")
                    res.flush()
                    print(f"  {name}: {rec['status']} {rec['wall_s']:.1f}s "
                          f"(d4 {rec.get('d4_s', '-')}s, peak {rec['d4_peak_mb']} MB, "
                          f"check {rec.get('count_check', '-')})", flush=True)
                    if rec["status"] in failed and errors[name] < a.attempts:
                        # d4's crashes and miscompilations are not repeatable
                        work = os.path.join(a.work, name)
                        shutil.rmtree(work, ignore_errors=True)
                        os.makedirs(work)
                        runs.append((name, theory_path(rec["theory"]), rec["horizon"], work))
        stuck = [n for n in names if last.get(n, {}).get("status") in ("timeout", "memout")
                 and last[n]["limit_s"] >= a.limit]
        if stuck:
            print(f"{size}: {', '.join(stuck)} did not compile within {a.limit:g}s; "
                  f"no larger size is tried at this limit", flush=True)
            break
    print("done", flush=True)


if __name__ == "__main__":
    main()
