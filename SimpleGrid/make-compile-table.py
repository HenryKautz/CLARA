#!/usr/bin/env python3
"""make-compile-table.py -- the d4 compilation table, from results/compile-d4.jsonl
(written by compile-d4.py): results/compile-d4.{md,tex,pdf}, one row per problem."""
import json, os, re, subprocess, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
NAME = "compile-d4"
PDF_WIDTH_IN = 7
# Runs started before this used FiFO's earlier, quadratic circuit evaluator
# (fixed in FiFO fd0d0b9): their sizes, counts and d4 times stand, but their
# total times (which include the unconditioned marginals) are shown as dashes.
CURRENT_SINCE = "2026-10-16T15:20"
SIZE_ORDER = ["3x3", "4x4", "5x5", "6x6", "7x7", "8x8", "9x9", "10x10"]
TITLE = "SimpleGrid problems compiled to d-DNNF with d4 (projected, no evidence)"

# (key, header lines, alignment)
COLS = [("instance", ["Instance"], "l"),
        ("horizon", ["Hori-", "zon"], "r"),
        ("circuit", ["Circuit file"], "l"),
        ("d4_t", ["d4", "time (s)"], "r"),
        ("total_t", ["Total", "time (s)"], "r"),
        ("vars", ["CNF", "variables"], "r"),
        ("clauses", ["CNF", "clauses"], "r"),
        ("proj", ["Projected", "variables"], "r"),
        ("nodes", ["Circuit", "nodes"], "r"),
        ("edges", ["Circuit", "edges"], "r"),
        ("models", ["Model count", "(verified)"], "r"),
        ("query", ["Query with", "2 obs. (s)"], "r"),
        ("tries", ["Tries"], "r")]


def gb(mb):
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:g} MB"


def qtime(s):
    return f"{s:.3f}" if s < 1 else f"{s:.2f}"


def stale(r):
    """A run older than the current FiFO: its total time is not comparable."""
    return r.get("started", "") < CURRENT_SINCE


def span(sizes):
    """'3×3–7×7, 9×9' for a set of grid sizes: runs of consecutive sizes joined."""
    idx = sorted(SIZE_ORDER.index(s) for s in set(sizes))
    parts, i = [], 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
            j += 1
        a, b = SIZE_ORDER[idx[i]], SIZE_ORDER[idx[j]]
        parts.append(a if i == j else f"{a}–{b}")
        i = j + 1
    return ", ".join(parts).replace("x", "×")


def by_value(recs, fn):
    """{value: [sizes]} for FN over RECS, in order of first appearance."""
    out = {}
    for r in recs:
        out.setdefault(fn(r), [])
        if r["size"] not in out[fn(r)]:
            out[fn(r)].append(r["size"])
    return out


def grouped(recs, fn, fmt):
    """FMT(value) for a setting shared by every row, else each value with the
    grid sizes it applies to: '30 minutes (3×3–7×7) or 20 minutes (8×8–10×10)'."""
    g = by_value(recs, fn)
    if len(g) == 1:
        return fmt(next(iter(g)))
    return " or ".join(f"{fmt(v)} ({span(s)})" for v, s in g.items())


