#!/usr/bin/env python3
"""compile-d4.py -- compile each SimpleGrid problem to a d-DNNF circuit with d4.

For each problem gridNxN-K.pddl, smallest grid first:

  1. Build the EVIDENCE-FREE recognition theory recognize.sh scores: the problem
     at its recognition horizon H (the largest per-goal feasible horizon), with
     the goal literals as hypotheses.  It is the rec-problem.scnf of a
     recognize.sh run (the run's own evidence goes to a separate file and is not
     used); saved as scnf/gridNxN-K.scnf.
  2. Compile it with  marginals.sh --solver d4 --project --save-circuit, which
     projects onto the actions, the final-slice goal atoms and the weighted atoms
     (after checking that they determine every other atom, so the projection is
     exact), runs d4, and saves FiFO's circuit as circuits/gridNxN-K.dnnf.  Any
     pinned observation is a unit literal over those actions, so the saved circuit
     answers every evidence file by conditioning, without recompiling:
         marginals.sh --circuit circuits/gridNxN-K.dnnf --solver d4 \\
                      --evidence-file evidence/...-obsN.txt

The d4 that marginals.sh runs is shims/d4, which records d4's own time, its
input CNF and its circuit dump; its sbcl is shims/sbcl, which gives SBCL an
--sbcl-heap-mb heap (SBCL's default 1 GB is too small to import a circuit of
~100k nodes).  Each compilation gets --limit seconds of AWAKE time (the whole
marginals.sh run), on CLOCK_UPTIME_RAW -- time.monotonic() on macOS -- which stops
while the Mac sleeps, so a suspend neither inflates a time nor times a run out.
Each record also has clock_s (wall clock, sleep included), slept_s and cpu_s (the
run's user + system time, from os.wait4), and is appended to --results the
moment the run ends.  Run the sweep under caffeinate -i to keep the Mac from
idling to sleep in the first place.  While a compilation runs, d4's resident memory is
sampled, so a run that times out still reports how large d4 had grown.  If
available memory runs low, the largest d4 is killed (status memout) rather than
let the machine swap.  The problems of one grid size compile in parallel; if
none of them finishes, larger grids are not tried.

Every circuit is checked before it is kept: its model count (all literals 1 in
the smoothed circuit) must equal the number of truck walks the theory allows,
counted directly by dynamic programming (walk_count).  d4 sometimes returns a
wrong circuit -- from 8x8 on, repeated runs on the same CNF give different
counts -- and nothing else would notice.  A circuit that fails is discarded
(status wrong) and the problem is tried again, like a crash.

One JSON line per problem goes to --results; problems already there are skipped,
except those whose last attempt ended in an error or a wrong circuit, which are
tried again (up to --attempts in a row).  A recorded ok circuit that was never
checked is checked first.
"""
import argparse, glob, hashlib, json, os, re, shutil, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
MARGINALS = os.path.expanduser("~/bin/marginals.sh")
SHIM = os.path.join(HERE, "shims")
CRASHES = "/tmp/sg-d4-crashes"
DOMAIN = "clara-logistics-old.pddl"
SIZES = ["3x3", "4x4", "5x5", "6x6", "7x7", "8x8", "9x9", "10x10"]


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
    records its exit code, its CPU time (os.wait4's rusage: the process and every
    descendant it waited for) and the awake and wall clocks at that moment.
    Returns whether it has ended.  Popen.poll/wait are not used after this, so
    the exit status is not read twice."""
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
    (scnf path in scnf/, horizon)."""
    name = problem[:-len(".pddl")]
    evs = sorted(glob.glob(os.path.join(HERE, "evidence", name + "-*-obs1.txt")))
    if evs:
        ev = evs[0]
    else:
        # A problem generated for compilation only has no evidence files.  The
        # theory does not depend on the evidence (only the horizon could, and one
        # observation at slice 1 never raises it), so any one legal first drive
        # will do -- the truck starts at p1-1.
        ev = os.path.join(work, "first-drive.txt")
        with open(ev, "w") as f:
            f.write("(and\n  (occurs (drive truck1 p1-1 p2-1) 1))\n")
    out = os.path.join(work, "rec")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    r = subprocess.run(["bash", RECOGNIZE, DOMAIN, os.path.join(HERE, problem), ev,
                        "--evidence-kind", "fifo", "--counter", "max-term", "--out", out],
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
               SBCL_HEAP_MB=str(heap_mb), D4_EXTRA=d4_options,
               SBCL_NODE_LIMIT=str(node_limit or ""))
    log = open(os.path.join(work, "marginals.log"), "w")
    # The run notes the moment it ends, so the total time does not depend on how
    # often the loop below polls -- on the awake clock (CLOCK_UPTIME_RAW, which
    # is time.monotonic() here), like every duration this script records.
    cmd = ["bash", "-c", 'bash "$0" "$@"; rc=$?; '
           'python3 -c \'import time; print("%.3f" % time.monotonic())\''
           ' > "$D4_LOG_DIR/total-end"; exit $rc',
           # --timeout: FiFO bounds d4 by *solver-timeout*, whose 600 s default
           # would otherwise end a longer compilation before this script's limit
           MARGINALS, scnf, "--solver", "d4", "--project", "--timeout", f"{limit:g}",
           "--save-circuit", os.path.join(work, name + ".dnnf")]
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


