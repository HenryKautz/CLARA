#!/usr/bin/env python3
"""run-benchmarks.py -- exact and approximate recognition on the R&G benchmarks.

For each generated instance (IntrusionDetectionCosts at H = 6, BlocksWorldCosts
at H = 15) and each evidence prefix evidence-K.txt (K = 1, 3, 5 by default):

  prepare      recognize.sh --stop-after scnf instantiates the theory at H with
               the observation monitor's axioms folded in, and writes the one
               literal to condition on (the (occur-in-order ...) assertion).
               Saved in theories/: <inst>-obsK.scnf, -assertion.txt, the
               theory's weighted CNF in the MCC-2024 dialect (the one SharpSAT-TD
               reads) without and with the evidence literal (.wcnf,
               -evidence.wcnf), and .map (DIMACS variable -> FiFO atom).
  max-term     recognize.sh --counter max-term: R&G's c(not O) - c(O), with the
               exact MaxSAT solver (bin/rc2-maxsat.py).
  sharpsat-td  recognize.sh --counter sharpsat-td: the exact posterior with the
               per-hypothesis baseline, P(h|O) proportional to
               P(h|T,O) / P(h|T) (uniform priors), by weighted model counting.
  d4           marginals.sh --solver d4 --save-circuit compiles the theory ONCE
               (circuits/<inst>-obsK.dnnf); its marginals are P(h|T).  The saved
               circuit is then queried with the assertion literal as a unit
               clamp for P(h|T,O) -- no recompilation -- and the posterior formed
               exactly as the sharpsat-td one is.  The two exact methods share no
               counting code, so where both finish each checks the other.
  d4-project   the same with marginals.sh --project: d4 compiles only the
               projection onto the actions, the final-slice goal atoms (the
               hypotheses among them), the weighted atoms and the assertion's
               atom, after a SAT check that these determine every other atom
               (so the marginals are exactly the full theory's).
               circuits/<inst>-obsK-projected.dnnf.
  ddnnf        FiFO's own d-DNNF compiler, a third exact method sharing no
               counting code with the other two: hypothesis-posterior (what
               recognize.sh --counter ddnnf runs) in an SBCL with a 48 GB heap.
  mc-sat       recognize.sh --counter mc-sat: MC-SAT sampling (WalkSAT v58), an
               APPROXIMATE but independent check on the exact posteriors.

Each run has a wall-clock limit (--limit, default 3600 s) on its whole process
tree, and the solvers inside get --timeout LIMIT too.  Runs go --jobs at a time.
Every finished run is appended to results/runs.jsonl at once, so a stopped sweep
resumes where it left off (a run with a record is not redone).

Usage: run-benchmarks.py [--limit S] [--jobs N] [--obs 1,3,5] [--match REGEX]
"""
import argparse, concurrent.futures as cf, json, os, re, shutil, signal
import subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.expanduser("~/bin")
FIFO_LISP = os.environ.get("FIFO_LISP", os.path.expanduser("~/lib/fifo/lisp"))
INSTANCES = {   # directory: (domain file, horizon H, true goal)
    "IntrusionDetectionCosts": ("intrusion-detection-costs.pddl", 6, "hyp0"),
    "BlocksWorldCosts": ("block-words-costs.pddl", 15, "hyp16"),
}
METHODS = ["max-term", "sharpsat-td", "d4", "d4-project", "ddnnf", "mc-sat"]
WORK = os.path.join(HERE, "work")
LOCK = threading.Lock()


def log(msg):
    with LOCK:
        print(time.strftime("%H:%M:%S ") + msg, flush=True)


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
        for c in kids.get(todo.pop(), []):
            found.append(c)
            todo.append(c)
    return found


def run(cmd, limit, cwd, logfile):
    """Run CMD in its own session; kill its whole process TREE at LIMIT seconds.
    The tree, not the process group: SBCL starts each solver as the leader of
    its own group, so a group kill leaves the solver running, orphaned (a
    sharpSAT outlived its timed-out run that way).  Returns (exit code or None
    on a timeout, wall seconds)."""
    t0 = time.monotonic()
    with open(logfile, "w") as lf:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            rc = p.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            pids = [p.pid] + descendants(p.pid)
            for sig in (signal.SIGTERM, signal.SIGKILL):
                for q in pids:
                    try:
                        os.kill(q, sig)
                    except ProcessLookupError:
                        pass
                if sig == signal.SIGTERM:
                    time.sleep(5)
                    # anything started meanwhile, and what is left
                    pids = pids + descendants(p.pid)
            p.wait()
            rc = None
    return rc, time.monotonic() - t0