def row(r, tries, q):
    ok = r["status"] == "ok"
    limit = f"{r['limit_s'] / 60:g} min"
    fail = {"timeout": f"timeout ({limit})", "memout": "out of memory",
            "wrong": "wrong circuit"}.get(r["status"], "error")
    num = lambda k: f"{r[k]:,}" if k in r else "–"
    d4_done = "nodes" in r      # d4 finished, even if a later step did not
    out = {"instance": r["instance"], "horizon": str(r["horizon"]),
           "circuit": os.path.basename(r["circuit"]) if ok else "none",
           "d4_t": f"{r['d4_s']:.2f}" if d4_done else
                   (f"crashed at {r['d4_s']:.2f}" if r["status"] == "error" and "d4_s" in r
                    else fail),
           "total_t": ("–" if stale(r) else f"{r['wall_s']:.1f}") if ok
                      else (fail if d4_done else "–"),
           "vars": num("cnf_vars"), "clauses": num("cnf_clauses"), "proj": num("projected_vars"),
           "nodes": num("nodes") if d4_done else
                    ("–" if r["status"] == "error"
                     else f"unfinished; d4 at {gb(r['d4_peak_mb'])}"),
           "edges": num("edges") if d4_done else "–",
           # ok rows: the circuit's count, which equals the independent count;
           # wrong rows: the circuit's count against the true one
           "models": (num("circuit_count") if ok else
                      f"{r['circuit_count']:,} ≠ {r['model_count']:,}" if r["status"] == "wrong"
                      else "–"),
           "query": qtime(q["query_s"]) if q and q["status"] == "ok" else "–",
           "tries": str(tries)}
    return out


def query_note(queries):
    """Caption text for the query-with-evidence column (results/query-evidence.jsonl)."""
    if not queries:
        return ""
    qs = list(queries.values())
    reps = sorted({q["repeats"] for q in qs})
    loads = [q["load_s"] for q in qs if "load_s" in q]
    return (" Query with 2 obs. is the time to recompute every marginal of the saved "
            "circuit conditioned on two observations — the first two drives of a "
            "shortest plan to the problem's alphabetically first destination, pinned "
            "to steps 1 and 2 (evidence/PROBLEM-DESTINATION-obs2.txt) — as "
            "marginals.sh --circuit --evidence-file does: the observations are unit "
            "literals over kept atoms, so the circuit is clamped and re-evaluated, "
            "not recompiled. It is timed inside SBCL, the median of "
            f"{' or '.join(map(str, reps))} repetitions, and excludes starting SBCL "
            "and loading FiFO (about 1.2 s) and reading the circuit file "
            f"({min(loads):.3f}–{max(loads):.2f} s). Each answer was checked: both "
            "observed drives have probability 1, and the final-slice goal marginals "
            "sum to 1. FiFO evaluates the circuit in two linear passes; its backward "
            "pass through an AND node of k children uses prefix and suffix products "
            "(an earlier version recomputed each child's k-1 sibling products, "
            "k² multiplications, and took up to 7 s on 7×7 — smoothed AND nodes "
            "here have up to 1,007 children).")


def larger_note(recs, runs):
    """Caption text for the d4 fix, and for rows whose total time is stale."""
    text = ""
    fixed = [r for r in recs if r.get("d4_sha")]
    if fixed:
        text += (" Until d4v2 commit c11210d (2026-10-16), d4 had a heap overflow "
                 "(ListLit::setListLit) that from 8×8 on made it crash, or silently "
                 "return a wrong circuit, at random. The "
                 f"{span(r['size'] for r in fixed)} rows are from the fixed d4; the "
                 f"{span(r['size'] for r in recs if not r.get('d4_sha'))} circuits were "
                 "compiled before the fix, which did not affect them (every one passed "
                 "the count check).")
    old = [r for r in recs if stale(r) and r["status"] == "ok"]
    if old:
        per = "; ".join(f"{r['instance']}: correct on {runs[r['instance']].count('ok')} "
                        f"of {len(runs[r['instance']])}" for r in old)
        text += (f" The {span(r['size'] for r in old)} rows give the run whose circuit "
                 f"passed the model-count check ({per} runs); its d4 time is that run's "
                 "alone, not counting failed runs. Their total time is not shown: it was "
                 "measured with FiFO's earlier, quadratic evaluator (and partly two "
                 "compilations at a time); and no queries were timed on them.")
    return text


