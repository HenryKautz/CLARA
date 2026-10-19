#!/usr/bin/env python3
"""verify-count.py -- a longer count check for circuits compile-d4.py could not verify.

compile-d4.py checks each circuit against sharpSAT's count of d4's own input CNF,
but gives that check only --verify-limit (120 s) and deletes the CNF afterwards.
This script redoes the check with a long limit, from the theory itself:

  1. FiFO writes circuits/NAME.scnf as plain DIMACS (propositionalize, :CNF --
     weights become comments, so the count is the theory's model count);
  2. sharpSAT counts it exactly, over all its variables;
  3. the count must equal the circuit's model count (circuits/NAME.dnnf, with
     every literal 1), which compile-d4.py's circuit_count computes.

The circuit is projected, but marginals.sh's Padoa check proved that the kept
atoms determine every other atom, so each projected model extends to exactly
one model of the theory and the two counts agree.  Run it first on a circuit
that compile-d4.py did verify (its model_count is in results/compile-d4.jsonl)
to confirm the method.  One JSON record per circuit is appended to --results.

    verify-count.py grid6x6-3 grid7x7-2 --limit 14400
"""
import argparse, importlib.util, json, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("compile_d4", os.path.join(HERE, "compile-d4.py"))
compile_d4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compile_d4)


def fifo_lisp():
    d = os.environ.get("FIFO_LISP") or os.path.expanduser("~/lib/fifo/lisp")
    path = os.path.join(d, "FiFO.lisp")
    if not os.path.exists(path):
        sys.exit(f"no FiFO.lisp at {path}: set FIFO_LISP or run FiFO's make install")
    return path


def write_cnf(scnf, cnf):
    form = f'(propositionalize "{scnf}" :cnffile "{cnf}" :mapfile "{cnf}.map" :cnf-format (quote cnf))'
    r = subprocess.run(["sbcl", "--noinform", "--non-interactive",
                        "--eval", f'(load "{fifo_lisp()}")', "--eval", form],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(cnf):
        sys.exit(f"propositionalize failed on {scnf}:\n{r.stdout}\n{r.stderr}")


def sharpsat_count(cnf, limit, cache_mb, tmpdir):
    """(exact count or None if it timed out, seconds)."""
    t0 = time.monotonic()
    try:
        r = subprocess.run(["sharpSAT", "-decot", "1", "-decow", "100", "-tmpdir", tmpdir,
                            "-cs", str(cache_mb), cnf],
                           capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return None, round(time.monotonic() - t0, 1)
    m = re.search(r"^c s exact arb int (\d+)", r.stdout, re.M)
    if not m:
        sys.exit(f"sharpSAT gave no exact count for {cnf}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return int(m.group(1)), round(time.monotonic() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+", help="circuit names, e.g. grid6x6-3")
    ap.add_argument("--limit", type=float, default=14400, help="seconds for each sharpSAT count")
    ap.add_argument("--cache-mb", type=int, default=16000, help="sharpSAT component cache")
    ap.add_argument("--results", default=os.path.join(HERE, "results", "verify-count.jsonl"))
    a = ap.parse_args()
    for name in a.names:
        scnf = os.path.join(HERE, "circuits", name + ".scnf")
        dnnf = os.path.join(HERE, "circuits", name + ".dnnf")
        for f in (scnf, dnnf):
            if not os.path.exists(f):
                sys.exit(f"missing {f} (a split circuit is rebuilt with cat {name}.dnnf.part-*)")
        rec = {"instance": name, "limit_s": a.limit, "cache_mb": a.cache_mb,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
        rec["circuit_count"] = compile_d4.circuit_count(dnnf)
        with tempfile.TemporaryDirectory() as d:
            cnf = os.path.join(d, name + ".cnf")
            write_cnf(scnf, cnf)
            rec["cnf_vars"], rec["cnf_clauses"], _ = compile_d4.cnf_stats(cnf)
            count, rec["count_s"] = sharpsat_count(cnf, a.limit, a.cache_mb, d)
        if count is None:
            rec["count_check"] = "timeout"
        else:
            rec["model_count"] = count
            rec["count_check"] = "agrees" if count == rec["circuit_count"] else "differs"
        with open(a.results, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{name}: {rec['count_check']} (circuit {rec['circuit_count']}, "
              f"sharpSAT {rec.get('model_count', '-')}, {rec['count_s']} s)", flush=True)


if __name__ == "__main__":
    main()
