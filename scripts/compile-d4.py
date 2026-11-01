#!/usr/bin/env python3
"""compile-d4.py --family F [--limit 7200] [--jobs 4]

Compile each problem of family F to a d-DNNF circuit with d4 (OldVersions/
ThreePackage/scripts/compile-d4.py, made family-generic and made to follow the
planning stage).

For each problem gridNxN-K, smallest grid first, once plans.jsonl says its size
is settled and its recognition problem exists:

  1. Build the EVIDENCE-FREE recognition theory recognize.sh scores: the
     problem at its recognition horizon (recognition/gridNxN-K.pddl), with the
     hypotheses of its goal.  It is the rec-problem.scnf of a recognize.sh
     --stop-after scnf run; saved as scnf/gridNxN-K.scnf.
  2. Compile it with  marginals.sh --solver d4 --project --save-circuit: the
     projection onto the actions, the final-slice goal atoms and the weighted
     atoms (exact: marginals.sh's Padoa check proves the kept atoms determine the
     rest), run d4, and save FiFO's circuit as circuits/gridNxN-K.dnnf.  Every
     pinned evidence file is a set of unit literals over those actions, so the
     circuit answers each by conditioning:
         marginals.sh --circuit circuits/gridNxN-K.dnnf --solver d4 \\
                      --evidence-file evidence/...-obs25.txt

The d4 that marginals.sh runs is shims/d4 (records d4's own time, its input CNF
and its dump); shims/sbcl gives SBCL an --sbcl-heap-mb heap.  Each compilation
gets --limit seconds of wall time (the whole marginals.sh run, theory import
included); d4's resident memory is sampled, and if the job's available memory
runs low the largest compilation is killed (status memout).

Every circuit is checked before it is kept: its model count must equal
SharpSAT-TD's exact count of d4's own input CNF over all its variables (equal
because the projection is exact).  d4 has returned wrong circuits before
(OldVersions/SimpleGrid, from 8x8 on).  A circuit whose count differs is
discarded (status wrong) and compiled again, up to --attempts in a row; one
whose check does not finish within --verify-limit is kept as unverified
(count_check "timeout").

STOP RULE: compilation stops after the first size where a problem times out or
runs out of memory.  Records: results/compile-d4.jsonl; an ok problem, or one
that timed out at this limit or longer, is not compiled again.
"""
import argparse, glob, hashlib, json, os, re, shutil, signal, subprocess, sys, time
import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--family", required=True)
ap.add_argument("--limit", type=float, default=7200, help="seconds per compilation")
ap.add_argument("--verify-limit", type=float, default=1800,
                help="seconds for sharpSAT's count check of each circuit")
ap.add_argument("--min-free-gb", type=float, default=8.0)
ap.add_argument("--jobs", type=int, default=4, help="compilations at once")
ap.add_argument("--attempts", type=int, default=3)
ap.add_argument("--sbcl-heap-mb", type=int, default=32768)
ap.add_argument("--node-limit", type=int, default=20000000,
                help="marginals.sh --node-limit: cap on the imported circuit (OldVersions/"
                     "ThreePackage grid5x5-3's 1.87M-node circuit overflowed FiFO's default, "
                     "2,000,000)")
ap.add_argument("--poll", type=float, default=60)
A = ap.parse_args()

FAM = C.Family(A.family)
HERE = FAM.dir
RESULTS = os.path.join(FAM.results, "compile-d4.jsonl")
PLANS = os.path.join(FAM.results, "plans.jsonl")
WORK = os.path.join(FAM.scratch, "d4")
CRASHES = os.path.join(FAM.scratch, "d4-crashes")
RECOGNIZE = shutil.which("recognize.sh")
MARGINALS = shutil.which("marginals.sh")


def plan_state():
    recs = C.load_jsonl(PLANS)
    return {r["size"] for r in recs if r["stage"] == "size"}, any(r["stage"] == "end" for r in recs)


