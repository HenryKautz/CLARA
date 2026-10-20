#!/usr/bin/env python3
"""query-evidence.py -- time queries with evidence on the circuits compile-d4.py saved.

For each problem with a saved circuit (circuits/<problem>.dnnf), takes one evidence
file with two pinned observations -- evidence/<problem>-<first goal>-obs2.txt, the
first two drives of a shortest plan to the alphabetically first destination -- and
in one SBCL process: loads FiFO, loads the circuit (timed), then recomputes all
marginals conditioned on the evidence (ddnnf-marginals on the loaded circuit, as
marginals.sh --circuit --evidence-file does), REPEATS times, reporting the median.

Each answer is checked: every observed drive must get probability 1, and the
final-slice goal marginals must sum to 1 (the truck is at exactly one cell).
Appends one JSON record per problem to results/query-evidence.jsonl.

Usage: query-evidence.py [--max-size N] [--repeats R] [names...]"""
import argparse, glob, json, os, re, statistics, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
FIFO_LISP = os.environ.get("FIFO_LISP", os.path.expanduser("~/Programming/FiFO/lisp"))
# Homebrew's sbcl on the Mac (where ~/bin/sbcl may be a wrapper), else the one on PATH
SBCL = os.environ.get("SBCL_REAL") or (
    "/opt/homebrew/bin/sbcl" if os.path.exists("/opt/homebrew/bin/sbcl") else "sbcl")
OUT = os.path.join(HERE, "results", "query-evidence.jsonl")


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
    files = sorted(glob.glob(os.path.join(HERE, "evidence", f"{problem}-p*-obs2.txt")))
    return files[0] if files else None


def observed(evfile):
    """The (occurs ...) atoms the evidence pins, normalised to FiFO's printed form."""
    text = open(evfile).read()
    return [re.sub(r"\s+", " ", m).upper()
            for m in re.findall(r"\(occurs \([^()]*\) \d+\)", text)]


def run(problem, repeats):
    circuit = os.path.join(HERE, "circuits", problem + ".dnnf")
    evfile = evidence_for(problem)
    rec = {"instance": problem, "circuit": os.path.relpath(circuit, HERE),
           "evidence": os.path.relpath(evfile, HERE) if evfile else None,
           "repeats": repeats, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not evfile:
        rec["status"] = "no evidence file"
        return rec
    horizon = int(re.search(r"fifo-projection-horizon: (\d+)",
                            open(os.path.join(HERE, "scnf", problem + ".scnf")).read(2000))[1])
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
    obs = observed(evfile)
    bad = [a for a in obs if abs(marg.get(a, -1) - 1) > 1e-6]
    goal = sum(v for a, v in marg.items()
               if a.startswith("(HOLDS (AT TRUCK1") and a.endswith(f" {horizon})"))
    rec["observed"] = obs
    rec["goal_sum"] = round(goal, 6)
    if bad or abs(goal - 1) > 1e-4:
        rec["status"] = "check failed"
        rec["unpinned"] = bad
    else:
        rec["status"] = "ok"
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-size", type=int, default=7)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    names = a.names or sorted(
        (os.path.basename(f)[:-5] for f in glob.glob(os.path.join(HERE, "circuits", "*.dnnf"))),
        key=lambda n: (int(n[4:].split("x")[0]), int(n.split("-")[1])))
    names = [n for n in names if int(n[4:].split("x")[0]) <= a.max_size
             and os.path.exists(os.path.join(HERE, "circuits", n + ".dnnf"))]
    for n in names:
        rec = run(n, a.repeats)
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{n}: {rec['status']}"
              + (f"  load {rec['load_s']:.2f}s  query {rec['query_s']:.3f}s  goals sum "
                 f"{rec['goal_sum']}" if "query_s" in rec else ""), flush=True)


if __name__ == "__main__":
    main()
