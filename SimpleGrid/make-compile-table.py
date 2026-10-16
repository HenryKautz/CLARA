#!/usr/bin/env python3
"""make-compile-table.py -- the d4 compilation table, from results/compile-d4.jsonl
(written by compile-d4.py): results/compile-d4.{md,tex,pdf}, one row per problem."""
import json, os, re, subprocess, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
NAME = "compile-d4"
PDF_WIDTH_IN = 7
# Largest grid reported: from 8x8 on d4 crashes or returns wrong circuits, so
# those runs stay in the jsonl but are left out of the table.
MAX_SIZE = 7
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


def row(r, tries, q):
    ok = r["status"] == "ok"
    limit = f"{r['limit_s'] / 60:g} min"
    fail = {"timeout": f"timeout ({limit})", "memout": "out of memory",
            "wrong": "wrong circuit"}.get(r["status"], "error")
    num = lambda k: f"{r[k]:,}" if k in r else "–"
    d4_done = "nodes" in r      # d4 finished, even if a later step did not
    out = {"instance": r["instance"], "horizon": str(r["horizon"]),
           "circuit": os.path.basename(r["circuit"]) if ok else "none",
           "d4_t": f"{r['d4_s']:.2f}" if d4_done else fail,
           "total_t": f"{r['wall_s']:.1f}" if ok else (fail if d4_done else "–"),
           "vars": num("cnf_vars"), "clauses": num("cnf_clauses"), "proj": num("projected_vars"),
           "nodes": num("nodes") if d4_done else
                    (f"d4 crashed after {r['d4_s']:g} s" if r["status"] == "error" and "d4_s" in r
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
            "sum to 1. Most of the query time is FiFO's backward pass, which for an "
            "AND node with k children recomputes the k-1 sibling products for each "
            "child (k² multiplications; the largest smoothed AND node of 7×7-4 has "
            "1,007 children), not the circuit size itself.")


def caption(recs, tries, queries):
    sizes = []
    for r in recs:
        if r["size"] not in sizes:
            sizes.append(r["size"])
    done = [s for s in sizes if any(r["size"] == s and r["status"] == "ok" for r in recs)]
    limit = recs[0]["limit_s"] / 60
    big = [r for r in recs if r.get("sbcl_heap_mb", 8192) != 8192]
    heaps = "an 8 GB heap" + (
        "".join(f" ({r['instance']}: {r['sbcl_heap_mb'] / 1024:g} GB: with 8 GB, SBCL's "
                "garbage collector failed while importing its circuit)" for r in big))
    jobs = sorted({r.get("jobs", 4) for r in recs})
    one = lambda r: r.get("jobs", 4) == 1
    if len(jobs) == 1:
        at_once = f"{jobs[0]} compilation{'s' if jobs[0] != 1 else ''} at a time"
    else:
        later = ", ".join(r["instance"] for r in recs if one(r)) if 1 in jobs else ""
        at_once = (f"{' or '.join(map(str, jobs))} compilations at a time"
                   + (f" ({later} one at a time: two 8 GB SBCL imports at once swap on "
                      "this 16 GB machine)" if later else ""))
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
            "d4's decision-DNNF, before FiFO smooths it. Times are wall-clock, "
            f"{at_once}, each limited to "
            f"{limit:g} minutes. SBCL ran with {heaps} and a 1 GB control stack, "
            "d4 with a 64 MB stack (the defaults, 1 GB, 2 MB and 8 MB, are too small "
            "for the larger circuits).")
    if any(r.get("fifo_lisp", "installed") != "installed" for r in recs):
        text += (" The circuits were imported by FiFO with its d4 importer rewritten to "
                 "use bit-vector scopes and iterative traversal (branch "
                 "ddnnf-import-bitvector-scopes); the released importer runs out of "
                 "memory on circuits of about a million nodes.")
    text += (" Model count (verified) is the number of models of the compiled circuit "
             "(all literals set to 1 in the smoothed circuit), that is, the number of "
             "truck walks the theory allows. Every circuit kept was checked against an "
             "independent count of those walks by dynamic programming over the grid "
             "(H-1 steps, each a drive to a neighbouring cell or a wait, from p1-1 to a "
             "goal cell), which also agrees with sharpSAT on every problem shown; the "
             "two counts were equal for every circuit in the table.")
    if any(r.get("status") == "ok" for r in recs) and max(
            int(r["size"].split("x")[0]) for r in recs) == MAX_SIZE:
        text += (f" Grids larger than {MAX_SIZE}×{MAX_SIZE} are omitted: from 8×8 on, "
                 "d4 often crashes (bus error or segmentation fault) or returns a wrong "
                 "circuit without any error, and repeated runs on the same CNF give "
                 "different circuits.")
    if any(t > 1 for t in tries.values()):
        text += (" Tries counts the runs of d4 on a problem, failed ones included, and "
                 "the times are those of the run that passed.")
    text += query_note(queries)
    for r in recs:
        if r.get("node_limit"):
            text += (f" For {r['instance']}, FiFO's circuit-size cap (*ddnnf-node-limit*, "
                     f"2,000,000 nodes) was raised to {r['node_limit']:,}: the smoothed "
                     "import of its d4 circuit exceeds the default.")
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
        text += " \"error\": no run finished — d4 crashed every time."
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
        r"\begin{minipage}{\textwidth}\small " + note_tex + r"\end{minipage}",
        r"\end{document}", ""])


def main():
    recs, history = {}, []
    for line in open(os.path.join(RES, NAME + ".jsonl")):
        if line.strip():
            r = json.loads(line)
            recs[r["instance"]] = r          # the latest record of each problem
            history.append(r)
    recs = sorted((r for r in recs.values() if int(r["size"].split("x")[0]) <= MAX_SIZE),
                  key=lambda r: (int(r["size"].split("x")[0]), int(r["instance"].split("-")[1])))
    lisp = lambda r: r.get("fifo_lisp", "installed")
    # d4 runs with the latest record's importer; a later check of a saved
    # circuit is not a run
    tries = {r["instance"]: sum(1 for h in history
                                if h["instance"] == r["instance"] and lisp(h) == lisp(r)
                                and "checked_later" not in h)
             for r in recs}
    queries = {}
    qfile = os.path.join(RES, "query-evidence.jsonl")
    if os.path.exists(qfile):
        for line in open(qfile):
            if line.strip():
                q = json.loads(line)
                queries[q["instance"]] = q   # the latest query run of each problem
    queries = {k: v for k, v in queries.items() if any(r["instance"] == k for r in recs)}
    rows = [row(r, tries[r["instance"]], queries.get(r["instance"])) for r in recs]
    note = caption(recs, tries, queries)
    cols = COLS
    if all(t == 1 for t in tries.values()):
        cols = [c for c in cols if c[0] != "tries"]
    if not queries:
        cols = [c for c in cols if c[0] != "query"]
    write(NAME, cols, TITLE, rows, note)
    srows = summary_rows(recs, queries)
    write(NAME + "-summary", [c for c in SUMMARY_COLS if c[0] != "query" or queries],
          TITLE + ": means by grid size", srows, summary_note(recs) + " " + note)


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


def summary_rows(recs, queries):
    """One row per grid size: the mean of each column over its compiled problems."""
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
                    "d4_t": f"{m('d4_s'):.2f}", "total_t": f"{m('wall_s'):.1f}",
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
