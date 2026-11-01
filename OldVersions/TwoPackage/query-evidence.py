#!/usr/bin/env python3
"""query-evidence.py -- time queries with evidence on the circuits compile-d4.py saved.

For each problem with a saved circuit (circuits/<problem>.dnnf), takes the evidence
file with the MOST pinned observations for its alphabetically first goal literal
(evidence/<problem>-<pkg>-<place>-obsK.txt, K = min(N-2, plan length)), and in one
SBCL process: loads FiFO, loads the circuit (timed), then recomputes all marginals
conditioned on the evidence (ddnnf-marginals on the loaded circuit, as
marginals.sh --circuit --evidence-file does), REPEATS times, reporting the median.

Each answer is checked two ways:
  * every observed action gets probability 1;
  * against an independent oracle: SharpSAT-TD on the same theory and evidence
    (marginals.sh --solver sharpsat-td on scnf/<problem>.scnf, which neither
    reads the circuit nor runs d4), compared on every atom the circuit keeps.
    max_abs_diff is the largest difference; the oracle gets --oracle-limit
    seconds and is skipped (oracle "timeout") if it needs longer.
A check also fails if no marginal is strictly between 0 and 1 (fractional_atoms),
since agreement on 0s and 1s alone says little.
Appends one JSON record per problem to results/query-evidence.jsonl.

Usage: query-evidence.py [--max-size N] [--repeats R] [names...]"""
import argparse, glob, json, os, re, statistics, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
FIFO_LISP = os.environ.get("FIFO_LISP", os.path.expanduser("~/lib/fifo/lisp"))
# Homebrew's sbcl on the Mac (where ~/bin/sbcl may be a wrapper), else the one on PATH
SBCL = os.environ.get("SBCL_REAL") or (
    "/opt/homebrew/bin/sbcl" if os.path.exists("/opt/homebrew/bin/sbcl") else "sbcl")
MARGINALS = os.path.expanduser("~/bin/marginals.sh")
OUT = os.path.join(HERE, "results", "query-evidence.jsonl")
TOL = 1e-6


def lisp_driver(circuit, evfile, repeats):
    return f"""
(let* ((t0 (get-internal-real-time))
       (c (ddnnf-load "{circuit}"))
       (load-s (/ (- (get-internal-real-time) t0) internal-time-units-per-second 1.0d0))
       (times nil) (result nil))
  (dotimes (i {repeats})
    (let ((t1 (get-internal-real-time)))
      (setf result (ddnnf-marginals nil :circuit c :evidence-file "{evfile}" :verbose nil))
      (push (/ (- (get-internal-real-time) t1) internal-time-units-per-second 1.0d0) times)))
  (format t "~&QLOAD ~F~%" load-s)
  (format t "QTIMES~{{ ~F~}}~%" (reverse times))
  (dolist (pair result)
    (format t "QMARG ~S ~F~%" (car pair) (cdr pair))))
"""


def evidence_for(problem):
    """The obsK file with the largest K for the problem's first goal literal."""
    files = glob.glob(os.path.join(HERE, "evidence", f"{problem}-pkg*-obs*.txt"))
    if not files:
        return None
    goal = min(re.match(r".*-(pkg\d+-p\d+-\d+)-obs\d+\.txt$", f).group(1) for f in files)
    mine = [f for f in files if f"-{goal}-obs" in f]
    return max(mine, key=lambda f: int(re.search(r"-obs(\d+)\.txt$", f).group(1)))


def observed(evfile):
    """The (occurs ...) atoms the evidence pins, normalised to FiFO's printed form."""
    text = open(evfile).read()
    return [re.sub(r"\s+", " ", m).upper()
            for m in re.findall(r"\(occurs \([^()]*\) \d+\)", text)]


def oracle(problem, evfile, limit):
    """{atom: marginal} from SharpSAT-TD on the theory, or None on a timeout."""
    scnf = os.path.join(HERE, "scnf", problem + ".scnf")
    try:
        p = subprocess.run(["bash", MARGINALS, scnf, "--solver", "sharpsat-td",
                            "--evidence-file", evfile, "--timeout", f"{limit:g}"],
                           capture_output=True, text=True, timeout=limit + 60, cwd="/tmp")
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        return None
    return {a: float(v) for a, v in re.findall(r"^\(MARGINAL (.*) (\S+)\)$", p.stdout, re.M)}


