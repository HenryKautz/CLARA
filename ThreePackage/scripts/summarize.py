#!/usr/bin/env python3
"""summarize.py -- the ThreePackage results tables, as Markdown, from results/*.jsonl.

Problems (results/plans.jsonl): per problem, the roads kept, the shortest
horizons of its 8 goal combinations (min and max -- the max is the recognition
horizon), their optimal costs, plan times, and the evidence files written.

Recognition (results/runs.jsonl): the last record of each (evidence, method), by
grid size, number of observed actions and method.  Columns:
  runs      evidence files the method was started on at that size and K
  ok, timeout, killed, error   how they ended; "killed" = still running when
            another run of the same method at that size timed out
  accuracy  mean of 1/k when the true goal is among the k tied top goals, else 0
            -- the expected accuracy of breaking ties at random
  top-k     the true goal anywhere among the tied top goals
  P(true)   mean posterior of the true goal
  time      mean and max wall time of the finished runs
Chance is 1/8: every problem has eight hypotheses.  Evidence files a method was
never started on (it had stopped at a smaller size) are listed as "not run".

d4 (results/compile-d4.jsonl, verify-count.jsonl): the last compile record of
each problem, and how its circuit was checked ("count": its model count equals
sharpSAT's exact count of d4's input CNF, or verify-count.py's longer count of
the theory).

    python3 scripts/summarize.py > tables.md
"""
import collections, glob, json, os, re, statistics as st
import tpcommon as T


def last_by(recs, key):
    out = {}
    for r in recs:
        k = key(r)
        if k not in out or r["started"] >= out[k]["started"]:
            out[k] = r
    return out


def fmt_s(x):
    return f"{x:,.1f} s" if x < 100 else f"{x:,.0f} s"