def hypotheses(inst):
    """hyp0 .. hypN-1, from the problem's disjunctive goal."""
    text = open(os.path.join(HERE, inst, "problem.pddl")).read()
    return sorted(set(re.findall(r"\((hyp\d+)\)", text)), key=lambda h: int(h[3:]))


def hyp_atom(h, H):
    return f"(HOLDS ({h.upper()}) {H})"


def theory(inst, k):
    return os.path.join(HERE, "theories", f"{inst}-obs{k}")


def prepare(inst, k):
    """The theory, assertion, WCNFs and map for (INST, K); skipped if present."""
    dom, H, _ = INSTANCES[inst]
    root = theory(inst, k)
    if all(os.path.exists(root + s) for s in
           (".scnf", "-assertion.txt", ".wcnf", "-evidence.wcnf", ".map")):
        return
    base = os.path.join(WORK, f"prep-{inst}-obs{k}")   # all of it inside base, as in one()
    out = os.path.join(base, "run")
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(out)
    rc, _ = run(["bash", f"{BIN}/recognize.sh", os.path.join(HERE, inst, dom),
                 os.path.join(HERE, inst, "problem.pddl"),
                 os.path.join(HERE, inst, f"evidence-{k}.txt"),
                 "--horizon", str(H), "--stop-after", "scnf", "--out", out],
                3600, out, out + ".log")
    if rc != 0:
        sys.exit(f"prepare {inst} obs{k} failed: see {out}.log")
    os.makedirs(os.path.dirname(root), exist_ok=True)
    shutil.copy(os.path.join(out, "rec-problem.scnf"), root + ".scnf")
    shutil.copy(os.path.join(out, "rec-problem-assertion.txt"), root + "-assertion.txt")
    assertion = open(root + "-assertion.txt").read().strip()
    # The writer and the atom numbering FiFO's own counters use (wmc-write-wcnf,
    # mx--index-atoms over the clauses and the weighted atoms, deterministic).
    driver = f"""
(progn
  (wmc-write-wcnf "{root}.scnf" "{root}.wcnf" :dialect :mcc-2024)
  (wmc-write-wcnf "{root}.scnf" "{root}-evidence.wcnf" :dialect :mcc-2024
                  :evidence (list (let ((*read-eval* nil)) (read-from-string "{assertion}"))))
  (multiple-value-bind (clauses probs opts weight-forms) (rw--read-scnf "{root}.scnf")
    (declare (ignore probs opts))
    (let ((a2i (mx--index-atoms clauses (mapcar (lambda (wf) (rw--literal-atom-and-sign (second wf)))
                                                weight-forms)))
          (rows nil))
      (maphash (lambda (a i) (push (cons i a) rows)) a2i)
      (with-open-file (s "{root}.map" :direction :output :if-exists :supersede)
        (format s "c DIMACS variable -> FiFO atom, for {os.path.basename(root)}.wcnf and -evidence.wcnf~%")
        (dolist (r (sort rows #'< :key #'car))
          (format s "~D ~S~%" (car r) (cdr r)))))))
"""
    rc, _ = run(["sbcl", "--noinform", "--non-interactive",
                 "--eval", f'(load "{FIFO_LISP}/FiFO.lisp")',
                 "--eval", f'(load "{FIFO_LISP}/maxent.lisp")',
                 "--eval", f'(load "{FIFO_LISP}/wmc.lisp")',
                 "--eval", driver], 3600, out, out + "-wcnf.log")
    if rc != 0:
        sys.exit(f"writing the WCNF for {inst} obs{k} failed: see {out}-wcnf.log")
    shutil.rmtree(base, ignore_errors=True)
    log(f"prepared {inst} obs{k}")


def parse_summary(path):
    post, co, cn = {}, {}, {}
    with open(path) as f:
        next(f)
        for line in f:
            h, c_o, c_n, _d, _l, _pr, p = line.rstrip("\n").split("\t")
            post[h] = float(p)
            co[h], cn[h] = c_o, c_n
    return post, co, cn


def marginals_of(text):
    return {a: float(v) for a, v in re.findall(r"^\(MARGINAL (.*) (\S+)\)$", text, re.M)}


def run_recognize(inst, k, method, limit, out):
    dom, H, _ = INSTANCES[inst]
    rc, wall = run(["bash", f"{BIN}/recognize.sh", os.path.join(HERE, inst, dom),
                    os.path.join(HERE, inst, "problem.pddl"),
                    os.path.join(HERE, inst, f"evidence-{k}.txt"),
                    "--horizon", str(H), "--counter", method,
                    "--timeout", f"{limit:g}", "--out", out],
                   limit + 120, out, out + ".log")
    rec = {"wall_s": round(wall, 1)}
    summary = os.path.join(out, "summary.tsv")
    # a solver stopped by --timeout fails the run with "timed out after N s"
    if rc is None or "timed out after" in open(out + ".log").read():
        rec["status"] = "timeout"
    elif rc == 0 and os.path.exists(summary):
        post, co, cn = parse_summary(summary)
        rec.update(status="ok", posterior=post)
        if method == "max-term":
            rec.update(c_O=co, c_notO=cn)
    else:
        rec["status"] = "error"
    return rec