def d4_rss_kb(pid, table):
    return max([table[p][1] for p in C.descendants(pid, table)
                if os.path.basename(table[p][2]) == "d4"] or [0])


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
    pids = [proc.pid] + C.descendants(proc.pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(3)
            pids += C.descendants(proc.pid)
    subprocess.run(["pkill", "-KILL", "-s", str(proc.pid)])
    reap(run, block=True)


def prepare(name, work):
    """recognize.sh --stop-after scnf: the evidence-free theory at the
    recognition horizon; returns (scnf path, horizon)."""
    out = os.path.join(work, "rec")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    r = subprocess.run(["bash", RECOGNIZE, FAM.domain, FAM.recognition_problem(name),
                        FAM.path("evidence", name + "-none.txt"),
                        "--evidence-kind", "fifo", "--stop-after", "scnf", "--out", out,
                        "--horizon", str(FAM.recognition_horizon(name)), "--planner-timeout", "none"],
                       cwd=work, capture_output=True, text=True,
                       env=C.env(heap_mb=A.sbcl_heap_mb))
    if r.returncode != 0:
        return None, f"recognize.sh failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    horizon = int(re.search(r"^Horizon H = (\d+)", r.stdout + r.stderr, re.M).group(1))
    scnf = FAM.path("scnf", name + ".scnf")
    shutil.copy(os.path.join(out, "rec-problem.scnf"), scnf)
    shutil.rmtree(out, ignore_errors=True)
    for f in glob.glob(glob.escape(out) + "-*"):
        os.remove(f)
    return scnf, horizon


def start(name, scnf, work, real):
    log_dir = os.path.join(work, "d4log")
    os.makedirs(log_dir, exist_ok=True)
    env = C.env(heap_mb=A.sbcl_heap_mb, extra=dict(D4_LOG_DIR=log_dir, D4_REAL=real["d4"]))
    log = open(os.path.join(work, "marginals.log"), "w")
    cmd = ["bash", "-c", 'bash "$0" "$@"; rc=$?; '
           'python3 -c \'import time; print("%.3f" % time.monotonic())\''
           ' > "$D4_LOG_DIR/total-end"; exit $rc',
           MARGINALS, scnf, "--solver", "d4", "--project", "--timeout", f"{A.limit:g}",
           "--save-circuit", os.path.join(work, name + ".dnnf")]
    if A.node_limit:
        cmd += ["--node-limit", str(A.node_limit)]
    proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    return {"name": name, "proc": proc, "t0": time.monotonic(), "log": log, "work": work,
            "log_dir": log_dir, "peak_kb": 0}


def cnf_stats(path):
    v = c = proj = None
    with open(path) as f:
        for line in f:
            if line.startswith("p cnf"):
                _, _, v, c = line.split()
            elif line.startswith("c p show"):
                proj = len(line.split()) - 4
            elif not line.startswith("c"):
                break
    return int(v), int(c), proj


def nnf_stats(path):
    nodes = edges = 0
    with open(path) as f:
        for line in f:
            if line[:1].isalpha():
                nodes += 1
            elif line[:1].isdigit():
                edges += 1
    return nodes, edges


def start_check(run):
    d = run["work"]
    out = open(os.path.join(d, "check.out"), "w")
    run["check"] = subprocess.Popen(
        ["sharpSAT", "-decot", "1", "-decow", "100", "-tmpdir", d, "-cs", "3500",
         os.path.join(run["log_dir"], "d4-input.cnf")],
        stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    run["check_out"], run["check_t0"] = out, time.monotonic()


def check_result(run, timed_out):
    run["check_out"].close()
    secs = round(time.monotonic() - run["check_t0"], 2)
    if timed_out:
        return None, secs
    text = open(os.path.join(run["work"], "check.out")).read()
    m = re.search(r"^c s exact arb int (\d+)", text, re.M)
    return (int(m.group(1)) if m else None), secs


def circuit_count(dnnf):
    with open(dnnf) as f:
        text = f.read()
    root = int(re.search(r":ROOT (\d+)", text).group(1))
    body = text[text.index(":NODES (") + len(":NODES ("):text.index(" :ATOMS")]
    val = []
    for kind, args in re.findall(r"\(:([FTLAO])([^()]*)\)", body):
        if kind == "F":
            val.append(0)
        elif kind in "TL":
            val.append(1)
        else:
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
    run["log"].close()
    d, work, name = run["log_dir"], run["work"], run["name"]
    end_file = os.path.join(d, "total-end")
    end = float(open(end_file).read()) if os.path.exists(end_file) else run["t_end"]
    ru = run["rusage"]
    rec = dict(info, status=status, wall_s=round(end - run["t0"], 2),
               cpu_s=round(ru.ru_utime + ru.ru_stime, 2),
               exit_code=run["proc"].returncode, d4_peak_mb=round(run["peak_kb"] / 1024))
    rd = lambda f: open(os.path.join(d, f)).read().strip()
    if os.path.exists(os.path.join(d, "d4-start")):
        e = float(rd("d4-end")) if os.path.exists(os.path.join(d, "d4-end")) else run["t_end"]
        rec["d4_s"] = round(e - float(rd("d4-start")), 2)
    cnf = os.path.join(d, "d4-input.cnf")
    if os.path.exists(cnf):
        rec["cnf_vars"], rec["cnf_clauses"], rec["projected_vars"] = cnf_stats(cnf)
    if os.path.exists(os.path.join(d, "d4.nnf")):
        rec["nodes"], rec["edges"] = nnf_stats(os.path.join(d, "d4.nnf"))
    dnnf = os.path.join(work, name + ".dnnf")
    if status == "ok" and not (os.path.exists(dnnf) and os.path.exists(cnf)):
        rec["status"] = "error"
    if rec["status"] == "error":
        text = open(os.path.join(work, "marginals.log"), errors="replace").read()
        if any(p in text for p in C.MEMOUT_PATTERNS):
            rec["status"] = "memout"
        elif "timed out after" in text or "stopped after the" in text:
            rec["status"] = "timeout"
    if rec["status"] == "ok":
        rec["circuit_count"] = circuit_count(dnnf)
    return rec


def finish(run, rec, check):
    d, work, name = run["log_dir"], run["work"], run["name"]
    cnf = os.path.join(d, "d4-input.cnf")
    dnnf = os.path.join(work, name + ".dnnf")
    dest = FAM.path("circuits", name + ".dnnf")
    if check is not None:
        count, rec["count_check_s"] = check
        if count is None:
            rec["count_check"] = "timeout"
        else:
            rec["model_count"] = str(count)
            rec["count_check"] = "agrees" if count == rec["circuit_count"] else "differs"
            if count != rec["circuit_count"]:
                rec["status"] = "wrong"
    if "circuit_count" in rec:
        rec["circuit_count"] = str(rec["circuit_count"])
    if rec["status"] == "ok":
        shutil.move(dnnf, dest)
        rec["circuit"] = "circuits/" + name + ".dnnf"
        rec["circuit_bytes"] = os.path.getsize(dest)
    if rec["status"] != "ok" and os.path.exists(dest):
        os.remove(dest)
    with open(os.path.join(work, "marginals.log"), errors="replace") as f:
        lines = f.read().strip().split("\n")
    proj = [l for l in lines if l.startswith("; projecting onto")]
    if proj:
        rec["projection"] = proj[0][2:]
    if rec["status"] != "ok":
        rec["log_tail"] = [l for l in lines if not l.startswith("(MARGINAL")][-8:]
    if rec["status"] in ("error", "wrong") and os.path.exists(cnf):
        keep = os.path.join(CRASHES, f"{name}-attempt{rec['attempt']}.cnf")
        os.makedirs(CRASHES, exist_ok=True)
        shutil.copy(cnf, keep)
        rec["kept_cnf"] = keep
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    real = {"d4": shutil.which("d4")}
    if not real["d4"] or os.path.dirname(real["d4"]) == C.SHIMS:
        sys.exit("the real d4 must be on PATH")
    if not shutil.which("sharpSAT"):
        sys.exit("sharpSAT must be on PATH: it checks every circuit's count")
    d4_sha = hashlib.sha256(open(real["d4"], "rb").read()).hexdigest()[:12]
    for d in ("circuits", "scnf"):
        os.makedirs(FAM.path(d), exist_ok=True)
    os.makedirs(FAM.results, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    last, errors = {}, {}
    failed = ("error", "wrong")
    for r in C.load_jsonl(RESULTS):
        last[r["instance"]] = r
        errors[r["instance"]] = errors.get(r["instance"], 0) + 1 if r["status"] in failed else 0

    def settled_rec(name):
        r = last.get(name)
        return r is not None and (r["status"] == "ok" or
                                  (r["status"] in ("timeout", "memout") and r["limit_s"] >= A.limit))

    C.say(f"{FAM.name}: d4, limit {A.limit:g}s, {A.jobs} jobs")
    for size in FAM.sizes:
        while True:
            sizes, ended = plan_state()
            if size in sizes or ended:
                break
            time.sleep(A.poll)
        if size not in sizes:
            C.say(f"{size}x{size}: never planned; stopping")
            break
        names = [p for p in FAM.problems([size]) if os.path.exists(FAM.recognition_problem(p))]
        todo = [n for n in names if not settled_rec(n) and errors.get(n, 0) < A.attempts]
        C.say(f"{size}x{size}: {len(todo)} of {len(names)} to compile")
        if not names:
            C.say(f"{size}x{size}: no recognition problems; stopping")
            break
        queue = []
        for name in todo:
            work = os.path.join(WORK, name)
            shutil.rmtree(work, ignore_errors=True)
            os.makedirs(work)
            queue.append((name, work))
        running = []
        while running or queue:
            while queue and len(running) < A.jobs:
                name, work = queue.pop(0)
                scnf, horizon = prepare(name, work)
                info = {"instance": name, "size": size, "horizon": horizon if scnf else None,
                        "theory": "scnf/" + name + ".scnf", "limit_s": A.limit,
                        "sbcl_heap_mb": A.sbcl_heap_mb, "jobs": A.jobs, "d4_sha": d4_sha,
                        "attempt": errors.get(name, 0) + 1, "started": C.now()}
                if scnf is None:
                    rec = dict(info, status="error", log_tail=C.log_tail(horizon))
                    C.append_jsonl(RESULTS, rec)
                    last[name] = rec
                    errors[name] = errors.get(name, 0) + 1
                    C.say(f"  {name}: theory failed")
                    continue
                C.say(f"  {name}: theory at horizon {horizon}")
                r = start(name, scnf, work, real)
                r["info"] = info
                running.append(r)
            time.sleep(2)
            table = C.process_table()
            for r in running:
                if "rec" not in r:
                    r["peak_kb"] = max(r["peak_kb"], d4_rss_kb(r["proc"].pid, table))
            low = C.available_bytes() < A.min_free_gb * 2**30
            compiling = [r for r in running if "rec" not in r]
            victim = max(compiling, key=lambda r: C.tree_rss_kb(r["proc"].pid, table)) \
                if low and compiling else None
            for r in list(running):
                if "rec" in r:
                    if r["check"].poll() is not None:
                        check = check_result(r, False)
                    elif time.monotonic() - r["check_t0"] > A.verify_limit:
                        os.killpg(r["check"].pid, signal.SIGKILL)
                        r["check"].wait()
                        check = check_result(r, True)
                    else:
                        continue
                    rec = finish(r, r["rec"], check)
                else:
                    over = time.monotonic() - r["t0"] > A.limit
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
                C.append_jsonl(RESULTS, rec)
                C.say(f"  {name}: {rec['status']} {rec['wall_s']:.1f}s (d4 {rec.get('d4_s', '-')}s, "
                      f"peak {rec['d4_peak_mb']} MB, check {rec.get('count_check', '-')})")
                if rec["status"] in failed and errors[name] < A.attempts:
                    work = os.path.join(WORK, name)
                    shutil.rmtree(work, ignore_errors=True)
                    os.makedirs(work)
                    queue.append((name, work))
        stuck = [n for n in names if last.get(n, {}).get("status") in ("timeout", "memout")]
        if stuck:
            C.say(f"{size}x{size}: {', '.join(stuck)} did not compile (timeout/memout); "
                  f"no larger size is tried")
            break
    C.say("done")


if __name__ == "__main__":
    main()