def problem_table():
    recs = T.load("plans.jsonl")
    goals = last_by([r for r in recs if r["stage"] == "goal"], lambda r: r["name"])
    probs = last_by([r for r in recs if r["stage"] == "problem"], lambda r: r["name"])
    lines = ["| Problem | Roads | Goals planned | Shortest horizon (min–max) | Recognition horizon | "
             "Optimal cost (min–max) | Actions (min–max) | Plan time (mean / max) | Evidence files (obs) |",
             "|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for p in T.problems():
        roads = len(re.findall(r"\(road ", open(os.path.join(T.HERE, p + ".pddl")).read())) // 2
        gs = [g for g in goals.values() if g["problem"] == p]
        ok = [g for g in gs if g["status"] == "ok"]
        n_ev = len(glob.glob(os.path.join(T.HERE, "evidence", p + "-*-obs*.txt")))
        if ok:
            hs = [g["horizon"] for g in ok]
            cs = [g["cost"] for g in ok]
            acts = [g["actions"] for g in ok]
            ws = [g["wall_s"] for g in ok]
            unproved = sum(not g.get("proved_optimal", True) for g in ok)
            cost = f"{min(cs):g}–{max(cs):g}" + (f" ({unproved} unproved)" if unproved else "")
            row = (f"{min(hs)}–{max(hs)} | {probs.get(p, {}).get('recognition_horizon', '–')} | {cost} | "
                   f"{min(acts)}–{max(acts)} | {fmt_s(st.mean(ws))} / {fmt_s(max(ws))}")
        else:
            row = "– | – | – | – | –"
        lines.append(f"| {p} | {roads} | {len(ok)}/8 | {row} | {n_ev} |")
    return "\n".join(lines)


def recognition_table():
    last = last_by(T.load("runs.jsonl"), lambda r: (r["evidence"], r["method"]))
    methods = sorted({r["method"] for r in last.values()})
    n_files = collections.Counter()
    for ev in glob.glob(os.path.join(T.HERE, "evidence", "*-obs*.txt")):
        m = re.match(r"grid(\d+)x.*-obs(\d+)\.txt$", os.path.basename(ev))
        n_files[(int(m.group(1)), int(m.group(2)))] += 1
    groups = collections.defaultdict(list)
    for r in last.values():
        groups[(r["size"], r["n_obs"], r["method"])].append(r)
    lines = ["| Grid | Observed actions | Method | Evidence files | Runs | Ok | Timeout | Killed | Error | "
             "Accuracy | Top-k | P(true) | Mean time | Max time |",
             "|---|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for size, k in sorted(n_files):
        for m in methods:
            rs = groups.get((size, k, m), [])
            ok = [r for r in rs if r["status"] == "ok"]
            cnt = collections.Counter(r["status"] for r in rs)
            if ok:
                acc = "%.3f" % st.mean(r["score"] for r in ok)
                topk = "%.3f" % st.mean(r["correct"] for r in ok)
                p = "%.3f" % st.mean(r["posterior"].get(r["true_goal"], 0.0) for r in ok)
                w = [r["wall_s"] for r in ok]
                mean_t, max_t = fmt_s(st.mean(w)), fmt_s(max(w))
            else:
                acc = topk = p = mean_t = max_t = "–"
            runs = len(rs) if rs else "not run"
            lines.append(f"| {size}×{size} | {k} | {m} | {n_files[(size, k)]} | {runs} | {len(ok)} | "
                         f"{cnt['timeout']} | {cnt['killed']} | {cnt['error']} | {acc} | {topk} | {p} | "
                         f"{mean_t} | {max_t} |")
    lines += ["", "| Method | Finished runs | Accuracy | Top-k | P(true) | Tied top goal |",
              "|---|--:|--:|--:|--:|--:|"]
    for m in methods:
        rs = [r for r in last.values() if r["method"] == m and r["status"] == "ok"]
        if rs:
            lines.append(f"| {m} | {len(rs)} | {st.mean(r['score'] for r in rs):.3f} | "
                         f"{st.mean(r['correct'] for r in rs):.3f} | "
                         f"{st.mean(r['posterior'].get(r['true_goal'], 0.0) for r in rs):.3f} | "
                         f"{sum(r['tie_size'] > 1 for r in rs)} |")
        else:
            lines.append(f"| {m} | 0 | – | – | – | – |")
    return "\n".join(lines)


def compile_table():
    comp = last_by(T.load("compile-d4.jsonl"), lambda r: r["instance"])
    longcheck = last_by(T.load("verify-count.jsonl"), lambda r: r["instance"])
    lines = ["| Problem | Horizon | CNF vars | CNF clauses | Status | Compile time | d4 time | "
             "Circuit nodes | d4 peak memory | Checked by |",
             "|---|--:|--:|--:|---|--:|--:|--:|--:|---|"]
    for name in T.problems():
        r = comp.get(name)
        if not r:
            lines.append(f"| {name} | – | – | – | not run | – | – | – | – | – |")
            continue
        ok = r["status"] == "ok"
        check = {"agrees": "count", "timeout": "unverified (count timed out)"}.get(r.get("count_check"), "–")
        lc = longcheck.get(name, {})
        if lc.get("count_check") == "agrees":
            check = f"count (verify-count.py, {lc['count_s']:,.0f} s)"
        elif lc.get("count_check") == "differs":
            check = "**WRONG**"
        elif lc.get("count_check") == "timeout":
            check = f"unverified (count timed out at {lc['limit_s']:,.0f} s)"
        cv = r.get("cnf_vars")
        cc = r.get("cnf_clauses")
        lines.append(f"| {name} | {r.get('horizon', '–')} | {f'{cv:,}' if cv else '–'} | "
                     f"{f'{cc:,}' if cc else '–'} | {r['status']} (limit {r['limit_s']:g} s) | "
                     f"{fmt_s(r['wall_s'])} | {fmt_s(r['d4_s']) if ok and 'd4_s' in r else '–'} | "
                     f"{'{:,}'.format(r['nodes']) if ok and r.get('nodes') else '–'} | "
                     f"{r.get('d4_peak_mb', 0):,} MB | {check if ok else '–'} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print("## Problems\n")
    print(problem_table())
    print("\n## Recognition\n")
    print(recognition_table())
    print("\n## d4 compilation\n")
    print(compile_table())