def run_d4(inst, k, limit, out, project=False):
    _, H, _ = INSTANCES[inst]
    root = theory(inst, k)
    assertion = open(root + "-assertion.txt").read().strip()
    os.makedirs(os.path.join(HERE, "circuits"), exist_ok=True)
    circ = os.path.join(HERE, "circuits",
                        f"{inst}-obs{k}{'-projected' if project else ''}.dnnf")
    # --project compiles only the projection onto the actions, the final-slice
    # goal atoms (the hypotheses among them) and the weighted atoms -- after a
    # SAT check that they determine every other atom, so the marginals are
    # exactly the full theory's.  The assertion's atom is kept too, so the
    # evidence can be clamped on the saved circuit.
    # (The assertion is the positive literal: complying with the observations.)
    proj = ["--project", "--project-also", assertion] if project else []
    rc, wall = run(["bash", f"{BIN}/marginals.sh", root + ".scnf", "--solver", "d4",
                    "--save-circuit", circ, "--timeout", f"{limit:g}"] + proj,
                   limit + 120, out, out + ".log")
    rec = {"compile_s": round(wall, 1)}
    text = open(out + ".log").read()
    if rc is None or "timed out after" in text:
        return dict(rec, status="timeout", wall_s=round(wall, 1))
    if rc != 0 or not os.path.exists(circ + "b"):
        return dict(rec, status="error", wall_s=round(wall, 1))
    uncond = marginals_of(text)
    m = re.search(r"(\d+) nodes", text)
    if m:
        rec["nodes"] = int(m.group(1))
    rec["circuit_bytes"] = os.path.getsize(circ)
    # Query the saved circuit (the binary file: the fast load) under the
    # assertion literal, a unit clamp, so nothing is recompiled.
    driver = f"""
(let* ((t0 (get-internal-real-time))
       (c (ddnnf-load "{circ}b"))
       (t1 (get-internal-real-time))
       (m (ddnnf-marginals nil :circuit c :verbose nil
                           :evidence (list (let ((*read-eval* nil)) (read-from-string "{assertion}")))))
       (t2 (get-internal-real-time)))
  (format t "~&QLOAD ~F~%QQUERY ~F~%"
          (/ (- t1 t0) internal-time-units-per-second 1.0d0)
          (/ (- t2 t1) internal-time-units-per-second 1.0d0))
  (dolist (pair m) (format t "(MARGINAL ~S ~F)~%" (car pair) (cdr pair))))
"""
    rcq, wq = run(["sbcl", "--noinform", "--non-interactive", "--dynamic-space-size", "32000",
                   "--eval", f'(load "{FIFO_LISP}/FiFO.lisp")',
                   "--eval", f'(load "{FIFO_LISP}/ddnnf.lisp")',
                   "--eval", driver], limit + 120, out, out + "-query.log")
    qtext = open(out + "-query.log").read()
    if rcq != 0:
        return dict(rec, status="error", wall_s=round(wall + wq, 1), stage="query")
    cond = marginals_of(qtext)
    rec["load_s"] = float(re.search(r"QLOAD (\S+)", qtext).group(1))
    rec["query_s"] = float(re.search(r"QQUERY (\S+)", qtext).group(1))
    hyps = hypotheses(inst)
    ratio = {}
    for h in hyps:
        a = hyp_atom(h, H)
        if a not in uncond or a not in cond:
            return dict(rec, status="error", wall_s=round(wall + wq, 1),
                        stage=f"no marginal for {a}")
        u, c = uncond[a], cond[a]
        ratio[h] = c / u if u > 0 else 0.0
    z = sum(ratio.values())
    post = {h: (r / z if z > 0 else 0.0) for h, r in ratio.items()}
    return dict(rec, status="ok", wall_s=round(wall + wq, 1), posterior=post,
                p_h=dict((h, uncond[hyp_atom(h, H)]) for h in hyps),
                p_h_given_o=dict((h, cond[hyp_atom(h, H)]) for h in hyps))


