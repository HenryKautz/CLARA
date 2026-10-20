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
METHODS = ["max-term", "sharpsat-td", "d4"]


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
    print("| Instance | Obs. | max \\|d4 − sharpsat-td\\| over the posteriors |")
    print("|---|--:|--:|")
    for inst in ORDER:
        for k in sorted({k for (i, k, _) in recs if i == inst}):
            a, b = recs.get((inst, k, "d4")), recs.get((inst, k, "sharpsat-td"))
            if a and b and a["status"] == b["status"] == "ok":
                d = max(abs(a["posterior"][h] - b["posterior"][h]) for h in a["posterior"])
                print(f"| {inst} | {k} | {d:.1e} |")
            else:
                print(f"| {inst} | {k} | – (not both finished) |")
    print()


def compile_table(recs):
    print("| Instance | Obs. | Status | Compile | Circuit (text) | Load (binary) | Query with evidence |")
    print("|---|--:|---|--:|--:|--:|--:|")
    for inst in ORDER:
        for k in sorted({k for (i, k, _) in recs if i == inst}):
            r = recs.get((inst, k, "d4"))
            if r is None:
                continue
            if r["status"] != "ok":
                print(f"| {inst} | {k} | {r['status']} | {fmt_time(r.get('compile_s'))} | – | – | – |")
                continue
            mb = r["circuit_bytes"] / 2**20
            print(f"| {inst} | {k} | ok | {fmt_time(r['compile_s'])} | {mb:.1f} MB | "
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