def timing_note(recs):
    """Caption text for the awake-time clock of the newer runs."""
    awake = [r for r in recs if r.get("timing") == "awake"]
    if not awake:
        return ""
    slept = [r["instance"] for r in awake if r.get("slept_s", 0) > 0]
    return (f" The {span(r['size'] for r in awake)} runs were timed on the awake clock "
            "(CLOCK_UPTIME_RAW), which stops while the computer sleeps, so a suspend "
            "neither lengthens a time nor times a run out; their records also hold "
            "wall-clock time and CPU time"
            + (f" ({', '.join(slept)}: the computer slept during the run)." if slept
               else ", and the computer did not sleep during any of them."))


def caption(recs, tries, queries, runs, mean_rows=False):
    sizes = []
    for r in recs:
        if r["size"] not in sizes:
            sizes.append(r["size"])
    done = [s for s in sizes if any(r["size"] == s and r["status"] == "ok" for r in recs)]
    if mean_rows:
        # a table of means shows only the problems that compiled: describe those
        recs = [r for r in recs if r["status"] == "ok"]
    limits = grouped(recs, lambda r: r["limit_s"], lambda s: f"{s / 60:g} minutes")
    heaps = grouped(recs, lambda r: r.get("sbcl_heap_mb", 8192),
                    lambda mb: f"{'an' if str(mb / 1024).startswith('8') else 'a'} "
                               f"{mb / 1024:g} GB heap")
    jobs = sorted({r.get("jobs", 4) for r in recs})
    one = lambda r: r.get("jobs", 4) == 1
    if len(jobs) == 1:
        at_once = f"{jobs[0]} compilation{'s' if jobs[0] != 1 else ''} at a time"
    else:
        # name the smaller group: the problems run one at a time, or the others
        ones = [r["instance"] for r in recs if one(r)]
        rest = [r for r in recs if not one(r)]
        if 1 in jobs and len(ones) <= len(rest):
            at_once = (f"{' or '.join(map(str, jobs))} compilations at a time "
                       f"({', '.join(ones)} one at a time: two 8 GB SBCL imports at once "
                       "swap on this 16 GB machine)")
        else:
            at_once = ("1 compilation at a time, except " + ", ".join(
                f"{r['instance']} ({r.get('jobs', 4)} at a time)" for r in rest))
    text = ("Each problem's evidence-free recognition theory — the problem at its "
            "recognition horizon, with the goal literals as the hypotheses, as "
            "recognize.sh builds it — compiled by marginals.sh --solver d4 --project. "
            "The projection keeps the drive actions and the final-slice goal atoms, "
            "and FiFO first verifies that they determine every other atom, so the "
            "projected circuit gives exact counts; any pinned observations are unit "
            "literals over the kept actions, so one saved circuit answers every "
            "evidence file by conditioning, without recompiling. CNF variables and "
            "clauses are those of the ground theory d4 is given; projected variables "
            "are the ones it keeps. d4 time is the d4 run alone; total time is the "
            "whole marginals.sh run (reading the theory, the projection check, d4, "
            "importing and saving the circuit, and the marginals of the unconditioned "
            "circuit). Circuit nodes and edges are those of "
            f"d4's decision-DNNF, before FiFO smooths it. Runs: {at_once}, each "
            f"limited to {limits}. SBCL ran with {heaps} and a 1 GB control stack, "
            "d4 with a 64 MB stack (the defaults, 1 GB, 2 MB and 8 MB, are too small "
            "for the larger circuits).")
    text += timing_note(recs)
    if any(r.get("fifo_lisp", "installed") != "installed" for r in recs):
        text += (" The circuits were imported by FiFO's d4 importer as rewritten to use "
                 "bit-vector scopes and iterative traversal (FiFO fd0d0b9); the earlier "
                 "importer ran out of memory on circuits of about a million nodes.")
        # the records do not name the importer; the packed one (single-pass build,
        # circuit in typed arrays) was first used on 2026-10-18
        packed = [r["instance"] for r in recs if r.get("started", "") >= "2026-10-18"]
        if packed:
            text += (f" {', '.join(packed)} {'was' if len(packed) == 1 else 'were'} "
                     "imported by its successor, which builds the circuit in one pass "
                     "into packed typed arrays; with fd0d0b9, SBCL's garbage collector "
                     "crashed while importing "
                     f"{'it' if len(packed) == 1 else 'them'}, after d4 had finished.")
    text += (" Model count (verified) is the number of models of the compiled circuit "
             "(all literals set to 1 in the smoothed circuit), that is, the number of "
             "truck walks the theory allows. Every circuit kept was checked against an "
             "independent count of those walks by dynamic programming over the grid "
             "(H-1 steps, each a drive to a neighbouring cell or a wait, from p1-1 to a "
             "goal cell), which agrees with sharpSAT on every problem up to 7×7 "
             "(sharpSAT did not finish an 8×8 problem in 2.5 hours); the two counts were "
             "equal for every circuit in the table.")
    text += larger_note(recs, runs)
    if any(t > 1 for t in tries.values()) and not mean_rows:
        text += (" Tries counts the runs of d4 on a problem, failed ones included — a "
                 "run whose saved circuit a later check found wrong counts as failed.")
    text += query_note(queries)
    capped = [r for r in recs if r.get("node_limit")]
    if capped:
        text += (" FiFO's circuit-size cap (*ddnnf-node-limit*, 2,000,000 nodes by "
                 "default) was raised to " + grouped(
                     capped, lambda r: r["node_limit"], lambda n: f"{n:,}")
                 + (f" for {span(r['size'] for r in capped)}" if
                    len(by_value(capped, lambda r: r["node_limit"])) == 1 else "")
                 + ", since a smoothed import of a large d4 circuit exceeds the default.")
    groups = {}
    for r in recs:
        if r.get("d4_options"):
            groups.setdefault(r["d4_options"], []).append(r["instance"])
    if groups:
        text += " In the run reported, d4 was given extra options: " + "; ".join(
            f"\"{opts}\" for {', '.join(names)}" for opts, names in groups.items()) + (
            " (every other problem: d4's defaults). Storing every clause in a cache "
            "entry, and cache pages smaller than the default 4 GB, made d4 miscompile "
            "less often, though not never.")
    if any(r["status"] == "wrong" for r in recs):
        text += (" \"wrong circuit\": no run passed the check; the counts shown are "
                 "the last circuit's and the true one.")
    if any(r["status"] == "error" for r in recs):
        text += (" \"crashed at\": no run finished — d4 crashed every time; the time is "
                 "when it crashed in the last run.")
        if any(r["status"] == "error" and "nodes" in r for r in recs):
            text += " Where d4 had finished but a later step failed, its circuit size is given."
    if any(r["status"] in ("timeout", "memout") and "nodes" not in r for r in recs):
        text += (" d4 holds its circuit in memory and writes it only when it finishes, "
                 "so an unfinished circuit cannot be counted; its size is given as "
                 "d4's peak memory (sampled every 2 s) before it was stopped.")
    if any(r["status"] == "timeout" and "nodes" in r for r in recs):
        text += (" A timeout with circuit sizes: d4 finished, but importing and saving "
                 "its circuit did not within the limit.")
    if sizes and sizes[-1] not in done:
        text += (f" No {sizes[-1].replace('x', '×')} problem compiled within the limit, "
                 "so larger grids were not tried.")
    return text