def run_ddnnf(inst, k, limit, out):
    """FiFO's own d-DNNF compiler, through hypothesis-posterior -- what
    recognize.sh --counter ddnnf runs -- but in an SBCL with a 48 GB heap and
    a node limit of 100 M: at the default heap it was exhausted within 3
    minutes on IntrusionDetectionCosts, and with the heap alone it stopped at
    the default 2 M nodes after 10."""
    _, H, _ = INSTANCES[inst]
    root = theory(inst, k)
    assertion = open(root + "-assertion.txt").read().strip()
    hyps = " ".join(hyp_atom(h, H) for h in hypotheses(inst))
    driver = f"""
(handler-case
    (progn
      (hypothesis-posterior "{root}.scnf" :hypotheses (quote ({hyps}))
                            :evidence (list (let ((*read-eval* nil)) (read-from-string "{assertion}")))
                            :baseline :per-hypothesis :counter "ddnnf"
                            :node-limit 100000000)
      (sb-ext:exit :code 0))
  (error (e) (format t "~&ERROR: ~A~%" e) (sb-ext:exit :code 1)))
"""
    rc, wall = run(["sbcl", "--dynamic-space-size", "48000", "--noinform", "--non-interactive",
                    "--eval", f'(load "{FIFO_LISP}/FiFO.lisp")',
                    "--eval", f"(setf *solver-timeout* {limit:g})",
                    "--eval", f'(load "{FIFO_LISP}/ddnnf.lisp")',
                    "--eval", f'(load "{FIFO_LISP}/hypotheses.lisp")',
                    "--eval", driver], limit, out, out + ".log")
    rec = {"wall_s": round(wall, 1), "heap_mb": 48000, "node_limit": 100000000}
    text = open(out + ".log").read()
    if rc is None:
        return dict(rec, status="timeout")
    if "Heap exhausted" in text:
        return dict(rec, status="out of memory (48 GB heap)")
    rows = re.findall(r"^\(HYPOTHESIS \(HOLDS \((HYP\d+)\) \d+\) :posterior (\S+)", text, re.M)
    if rc != 0 or not rows:
        return dict(rec, status="error")
    return dict(rec, status="ok", posterior={h.lower(): float(p) for h, p in rows})


def one(inst, k, method, limit, results):
    key = f"{inst}-obs{k}-{method}"
    # Everything a run writes -- its working directory, its logs (out + ".log"),
    # recognize.sh's scratch beside its --out -- stays inside base, and only
    # base is removed afterwards.  The first version globbed WORK/<key>* to
    # clean up, and "...-d4" is a prefix of "...-d4-project": a finishing full
    # d4 run deleted the log of the projected run on the same theory, whose
    # thread then failed to read it and recorded nothing.
    base = os.path.join(WORK, key)
    out = os.path.join(base, "run")
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(out)
    log(f"start {key}")
    t = time.strftime("%Y-%m-%dT%H:%M:%S")
    if method in ("d4", "d4-project"):
        rec = run_d4(inst, k, limit, out, project=(method == "d4-project"))
    elif method == "ddnnf":
        rec = run_ddnnf(inst, k, limit, out)
    else:
        rec = run_recognize(inst, k, method, limit, out)
    _, H, true_goal = INSTANCES[inst]
    rec = dict(instance=inst, n_obs=k, horizon=H, method=method, limit_s=limit,
               true_goal=true_goal, started=t, **rec)
    if rec["status"] == "ok":
        top = max(rec["posterior"].values())
        rec["argmax"] = sorted((h for h, p in rec["posterior"].items() if p == top),
                               key=lambda h: int(h[3:]))
    else:
        logs = [out + ".log", out + "-query.log"]
        tail = []
        for lf in logs:
            if os.path.exists(lf):
                tail += open(lf).read().strip().split("\n")[-6:]
        rec["log_tail"] = tail
    with LOCK:
        with open(results, "a") as f:
            f.write(json.dumps(rec) + "\n")
    shutil.rmtree(base, ignore_errors=True)
    log(f"done  {key}: {rec['status']} {rec['wall_s']} s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=float, default=3600)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--obs", default="1,3,5")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--match", default="")
    a = ap.parse_args()
    results = os.path.join(HERE, "results", "runs.jsonl")
    os.makedirs(os.path.dirname(results), exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    done = set()
    if os.path.exists(results):
        for line in open(results):
            if line.strip():
                r = json.loads(line)
                done.add((r["instance"], r["n_obs"], r["method"]))
    ks = [int(x) for x in a.obs.split(",")]
    todo = [(i, k, m) for i in INSTANCES for k in ks for m in a.methods.split(",")
            if re.search(a.match, f"{i}-obs{k}-{m}") and (i, k, m) not in done]
    for i, k in sorted({(i, k) for i, k, _ in todo}, key=lambda x: (list(INSTANCES).index(x[0]), x[1])):
        prepare(i, k)
    log(f"{len(todo)} runs, limit {a.limit:g} s, {a.jobs} at a time")
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for f in [ex.submit(one, i, k, m, a.limit, results) for i, k, m in todo]:
            f.result()
    log("all done")


if __name__ == "__main__":
    main()
