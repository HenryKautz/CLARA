#!/usr/bin/env python3
"""summarize.py -- the FourPackage tables, from results/*.jsonl, as Markdown on stdout.

  1. Per problem: the specification (grid, roads kept, the shortest horizon of the
     general problem and the recognition horizon), the size in each format (PDDL;
     the recognition theory as FiFO source, instantiated scnf, and weighted CNF;
     the general problem's weighted CNF), the time to plan the general problem
     (run-plans.py --stage general), and Ramirez & Geffner recognition over the
     problem's evidence files (run-recognize.py, max-term): runs finished out of
     attempted, mean and max time, accuracy.
  2. Per grid size: the same, aggregated, with the clamped-goal plans
     (run-plans.py --stage goals): how many were planned, how many of those the
     solver proved optimal, and their mean time.
  3. SatPlan's interfering-action mutexes, original vs FiFO's MUTEX written
     pairwise vs linear (compare-encodings.py): per general problem, the weighted
     CNF planned and the time and peak memory to plan it at the same horizon with
     the same exact solver, and whether every encoding found the same optimum.

Accuracy counts ties fractionally: a run scores 1/k when the true goal is among
the k top-scoring goals, else 0.  Chance is 1/12.
"""
import collections, json, os, re, statistics
import fpcommon as F

R = os.path.join(F.HERE, "results")