def tex_escape(s):
    return (s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
            .replace("×", r"$\times$").replace("≠", r"$\neq$")
            .replace("–", "--").replace("—", "---"))


def markdown(cols, title, rows, note):
    head = "| " + " | ".join(" ".join(h).replace("- ", "") for _, h, _ in cols) + " |"
    align = "|" + "|".join(":--" if a == "l" else "--:" for _, _, a in cols) + "|"
    body = ["| " + " | ".join(r[k] for k, _, _ in cols) + " |" for r in rows]
    return "\n".join([f"## {title}", "", head, align, *body, "", textwrap.fill(note, 80), ""])


def latex(cols, title, rows, note):
    spec = "".join(a for _, _, a in cols)
    head = " & ".join(r"\makecell[%sb]{%s}" % (a, r"\\".join(map(tex_escape, h)))
                      for _, h, a in cols)
    body = "\n".join(" & ".join(tex_escape(r[k]) for k, _, _ in cols) + r" \\" for r in rows)
    note_tex = re.sub(r'"([^"]*)"', r"``\1''", tex_escape(note))
    # command-line options: keep "--" from becoming an en dash
    note_tex = re.sub(r"(?<!-)--([a-z][a-z-]*)", r"\\texttt{-{}-\1}", note_tex)
    margin = (8.5 - PDF_WIDTH_IN) / 2
    return "\n".join([
        r"\documentclass[10pt]{article}",
        r"\usepackage[letterpaper,hmargin=%gin,vmargin=0.75in]{geometry}" % margin,
        r"\usepackage{booktabs,makecell,adjustbox}",
        r"\usepackage[T1]{fontenc}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        r"\section*{%s}" % tex_escape(title),
        r"\newsavebox{\tbl}",
        r"\begin{lrbox}{\tbl}\small\setlength{\tabcolsep}{4pt}\begin{tabular}{%s}" % spec,
        r"\toprule", head + r" \\", r"\midrule", body, r"\bottomrule",
        r"\end{tabular}\end{lrbox}",
        r"\typeout{TABLEWIDTH \the\wd\tbl\space TEXTWIDTH \the\textwidth}",
        r"\noindent\adjustbox{max width=\textwidth}{\usebox{\tbl}}",
        r"\par\bigskip\noindent",
        # a plain paragraph, not a minipage: a long caption may need to break
        # across pages, and a minipage that does not fit moves whole to the next
        r"{\small " + note_tex + r"\par}",
        r"\end{document}", ""])


