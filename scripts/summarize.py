#!/usr/bin/env python3
"""summarize.py --family F -- markdown tables of F's results/*.jsonl.

Planning: per size, goals planned by tt-open-wbo-inc, EvalMaxSAT runs that
proved an optimum (and that failed or were killed), which plan the evidence came
from, horizons, and how far tt's cost was above the proved optimum.

Recognition: per size, evidence (none / 25% / 100%) and method, runs ok of
those attempted, timeouts/memouts/killed, mean wall time of the ok runs, and
for 25%/100% the accuracy -- the mean of score (1/k when the true hypothesis is
among k tied argmax hypotheses, else 0) -- and the mean posterior of the true
hypothesis.  "chance" is 1/(number of hypotheses).

d4: per size, problems compiled (count verified against SharpSAT-TD /
unverified), timeouts/memouts, mean compile time, nodes and circuit size.

The LAST record of a run counts (a rerun supersedes).
"""
import argparse, collections, statistics as st
import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--family", required=True)
A = ap.parse_args()
FAM = C.Family(A.family)


def last_by(recs, key):
    out = {}
    for r in recs:
        out[key(r)] = r
    return list(out.values())


def mean(xs, fmt="{:.1f}"):
    xs = [x for x in xs if x is not None]
    return fmt.format(st.mean(xs)) if xs else "-"


def table(head, rows):
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()


def planning():
    recs = FAM.load("plans.jsonl")
    if not recs:
        return
    print(f"## {FAM.name}: planning\n")
    tt = last_by([r for r in recs if r["stage"] == "tt"], lambda r: r["name"])
    ev = last_by([r for r in recs if r["stage"] == "eval"], lambda r: r["name"])
    goals = last_by([r for r in recs if r["stage"] == "goal"], lambda r: r["name"])
    probs = last_by([r for r in recs if r["stage"] == "problem"], lambda r: r["name"])
    rows = []
    for s in FAM.sizes:
        n_goals = sum(len(FAM.hypotheses(p)) for p in FAM.problems([s]))
        t = [r for r in tt if r["size"] == s]
        e = [r for r in ev if r["size"] == s]
        g = [r for r in goals if r["size"] == s]
        p = [r for r in probs if r["size"] == s]
        if not (t or e or g):
            rows.append([f"{s}x{s}", n_goals] + ["-"] * 9)
            continue
        t_ok = [r for r in t if r["status"] == "ok"]
        e_ok = [r for r in e if r["status"] == "ok"]
        e_bad = collections.Counter(r["status"] for r in e if r["status"] != "ok")
        gaps = [r["tt_cost"] - r["eval_cost"] for r in g if r.get("eval_cost") is not None]
        rows.append([f"{s}x{s}", n_goals, len(t_ok),
                     len(e_ok), ", ".join(f"{v} {k}" for k, v in sorted(e_bad.items())) or "-",
                     sum(r["plan_from"] == "tt" for r in g),
                     f"{sum(r['status'] == 'ok' for r in p)}/{len(FAM.problems([s]))}",
                     mean([r["horizon"] for r in g]),
                     mean([r["wall_s"] for r in t_ok]), mean([r["wall_s"] for r in e_ok]),
                     f"{sum(x > 0 for x in gaps)}/{len(gaps)}, mean {mean(gaps, '{:.2f}')}" if gaps else "-"])
    table(["size", "goals", "tt plans", "EvalMaxSAT proved", "EvalMaxSAT not",
           "evidence from tt", "problems ready", "mean H", "tt s", "EvalMaxSAT s",
           "tt above optimum (n, mean)"], rows)


def recognition():
    recs = FAM.load("runs.jsonl")
    if not recs:
        return
    print(f"## {FAM.name}: recognition (posterior of the hypotheses)\n")
    runs = last_by(recs, lambda r: (r["evidence"], r["method"]))
    rows = []
    for s in FAM.sizes:
        rs = [r for r in runs if r["size"] == s]
        if not rs:
            continue
        nh = len(FAM.hypotheses(FAM.problems([s])[0]))
        for pct in (0,) + C.EVIDENCE_FRACTIONS:
            for m in C.METHODS:
                x = [r for r in rs if r["evidence_pct"] == pct and r["method"] == m]
                if not x:
                    continue
                ok = [r for r in x if r["status"] == "ok"]
                bad = collections.Counter(r["status"] for r in x if r["status"] != "ok")
                acc = mean([r.get("score") for r in ok], "{:.3f}") if pct else "-"
                ptrue = mean([r["posterior"].get(r["true_goal"]) for r in ok if r.get("true_goal")],
                             "{:.3f}") if pct else "-"
                rows.append([f"{s}x{s}", "none" if pct == 0 else f"{pct}%", m,
                             f"{len(ok)}/{len(x)}", ", ".join(f"{v} {k}" for k, v in sorted(bad.items())) or "-",
                             mean([r["wall_s"] for r in ok]), acc, ptrue, f"{1 / nh:.3f}"])
    table(["size", "evidence", "method", "ok", "not ok", "mean s (ok)", "accuracy",
           "mean P(true)", "chance"], rows)


def d4():
    recs = FAM.load("compile-d4.jsonl")
    if not recs:
        return
    print(f"## {FAM.name}: d4 compilation (2-hour limit)\n")
    rs = last_by(recs, lambda r: r["instance"])
    rows = []
    for s in FAM.sizes:
        x = [r for r in rs if r["size"] == s]
        if not x:
            continue
        ok = [r for r in x if r["status"] == "ok"]
        bad = collections.Counter(r["status"] for r in x if r["status"] != "ok")
        rows.append([f"{s}x{s}", f"{len(ok)}/{len(FAM.problems([s]))}",
                     sum(r.get("count_check") == "agrees" for r in ok),
                     ", ".join(f"{v} {k}" for k, v in sorted(bad.items())) or "-",
                     mean([r["wall_s"] for r in ok]), mean([r.get("d4_s") for r in ok]),
                     mean([r.get("nodes") for r in ok], "{:.0f}"),
                     mean([r.get("circuit_bytes", 0) / 2**20 for r in ok])])
    table(["size", "compiled", "count verified", "not ok", "mean s", "mean d4 s",
           "mean nodes", "mean MB"], rows)


if __name__ == "__main__":
    print(f"# {FAM.name} results\n")
    print(f"Generated by scripts/summarize.py on {C.now()[:10]}.\n")
    planning()
    recognition()
    d4()
