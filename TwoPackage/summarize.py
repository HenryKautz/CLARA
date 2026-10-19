#!/usr/bin/env python3
"""summarize.py -- the TwoPackage results tables, as Markdown, from results/*.jsonl.

Recognition (results/runs.jsonl): the LAST record of each (evidence, method) --
the 20-minute rerun where a run timed out at 5 minutes -- by grid size and
method.  Columns:
  runs      evidence files the method was run on at that size (a method stops
            at the size where it first times out, so later runs were never made)
  ok        runs that finished; timeouts and errors are counted separately
  accuracy  mean of 1/k when the true goal is among the k tied top goals, else 0
            -- the expected accuracy of breaking ties at random.  Records from
            before run-recognize.py wrote `score` are scored from their argmax.
  top-k     the old `correct`: true goal anywhere among the tied top goals
  P(true)   mean posterior probability of the true goal
  time      mean and max wall time of the finished runs
Chance is 1/4: every problem has four hypotheses.

d4 (results/compile-d4.jsonl, query-evidence.jsonl, verify-count.jsonl): the
last compile record of each problem, by size, and how each circuit was checked:
  count   its model count equals sharpSAT's exact count of the theory --
          compile-d4.py's 120 s check, or verify-count.py's longer one
  oracle  evidence-query marginals equal marginals.sh --solver sharpsat-td's
  -       unverified

    python3 summarize.py > tables.md
"""
import collections, json, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")


def records(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def last_by(recs, key):
    out = {}
    for r in recs:
        k = key(r)
        if k not in out or r["started"] >= out[k]["started"]:
            out[k] = r
    return out


def score(r):
    if "score" in r:
        return r["score"]
    return 1 / len(r["argmax"]) if r["true_goal"] in r["argmax"] else 0.0


def recognition_table():
    last = last_by(records("runs.jsonl"), lambda r: (r["evidence"], r["method"]))
    groups = collections.defaultdict(list)
    for r in last.values():
        groups[(r["size"], r["method"])].append(r)
    lines = ["| Grid | Method | Runs | Ok | Timeout | Error | Accuracy | Top-k | P(true) | Mean time | Max time |",
             "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for (size, method) in sorted(groups):
        rs = groups[(size, method)]
        ok = [r for r in rs if r["status"] == "ok"]
        n_to = sum(r["status"] == "timeout" for r in rs)
        n_err = sum(r["status"] == "error" for r in rs)
        if ok:
            acc = "%.3f" % st.mean(score(r) for r in ok)
            topk = "%.3f" % st.mean(r["true_goal"] in r["argmax"] for r in ok)
            p = "%.3f" % st.mean(r["posterior"].get(r["true_goal"], 0.0) for r in ok)
            w = [r["wall_s"] for r in ok]
            mean_t, max_t = "%.0f s" % st.mean(w), "%.0f s" % max(w)
        else:
            acc = topk = p = mean_t = max_t = "–"
        lines.append(f"| {size}×{size} | {method} | {len(rs)} | {len(ok)} | {n_to} | {n_err} | "
                     f"{acc} | {topk} | {p} | {mean_t} | {max_t} |")
    # overall accuracy over every finished run of each method
    lines.append("")
    by_method = collections.defaultdict(list)
    for r in last.values():
        if r["status"] == "ok":
            by_method[r["method"]].append(r)
    lines.append("| Method | Finished runs | Accuracy | Top-k | P(true) | Tied top goal |")
    lines.append("|---|--:|--:|--:|--:|--:|")
    for m in sorted(by_method):
        rs = by_method[m]
        lines.append(f"| {m} | {len(rs)} | {st.mean(score(r) for r in rs):.3f} | "
                     f"{st.mean(r['true_goal'] in r['argmax'] for r in rs):.3f} | "
                     f"{st.mean(r['posterior'].get(r['true_goal'], 0.0) for r in rs):.3f} | "
                     f"{sum(len(r['argmax']) > 1 for r in rs)} |")
    return "\n".join(lines)


def check_of(name, comp, oracle, longcheck):
    if comp.get("count_check") == "agrees":
        return "count"
    if longcheck.get(name, {}).get("count_check") == "agrees":
        return "count (long)"
    if longcheck.get(name, {}).get("count_check") == "differs":
        return "**WRONG**"
    o = oracle.get(name)
    if o and o.get("status") == "ok" and o.get("compared_atoms") and o.get("max_abs_diff") is not None:
        return "oracle"
    return "–"


def compile_table():
    comp = last_by(records("compile-d4.jsonl"), lambda r: r["instance"])
    oracle = last_by(records("query-evidence.jsonl"), lambda r: r["instance"])
    longcheck = last_by(records("verify-count.jsonl"), lambda r: r["instance"])
    lines = ["| Problem | Horizon | CNF vars | Status | Compile time | d4 time | Circuit nodes | Query time | Checked by |",
             "|---|--:|--:|---|--:|--:|--:|--:|---|"]
    for name in sorted(comp, key=lambda n: (int(n[4:].split("x")[0]), n)):
        r = comp[name]
        q = oracle.get(name, {})
        ok = r["status"] == "ok"
        lines.append(f"| {name} | {r.get('horizon', '–')} | {r.get('cnf_vars', '–'):,} | {r['status']} "
                     f"(limit {r['limit_s']:g} s) | {r['wall_s']:.1f} s | "
                     f"{('%.1f s' % r['d4_s']) if ok and 'd4_s' in r else '–'} | "
                     f"{('{:,}'.format(r['nodes'])) if ok and r.get('nodes') else '–'} | "
                     f"{('%.3f s' % q['query_s']) if q.get('query_s') is not None else '–'} | "
                     f"{check_of(name, r, oracle, longcheck) if ok else '–'} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print("## Recognition\n")
    print(recognition_table())
    print("\n## d4 compilation\n")
    print(compile_table())
