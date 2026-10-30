#!/usr/bin/env python3
"""summarize.py [BENCH...] -- Markdown tables from results/<bench>.jsonl.

For each benchmark, grid size and slack, over the problems where all three runs
finished:
  problems      problems compared
  SAT = opt     the SAT plan was already optimal
  steps = opt, actions = opt   the restricted optimum equals the true one
  excess        mean (cost - optimum) / optimum, in percent, for the SAT plan
                and the two restrictions
  time          mean wall time of the full and restricted runs (each a whole
                planner.sh run: translation, instantiation, kissat, MaxSAT)
  full proven   problems whose full run proved its optimum; the others hit the
                MaxSAT limit and reported their best plan
  beats full    problems where a restricted plan is CHEAPER than the full run's
                (possible only when the full run was stopped early)
"full" is EvalMaxSAT on the whole theory.  The optimum is the cheapest of the
three runs, so it is the true optimum where the full run proved its plan and
the best plan known otherwise.  A problem whose full run found no plan at all
(timeout or failure) is counted under "unfinished".
"""
import collections, json, os, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(bench):
    path = os.path.join(HERE, "results", bench + ".jsonl")
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def pct(xs):
    return f"{100 * st.mean(xs):.1f}%" if xs else "–"


def table(bench):
    recs = load(bench)
    by = collections.defaultdict(dict)
    for r in recs:
        by[(r["name"], r["slack"])][r["method"]] = r
    groups = collections.defaultdict(list)
    unfinished = collections.Counter()
    for (name, slack), ms in by.items():
        if all(m in ms and ms[m]["status"] == "ok" for m in ("full", "steps", "actions")):
            groups[(ms["full"]["size"], slack)].append(ms)
        else:
            unfinished[(next(iter(ms.values()))["size"], slack)] += 1
    lines = [f"### {bench}", "",
             "| Grid | Slack | Problems | Full proven | SAT = opt | steps = opt | actions = opt | "
             "Beats full | SAT excess | steps excess | actions excess | Full time | steps time | "
             "actions time | Unfinished |",
             "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for key in sorted(set(groups) | set(unfinished)):
        size, slack = key
        gs = groups.get(key, [])
        rows = []
        for ms in gs:
            opt = min(ms["full"]["cost"], ms["steps"]["cost"], ms["actions"]["cost"])
            rows.append((opt, ms["steps"]["sat_cost"], ms["steps"]["cost"], ms["actions"]["cost"], ms))
        ex = lambda i: [(r[i] - r[0]) / r[0] if r[0] else 0.0 for r in rows]
        eq = lambda i: sum(abs(r[i] - r[0]) < 1e-9 for r in rows)
        t = lambda m: f"{st.mean(ms[m]['wall_s'] for ms in gs):.1f} s" if gs else "–"
        proven = sum(not ms["full"].get("stopped_early") for ms in gs)
        beats = sum(min(ms["steps"]["cost"], ms["actions"]["cost"]) < ms["full"]["cost"] - 1e-9 for ms in gs)
        lines.append(f"| {size}×{size} | {slack} | {len(gs)} | {proven} | {eq(1)} | {eq(2)} | {eq(3)} | "
                     f"{beats} | {pct(ex(1))} | {pct(ex(2))} | {pct(ex(3))} | {t('full')} | {t('steps')} | "
                     f"{t('actions')} | {unfinished.get(key, 0)} |")
    return "\n".join(lines)


if __name__ == "__main__":
    benches = sys.argv[1:] or ["SimpleGrid", "TwoPackage", "ThreePackage"]
    print("\n\n".join(table(b) for b in benches if load(b)))
