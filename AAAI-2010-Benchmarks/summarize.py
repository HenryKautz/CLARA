#!/usr/bin/env python3
"""summarize.py -- Markdown tables from results/runs.jsonl (run-benchmarks.py).

Prints, for the README:
  * theory sizes (from theories/*.wcnf);
  * per instance and evidence prefix, each method's status, time, recognized
    hypothesis (argmax, ties kept) and the posterior and rank of the true goal;
  * the agreement of the two exact methods (largest posterior difference);
  * d4's compilation: time, circuit size, load and query time.
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["IntrusionDetectionCosts", "BlocksWorldCosts"]
METHODS = ["max-term", "sharpsat-td", "d4", "d4-project", "ddnnf", "mc-sat"]
EXACT = ["sharpsat-td", "d4", "d4-project", "ddnnf"]


def load():
    recs = {}
    with open(os.path.join(HERE, "results", "runs.jsonl")) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                recs[(r["instance"], r["n_obs"], r["method"])] = r   # the last record wins
    return recs


def fmt_time(s):
    if s is None:
        return "–"
    if s < 60:
        return f"{s:.1f} s"
    if s < 3600:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.2f} h"


def rank(post, h):
    """1-based rank of H, ties sharing the best rank, and the tie size."""
    p = post[h]
    better = sum(1 for v in post.values() if v > p + 1e-12)
    tied = sum(1 for v in post.values() if abs(v - p) <= 1e-12)
    return better + 1, tied


def sizes():
    print("| Theory | H | Variables | Clauses |")
    print("|---|--:|--:|--:|")
    for inst in ORDER:
        for path in sorted(glob.glob(os.path.join(HERE, "theories", f"{inst}-obs*.wcnf"))):
            if path.endswith("-evidence.wcnf"):
                continue
            with open(path) as f:
                for line in f:
                    if line.startswith("p "):
                        _, _, v, c = line.split()
                        break
            name = os.path.basename(path)[:-5]
            H = 6 if inst.startswith("Intrusion") else 15
            print(f"| {name} | {H} | {int(v):,} | {int(c):,} |")
    print()


def results(recs):
    print("| Instance | Obs. | Method | Status | Time | Recognized (posterior) | True goal: posterior, rank |")
    print("|---|--:|---|---|--:|---|---|")
    for inst in ORDER:
        for k in sorted({k for (i, k, _) in recs if i == inst}):
            for m in METHODS:
                r = recs.get((inst, k, m))
                if r is None:
                    # ddnnf and mc-sat are cross-checks, run where needed
                    if m not in ("ddnnf", "mc-sat"):
                        print(f"| {inst} | {k} | {m} | not run | – | – | – |")
                    continue
                if r["status"] != "ok":
                    limit = f" ({fmt_time(r['limit_s'])} limit)" if r["status"] == "timeout" else ""
                    print(f"| {inst} | {k} | {m} | {r['status']}{limit} | {fmt_time(r['wall_s'])} | – | – |")
                    continue
                post, tg = r["posterior"], r["true_goal"]
                am = r["argmax"]
                top = post[am[0]]
                rec = (f"{am[0]} ({top:.3f})" if len(am) == 1
                       else f"{len(am)}-way tie incl. {', '.join(am[:3])}{'…' if len(am) > 3 else ''} ({top:.3f})")
                rk, tied = rank(post, tg)
                rks = f"{rk}" + (f" (tied ×{tied})" if tied > 1 else "")
                print(f"| {inst} | {k} | {m} | ok | {fmt_time(r['wall_s'])} | {rec} | {post[tg]:.3f}, {rks} |")
    print()


def agreement(recs):
    """Each exact method that finished, against sharpsat-td: the largest
    difference over the hypotheses' posteriors."""
    print("| Instance | Obs. | Methods compared with sharpsat-td | max \\|difference\\| over the posteriors |")
    print("|---|--:|---|--:|")
    for inst in ORDER:
        for k in sorted({k for (i, k, _) in recs if i == inst}):
            b = recs.get((inst, k, "sharpsat-td"))
            others = [m for m in EXACT[1:] if recs.get((inst, k, m), {}).get("status") == "ok"]
            if not (b and b["status"] == "ok" and others):
                print(f"| {inst} | {k} | – | – (no two exact methods finished) |")
                continue
            for m in others:
                a = recs[(inst, k, m)]
                d = max(abs(a["posterior"][h] - b["posterior"][h]) for h in b["posterior"])
                print(f"| {inst} | {k} | {m} | {d:.1e} |")
    print()


def compile_table(recs):
    print("| Instance | Obs. | Compilation | Status | Compile | Circuit (text) | Load (binary) | Query with evidence |")
    print("|---|--:|---|---|--:|--:|--:|--:|")
    for inst in ORDER:
        for k in sorted({k for (i, k, _) in recs if i == inst}):
            for m in ("d4", "d4-project"):
                r = recs.get((inst, k, m))
                if r is None:
                    continue
                label = "full" if m == "d4" else "projected"
                if r["status"] != "ok":
                    print(f"| {inst} | {k} | {label} | {r['status']} | {fmt_time(r.get('compile_s'))} | – | – | – |")
                    continue
                mb = r["circuit_bytes"] / 2**20
                print(f"| {inst} | {k} | {label} | ok | {fmt_time(r['compile_s'])} | {mb:.1f} MB | "
                      f"{fmt_time(r['load_s'])} | {fmt_time(r['query_s'])} |")
    print()


def main():
    recs = load()
    print("### Theory sizes\n")
    sizes()
    print("### Posterior over the goals\n")
    results(recs)
    print("### Agreement of the two exact methods\n")
    agreement(recs)
    print("### d4 compilation\n")
    compile_table(recs)


if __name__ == "__main__":
    main()