def load(name):
    p = os.path.join(R, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def last(recs, key):
    """The last record per key (a rerun supersedes), except that a run that never
    planned (too-big, timeout, failed) does not displace an ok one: the stopped
    pairwise sweep wrote a too-big for a 12x12 goal after MUTEX had planned it."""
    out = {}
    for r in recs:
        k = key(r)
        if r.get("status") != "ok" and out.get(k, {}).get("status") == "ok":
            continue
        out[k] = r
    return out


def kb(b):
    return "–" if b is None else f"{b / 1024:,.0f} KB" if b < 2**20 else f"{b / 2**20:,.1f} MB"


def num(x):
    return "–" if x is None else f"{x:,}"


def secs(x):
    return "–" if x is None else f"{x:,.1f} s"


def roads(name):
    return len(re.findall(r"\(road ", open(os.path.join(F.HERE, name + ".pddl")).read())) // 2


def main():
    general = last([r for r in load("plans.jsonl") if r["stage"] == "general"], lambda r: r["name"])
    goals = last([r for r in load("plans.jsonl") if r["stage"] == "goals"], lambda r: r["name"])
    formats = last(load("formats.jsonl"), lambda r: r["name"])
    runs = last(load("runs.jsonl"), lambda r: (r["evidence"], r["method"]))
    rec = collections.defaultdict(list)
    for r in runs.values():
        rec[r["problem"][:-5]].append(r)

    print("| Problem | Roads | H general | H recog. | PDDL | wff | scnf | WCNF (recog.) | vars | clauses "
          "| WCNF (general) | Plan time | Plan cost | Goals planned | R&G runs ok | R&G mean | R&G max | Accuracy |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    by_size = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in F.problems():
        n = F.size_of(p)
        src = os.path.join(F.HERE, p + ".pddl")
        hs = F.horizons(src)
        g, f = general.get(p, {}), formats.get(p, {})
        gp = [r for r in goals.values() if r["problem"] == p]
        ok = [r for r in rec.get(p, []) if r["status"] == "ok"]
        times = [r["wall_s"] for r in ok]
        acc = statistics.mean(r["score"] for r in ok) if ok else None
        plan_t = g.get("wall_s") if g.get("status") == "ok" else None
        plan_cell = secs(plan_t) if plan_t is not None else (g.get("status", "–") +
                    (f" ({g['limit_s']} s)" if g.get("status") == "timeout" else ""))
        print(f"| {p} | {roads(p)} | {min(hs.values())} | {F.recognition_horizon(src)} "
              f"| {kb(os.path.getsize(src))} | {kb(f.get('wff_bytes'))} | {kb(f.get('scnf_bytes'))} "
              f"| {kb(f.get('wcnf2024_bytes'))} | {num(f.get('wcnf_vars'))} | {num(f.get('wcnf_clauses'))} "
              f"| {kb(g.get('wcnf_bytes'))} | {plan_cell} | {g.get('cost', '–')} "
              f"| {sum(r['status'] == 'ok' for r in gp)}/{len(hs)} "
              f"| {len(ok)}/{len(rec.get(p, []))} | {secs(statistics.mean(times)) if times else '–'} "
              f"| {secs(max(times)) if times else '–'} | {'–' if acc is None else f'{acc:.3f}'} |")
        s = by_size[n]
        if plan_t is not None:
            s["plan"].append(plan_t)
        s["plan_n"].append(g.get("status") == "ok")
        if f.get("status") == "ok":
            s["clauses"].append(f["wcnf_clauses"])
        s["rg"] += times
        s["rg_n"] += [r["status"] for r in rec.get(p, [])]
        s["score"] += [r["score"] for r in ok]
        s["goals_n"] += [r["status"] for r in gp]
        s["goals_t"] += [r["wall_s"] for r in gp if r["status"] == "ok"]
        s["goals_opt"] += [r for r in gp if r["status"] == "ok" and r.get("proved_optimal",
                                                                        r["solver"] in EXACT)]

    print()
    print("| Grid | General plans | Mean plan time | Max plan time | Recog. theory clauses (mean) "
          "| Goals planned | proved optimal | too big | Mean goal time "
          "| R&G runs | ok | timeout | error | Mean R&G time | Max R&G time | Accuracy |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for n in sorted(by_size):
        s = by_size[n]
        c = collections.Counter(s["rg_n"])
        gc = collections.Counter(s["goals_n"])
        acc = f"{statistics.mean(s['score']):.3f}" if s["score"] else "–"
        print(f"| {n}×{n} | {sum(s['plan_n'])}/{len(s['plan_n'])} "
              f"| {secs(statistics.mean(s['plan'])) if s['plan'] else '–'} "
              f"| {secs(max(s['plan'])) if s['plan'] else '–'} "
              f"| {num(round(statistics.mean(s['clauses']))) if s['clauses'] else '–'} "
              f"| {gc['ok']}/{4 * 12} | {len(s['goals_opt'])} | {gc['too-big']} "
              f"| {secs(statistics.mean(s['goals_t'])) if s['goals_t'] else '–'} "
              f"| {len(s['rg_n'])} | {c['ok']} | {c['timeout']} | {c['error']} "
              f"| {secs(statistics.mean(s['rg'])) if s['rg'] else '–'} "
              f"| {secs(max(s['rg'])) if s['rg'] else '–'} | {acc} |")

    enc = last(load("encodings.jsonl"), lambda r: (r["encoding"], r["name"]))
    if enc:
        encoding_table(enc)


EXACT = {"wmaxcdcl", "EvalMaxSAT_bin", "rc2"}
ENCODINGS = ("original", "pairwise", "linear")


def mb(x):
    return "–" if x is None else f"{x:,} MB"


def encoding_table(enc):
    print()
    print("| Problem | H | Clauses: original | pairwise | linear | linear/original "
          "| Vars: original | linear | Time: original | pairwise | linear "
          "| Peak memory: original | linear | Same optimum |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|")
    for p in F.problems():
        rs = {e: enc.get((e, p)) for e in ENCODINGS}
        if not any(rs.values()):
            continue
        g = lambda e, k: (rs[e] or {}).get(k)
        cell_t = lambda e: secs(g(e, "wall_s")) if g(e, "status") == "ok" else (g(e, "status") or "–")
        ratio = (f"{g('linear', 'wcnf_clauses') / g('original', 'wcnf_clauses'):.2f}"
                 if g("linear", "wcnf_clauses") and g("original", "wcnf_clauses") else "–")
        costs = {g(e, "cost") for e in ENCODINGS if g(e, "status") == "ok"}
        statuses = [g(e, "status") for e in ENCODINGS if rs[e]]
        same = ("yes" if len(costs) == 1 and all(s == "ok" for s in statuses)
                else "MISMATCH" if "cost-mismatch" in statuses or len(costs) > 1 else "–")
        H = next(r["horizon"] for r in rs.values() if r)
        print(f"| {p} | {H} | {num(g('original', 'wcnf_clauses'))} | {num(g('pairwise', 'wcnf_clauses'))} "
              f"| {num(g('linear', 'wcnf_clauses'))} | {ratio} "
              f"| {num(g('original', 'wcnf_vars'))} | {num(g('linear', 'wcnf_vars'))} "
              f"| {cell_t('original')} | {cell_t('pairwise')} | {cell_t('linear')} "
              f"| {mb(g('original', 'peak_rss_mb'))} | {mb(g('linear', 'peak_rss_mb'))} | {same} |")


if __name__ == "__main__":
    main()