def run(problem, repeats, oracle_limit):
    circuit = os.path.join(HERE, "circuits", problem + ".dnnf")
    evfile = evidence_for(problem)
    rec = {"instance": problem, "circuit": os.path.relpath(circuit, HERE),
           "evidence": os.path.relpath(evfile, HERE) if evfile else None,
           "repeats": repeats, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not evfile:
        rec["status"] = "no evidence file"
        return rec
    t = time.time()
    p = subprocess.run([SBCL, "--dynamic-space-size", "12288", "--control-stack-size", "1000MB",
                        "--noinform", "--non-interactive",
                        "--eval", f'(load "{FIFO_LISP}/FiFO.lisp")',
                        "--eval", f'(load "{FIFO_LISP}/ddnnf.lisp")',
                        "--eval", lisp_driver(circuit, evfile, repeats)],
                       capture_output=True, text=True)
    rec["wall_s"] = round(time.time() - t, 2)
    out = p.stdout
    if p.returncode != 0 or "QLOAD" not in out:
        rec["status"] = "error"
        rec["log_tail"] = (p.stdout + p.stderr).splitlines()[-8:]
        return rec
    rec["load_s"] = float(re.search(r"QLOAD (\S+)", out)[1])
    times = [float(x) for x in re.search(r"QTIMES (.*)", out)[1].split()]
    rec["query_times_s"] = times
    rec["query_s"] = statistics.median(times)
    marg = {a: float(v) for a, v in re.findall(r"QMARG (.*) (\S+)$", out, re.M)}
    rec["atoms"] = len(marg)
    # a comparison over nothing but 0s and 1s would say little
    rec["fractional_atoms"] = sum(1 for v in marg.values() if TOL < v < 1 - TOL)
    obs = observed(evfile)
    rec["observed"] = obs
    bad = [a for a in obs if abs(marg.get(a, -1) - 1) > TOL]
    t = time.time()
    ref = oracle(problem, evfile, oracle_limit)
    rec["oracle_s"] = round(time.time() - t, 2)
    if ref is None:
        rec["oracle"] = "timeout or error"
    else:
        missing = [a for a in marg if a not in ref]
        diffs = [abs(marg[a] - ref[a]) for a in marg if a in ref]
        rec["oracle"] = "sharpsat-td"
        rec["compared_atoms"] = len(diffs)
        rec["max_abs_diff"] = max(diffs) if diffs else None
        if missing:
            rec["oracle_missing"] = missing[:10]
    if bad or not rec["fractional_atoms"] or \
            (ref is not None and (not rec["compared_atoms"] or rec["max_abs_diff"] > TOL
                                    or "oracle_missing" in rec)):
        rec["status"] = "check failed"
        rec["unpinned"] = bad
    else:
        rec["status"] = "ok"
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-size", type=int, default=7)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--oracle-limit", type=float, default=600)
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    names = a.names or sorted(
        (os.path.basename(f)[:-5] for f in glob.glob(os.path.join(HERE, "circuits", "*.dnnf"))),
        key=lambda n: (int(n[4:].split("x")[0]), int(n.split("-")[1])))
    names = [n for n in names if int(n[4:].split("x")[0]) <= a.max_size
             and os.path.exists(os.path.join(HERE, "circuits", n + ".dnnf"))]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for n in names:
        rec = run(n, a.repeats, a.oracle_limit)
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{n}: {rec['status']}"
              + (f"  load {rec['load_s']:.2f}s  query {rec['query_s']:.3f}s  "
                 f"oracle {rec['oracle']}"
                 + (f" max diff {rec['max_abs_diff']:.1e} over {rec['compared_atoms']} atoms"
                    if rec.get("max_abs_diff") is not None else "")
                 if "query_s" in rec else ""), flush=True)


if __name__ == "__main__":
    main()