def main():
    lines = [json.loads(l) for l in open(os.path.join(RES, NAME + ".jsonl")) if l.strip()]
    # A "checked_later" record is a later check of a saved circuit, not a run:
    # its verdict (and counts) replace those of the run it checked, matched by
    # start time -- e.g. a run recorded "ok" whose circuit was later found wrong.
    checks = {(h["instance"], h["started"]): h for h in lines if "checked_later" in h}
    history = []
    for h in lines:
        if "checked_later" in h:
            continue
        c = checks.get((h["instance"], h["started"]))
        if c:
            h = dict(h, status=c["status"],
                     **{k: c[k] for k in ("circuit_count", "model_count") if k in c})
        history.append(h)
    recs = {}
    for h in history:
        recs[h["instance"]] = h              # the latest run of each problem
    recs = sorted(recs.values(),
                  key=lambda r: (int(r["size"].split("x")[0]), int(r["instance"].split("-")[1])))
    lisp = lambda r: r.get("fifo_lisp", "installed")
    # runs: every run of a problem with the reported run's FiFO and d4 binary, in
    # order (runs of the buggy d4 are not tries of the fixed one)
    runs = {r["instance"]: [h["status"] for h in history
                            if h["instance"] == r["instance"] and lisp(h) == lisp(r)
                            and h.get("d4_sha") == r.get("d4_sha")]
            for r in recs}
    # Tries: the runs that led to the reported one -- it and the failed runs
    # just before it, back to the previous run that passed (an earlier passing
    # run, e.g. one redone to re-time it, starts a new count).
    def count_tries(r):
        n = 0
        for s in reversed(runs[r["instance"]]):
            if n and s == "ok":
                break
            n += 1
        return n
    tries = {r["instance"]: count_tries(r) for r in recs}
    queries = {}
    qfile = os.path.join(RES, "query-evidence.jsonl")
    if os.path.exists(qfile):
        for line in open(qfile):
            if line.strip():
                q = json.loads(line)
                queries[q["instance"]] = q   # the latest query run of each problem
    queries = {k: v for k, v in queries.items() if any(r["instance"] == k for r in recs)}
    rows = [row(r, tries[r["instance"]], queries.get(r["instance"])) for r in recs]
    note = caption(recs, tries, queries, runs)
    cols = COLS
    if all(t == 1 for t in tries.values()):
        cols = [c for c in cols if c[0] != "tries"]
    if not queries:
        cols = [c for c in cols if c[0] != "query"]
    write(NAME, cols, TITLE, rows, note)
    srows = (summary_rows([r for r in recs if not stale(r)], queries)
             + summary_rows([r for r in recs if stale(r)], {}, old=True))
    snote = caption(recs, tries, queries, runs, mean_rows=True)
    write(NAME + "-summary", [c for c in SUMMARY_COLS if c[0] != "query" or queries],
          TITLE + ": means by grid size", srows, summary_note(recs) + " " + snote)