def walk_count(scnf):
    """Models of the theory over its projected atoms, counted without any solver:
    the truck starts at p1-1 and takes H-1 steps, each a drive to a grid
    neighbour or a wait, and must end on a goal cell.  (The drives determine
    the final-slice goal atoms, so walks and projected models correspond one to
    one.)  Agrees with sharpSAT on every 3x3-7x7 problem."""
    with open(scnf) as f:
        head = "".join(next(f, "") for _ in range(5))
    horizon = int(re.search(r"fifo-projection-horizon: (\d+)", head).group(1))
    goals = {(int(a), int(b)) for a, b in
             re.findall(r"P(\d+)-(\d+)", re.search(r"fifo-projection-goal: (.*)", head).group(1))}
    n = int(re.search(r"grid(\d+)x", os.path.basename(scnf)).group(1))
    ways = {(1, 1): 1}
    for _ in range(horizon - 1):
        nxt = {}
        for (r, c), w in ways.items():
            for q in ((r, c), (r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 1 <= q[0] <= n and 1 <= q[1] <= n:
                    nxt[q] = nxt.get(q, 0) + w
        ways = nxt
    return sum(w for q, w in ways.items() if q in goals)


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


def verify(rec, dnnf, scnf):
    """Check the circuit's count; mark REC wrong (and return False) if it is off."""
    rec["model_count"] = walk_count(scnf)
    rec["circuit_count"] = circuit_count(dnnf)
    if rec["circuit_count"] != rec["model_count"]:
        rec["status"] = "wrong"
        return False
    return True


def finish(run, status, info):
    run["log"].close()
    d, work, name = run["log_dir"], run["work"], run["name"]
    end_file = os.path.join(d, "total-end")
    end = float(open(end_file).read()) if os.path.exists(end_file) else run["t_end"]
    # wall_s: awake time (the clock stops while the Mac sleeps); clock_s: wall
    # clock including any sleep; slept_s: the difference; cpu_s: user + system
    # time of the run's process tree (descendants a timeout killed are missed).
    # sleep = wall-clock minus awake time between start and reaping; clock_s is
    # the run's own span (to its end-of-run stamp) plus that sleep
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
    if os.path.exists(os.path.join(d, "d4-input.cnf")):
        rec["cnf_vars"], rec["cnf_clauses"], rec["projected_vars"] = \
            cnf_stats(os.path.join(d, "d4-input.cnf"))
    if os.path.exists(os.path.join(d, "d4.nnf")):
        rec["nodes"], rec["edges"] = nnf_stats(os.path.join(d, "d4.nnf"))
    dnnf = os.path.join(work, name + ".dnnf")
    dest = os.path.join(HERE, "circuits", name + ".dnnf")
    if status == "ok" and os.path.exists(dnnf) and verify(rec, dnnf, theory_path(info["theory"])):
        shutil.move(dnnf, dest)
        rec["circuit"] = "circuits/" + name + ".dnnf"
        rec["circuit_bytes"] = os.path.getsize(dest)
    elif status == "ok" and not os.path.exists(dnnf):
        rec["status"] = "error"
    if rec["status"] != "ok" and os.path.exists(dest):
        os.remove(dest)               # never leave an earlier attempt's circuit behind
    with open(os.path.join(work, "marginals.log")) as f:
        lines = f.read().strip().split("\n")
    proj = [l for l in lines if l.startswith("; projecting onto")]
    if proj:
        rec["projection"] = proj[0][2:]
    if rec["status"] != "ok":
        rec["log_tail"] = [l for l in lines if not l.startswith("(MARGINAL")][-8:]
    if rec["status"] in ("error", "wrong") and os.path.exists(os.path.join(d, "d4-input.cnf")):
        # d4 sometimes crashes (bus error / segfault) or returns a wrong circuit
        # on a CNF it compiles correctly on another try; keep the input so the
        # failure can be reproduced
        keep = os.path.join(CRASHES, f"{name}-attempt{info['attempt']}.cnf")
        os.makedirs(CRASHES, exist_ok=True)
        shutil.copy(os.path.join(d, "d4-input.cnf"), keep)
        rec["kept_cnf"] = keep
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=float, default=1800, help="seconds per compilation")
    ap.add_argument("--min-free-gb", type=float, default=1.0,
                    help="kill the largest d4 when available memory falls below this")
    ap.add_argument("--results", default=os.path.join(HERE, "results", "compile-d4.jsonl"))
    ap.add_argument("--work", default="/tmp/sg-d4")
    ap.add_argument("--sizes", default=",".join(SIZES))
    ap.add_argument("--jobs", type=int, default=4, help="compilations at once")
    ap.add_argument("--attempts", type=int, default=3,
                    help="tries in a row per problem whose runs end in an error or a wrong "
                         "circuit (d4 crashes, and miscompiles, at random)")
    ap.add_argument("--redo", action="store_true",
                    help="compile every problem again, even those already recorded")
    ap.add_argument("--d4-options", default="",
                    help="extra d4 options, appended to FiFO's (via shims/d4); e.g. "
                         "'--cache-store-strategy all --cache-size-first-page 268435456 "
                         "--cache-size-additional-page 268435456', with which d4 "
                         "miscompiles less often on 8x8")
    ap.add_argument("--node-limit", type=int, default=None,
                    help="raise FiFO's *ddnnf-node-limit* (default 2,000,000), which "
                         "caps the imported circuit (via shims/sbcl)")
    ap.add_argument("--retry", default="",
                    help="comma-separated problems to compile again whatever their "
                         "last status (e.g. a timeout caused by swapping)")
    ap.add_argument("--sbcl-heap-mb", type=int, default=8192,
                    help="SBCL heap for marginals.sh (reserved, not allocated)")
    a = ap.parse_args()

    real = {p: shutil.which(p) for p in ("d4", "sbcl")}
    for p, path in real.items():
        if not path or os.path.dirname(path) == SHIM:
            sys.exit(f"the real {p} must be on PATH (and {SHIM} must not be)")
    # which d4 binary made each record (the d4 in use changed when its
    # heap-overflow bug was fixed, d4v2 c11210d)
    d4_sha = hashlib.sha256(open(real["d4"], "rb").read()).hexdigest()[:12]
    os.makedirs(os.path.join(HERE, "circuits"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "scnf"), exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    # done: the latest record of each problem; errors: its failed attempts since
    # its last success.  Only records made with this FiFO (FIFO_LISP) and this d4
    # binary count -- a different importer, or the d4 before its heap-overflow
    # fix (whose records have no d4_sha), is a different experiment.
    done, errors = {}, {}
    failed = ("error", "wrong")
    lisp = os.environ.get("FIFO_LISP", "installed")
    if os.path.exists(a.results) and not a.redo:
        for r in map(json.loads, open(a.results)):
            if r.get("fifo_lisp", "installed") != lisp or r.get("d4_sha") != d4_sha:
                continue
            done[r["instance"]] = r
            errors[r["instance"]] = errors.get(r["instance"], 0) + 1 if r["status"] in failed else 0
    # Circuits recorded before checking existed are checked now; a wrong one gets
    # a record of its own (status wrong) and is compiled again.
    for name, r in sorted(done.items()):
        if r["status"] == "ok" and "circuit_count" not in r:
            rec = dict(r, checked_later=time.strftime("%Y-%m-%dT%H:%M:%S"))
            path = os.path.join(HERE, rec["circuit"])
            if not verify(rec, path, theory_path(rec["theory"])):
                os.remove(path)
                for k in ("circuit", "circuit_bytes"):
                    rec.pop(k, None)
            print(f"  {name}: checked saved circuit, {rec['status']} "
                  f"(count {rec['circuit_count']}, expected {rec['model_count']})", flush=True)
            done[name] = rec
            errors[name] = 1 if rec["status"] == "wrong" else 0
            with open(a.results, "a") as res:
                res.write(json.dumps(rec) + "\n")

    for name in filter(None, a.retry.split(",")):
        done.pop(name, None)
        errors[name] = 0
    for size in a.sizes.split(","):
        problems = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, f"grid{size}-*.pddl")))
        names = [p[:-len(".pddl")] for p in problems]
        if not problems:
            print(f"no {size} problems; stopping", flush=True)
            break
        todo = [p for p in problems
                if done.get(p[:-len(".pddl")], {}).get("status", "error") in failed
                and errors.get(p[:-len(".pddl")], 0) < a.attempts]
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
                    r["peak_kb"] = max(r["peak_kb"], d4_rss_kb(r["proc"].pid, table))
                low = available_bytes() < a.min_free_gb * 2**30
                tree_kb = lambda r: sum(table[p][1] for p in descendants(r["proc"].pid, table))
                victim = max(running, key=tree_kb) if low else None
                for r in list(running):
                    # the limit is on awake time, so a sleep does not time a run out
                    over = time.monotonic() - r["t0"] > a.limit
                    if reap(r):
                        status = "ok" if r["proc"].returncode == 0 else "error"
                    elif over or r is victim:
                        kill_tree(r)
                        status = "timeout" if over else "memout"
                    else:
                        continue
                    rec = finish(r, status, r["info"])
                    running.remove(r)
                    done[rec["instance"]] = rec
                    errors[rec["instance"]] = \
                        errors.get(rec["instance"], 0) + 1 if rec["status"] in failed else 0
                    res.write(json.dumps(rec) + "\n")
                    res.flush()
                    print(f"  {rec['instance']}: {rec['status']} {rec['wall_s']:.1f}s "
                          f"(d4 {rec.get('d4_s', '-')}s, peak {rec['d4_peak_mb']} MB)", flush=True)
                    name = rec["instance"]
                    if rec["status"] in failed and errors[name] < a.attempts:
                        # d4's crashes and miscompilations are not repeatable:
                        # the same theory, compiled again, often passes
                        work = os.path.join(a.work, name)
                        shutil.rmtree(work, ignore_errors=True)
                        os.makedirs(work)
                        runs.append((name, theory_path(rec["theory"]), rec["horizon"], work))
        if not any(done.get(n, {}).get("status") == "ok" for n in names):
            print(f"no {size} problem compiled within the limit; stopping", flush=True)
            break
    print("done", flush=True)


if __name__ == "__main__":
    main()