SUMMARY_COLS = [("size", ["Grid"], "l"),
                ("n", ["Prob-", "lems"], "r"),
                ("horizon", ["Hori-", "zon"], "r"),
                ("d4_t", ["d4", "time (s)"], "r"),
                ("total_t", ["Total", "time (s)"], "r"),
                ("vars", ["CNF", "variables"], "r"),
                ("clauses", ["CNF", "clauses"], "r"),
                ("proj", ["Projected", "variables"], "r"),
                ("nodes", ["Circuit", "nodes"], "r"),
                ("edges", ["Circuit", "edges"], "r"),
                ("models", ["Model", "count"], "r"),
                ("query", ["Query with", "2 obs. (s)"], "r")]


def summary_rows(recs, queries, old=False):
    """One row per grid size: the mean of each column over its compiled problems.
    OLD: total time and query time are not comparable, so shown as dashes."""
    out = []
    for size in dict.fromkeys(r["size"] for r in recs):
        ok = [r for r in recs if r["size"] == size and r["status"] == "ok"]
        if not ok:
            continue
        mean = lambda xs: sum(xs) / len(xs)
        m = lambda k: mean([r[k] for r in ok])
        num = lambda k: f"{round(m(k)):,}"
        qs = [queries[r["instance"]]["query_s"] for r in ok
              if queries.get(r["instance"], {}).get("status") == "ok"]
        out.append({"size": size.replace("x", "×"), "n": str(len(ok)),
                    "horizon": f"{round(m('horizon'), 2):g}",
                    "d4_t": f"{m('d4_s'):.2f}",
                    "total_t": "–" if old else f"{m('wall_s'):.1f}",
                    "vars": num("cnf_vars"), "clauses": num("cnf_clauses"),
                    "proj": num("projected_vars"), "nodes": num("nodes"), "edges": num("edges"),
                    "models": num("circuit_count"),
                    "query": qtime(mean(qs)) if len(qs) == len(ok) else "–"})
    return out


def summary_note(recs):
    return ("Each row is the arithmetic mean over that grid size's problems (Problems "
            "gives how many), rounded; the per-problem values are in compile-d4.md.")


def write(name, cols, title, rows, note):
    base = os.path.join(RES, name)
    open(base + ".md", "w").write(markdown(cols, title, rows, note))
    open(base + ".tex", "w").write(latex(cols, title, rows, note))
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", name + ".tex"],
                   cwd=RES, check=True, stdout=subprocess.DEVNULL)
    m = re.search(r"TABLEWIDTH ([\d.]+)pt TEXTWIDTH ([\d.]+)pt", open(base + ".log").read())
    tw, xw = float(m.group(1)), float(m.group(2))
    for ext in ("aux", "log"):
        os.remove(base + "." + ext)
    print(f"wrote {base}.{{md,tex,pdf}}  table {tw / 72.27:.2f} in"
          + (f" -> scaled to {xw / 72.27:.2f} in" if tw > xw else ""))


if __name__ == "__main__":
    main()
