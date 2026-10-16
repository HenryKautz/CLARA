#!/usr/bin/env python3
"""make-tables.py -- summary tables of the recognize.sh sweep, per grid size.

Reads results/runs.jsonl (from run-recognize.py) and results/cnf-sizes.txt
(from cnf-size.sh), and writes results/table-NxN.{md,tex,pdf}: one row per
method, over the pinned (obsN) evidence of that grid size.  A run's final record
is the one at the longest time limit tried (1 min, then 15 min for a timeout).
"""
import collections, json, os, re, subprocess, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
SIZES = [("3x3", 2, ["max-term", "sharpsat-td", "mc-sat", "addmc"]),
         ("4x4", 3, ["max-term", "sharpsat-td", "mc-sat"]),
         ("5x5", 4, ["max-term", "sharpsat-td", "mc-sat"]),
         ("6x6", 5, ["max-term", "sharpsat-td", "mc-sat"])]

# (key, header lines, alignment)
COLS = [("method", ["Method"], "l"),
        ("runs", ["Runs"], "r"),
        ("vars", ["CNF", "variables"], "r"),
        ("clauses", ["CNF", "clauses"], "r"),
        ("mean_t", ["Mean", "time (s)"], "r"),
        ("max_t", ["Max", "time (s)"], "r"),
        ("in_top", ["True goal", "among top", "scorers"], "r"),
        ("alone", ["True goal", "is the sole", "top scorer"], "r"),
        ("p_true", ["Mean", "P(true", "goal)"], "r")]


def span(xs):
    lo, hi = min(xs), max(xs)
    return f"{lo:,}" if lo == hi else f"{lo:,}–{hi:,}"


def rows_for(size, goals, methods, final, sizes, nobs=None):
    """One row per method, over the runs of SIZE -- only those with NOBS observed
    actions when NOBS is given."""
    rows = []
    for m in methods:
        rs = [r for (ev, meth), r in final.items() if meth == m and f"grid{size}-" in ev
              and (nobs is None or r["n_obs"] == nobs)]
        ok = [r for r in rs if r["status"] == "ok"]
        cnf = [sizes[r["evidence"]] for r in rs]
        n = len(rs)
        rows.append({
            "method": m, "runs": str(n),
            "vars": span([v for v, _ in cnf]), "clauses": span([c for _, c in cnf]),
            "mean_t": f"{sum(r['wall_s'] for r in ok) / len(ok):.1f}" if ok else "–",
            "max_t": f"{max(r['wall_s'] for r in ok):.1f}" if ok else "–",
            "in_top": f"{sum(r['correct'] for r in ok)}/{n}",
            "alone": f"{sum(1 for r in ok if r['correct'] and len(r['argmax']) == 1)}/{n}",
            "p_true": f"{sum(r['posterior'][r['true_goal']] for r in ok) / len(ok):.3f}" if ok else "–",
        })
    return rows


def title(size, goals, n_problems, nobs=None):
    """(title, subtitle): the title names the grid and the evidence length; the
    subtitle carries the rest, so neither runs long."""
    obs = ("all evidence lengths" if nobs is None
           else f"{nobs} observed action{'' if nobs == 1 else 's'}")
    return (f"SimpleGrid {size.replace('x', '×')}, {obs}",
            f"{goals} possible goals per problem; {n_problems} problems; pinned evidence")


def notes(unfinished, addmc, two_pass):
    """The per-table notes: how the runs were timed, and whether every one finished."""
    done = ("every run finished" if not unfinished else
            f"{unfinished} run{' did' if unfinished == 1 else 's did'} not finish within "
            "15 minutes; each counts as a miss in the top-scorer columns and is left out "
            "of the times and mean P(true goal)")
    limit = ("each first limited to 1 minute and rerun with 15 minutes if it timed out "
             "(its time is then that of the rerun)" if two_pass else
             "each limited to 15 minutes")
    return NOTES_TEXT.format(parallel="8 runs in parallel" + (" (ADDMC: 2)" if addmc else ""),
                             limit=limit, done=done)


NOTES_TEXT = ("Each run is one problem, one pinned evidence file (the first N drives of a "
         "plan) and one recognize.sh --counter method. CNF size is the instantiated "
         "problem plus evidence that every method starts from (max-term adds its own "
         "soft clauses); it depends on the problem and evidence, not the method. Times "
         "are wall-clock, {parallel}, {limit}; {done}. \"Top scorers\" are the "
         "hypotheses sharing the highest posterior, so a tie counts as among them but "
         "not as sole.")

PDF_WIDTH_IN = 7     # the PDF's text width: title, table and notes all fit in it


def markdown(heading, rows, note):
    head = "| " + " | ".join("<br>".join(h) for _, h, _ in COLS) + " |"
    align = "|" + "|".join(":--" if a == "l" else "--:" for _, _, a in COLS) + "|"
    body = ["| " + " | ".join(r[k] for k, _, _ in COLS) + " |" for r in rows]
    return "\n".join([f"## {heading[0]}", "", f"*{heading[1]}*", "", head, align, *body,
                      "", textwrap.fill(note, 80), ""])


def tex_escape(s):
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("×", r"$\times$")


def latex(heading, rows, note):
    spec = "".join(a for _, _, a in COLS)
    head = " & ".join(r"\makecell[%s]{%s}" % ("lb" if a == "l" else "rb", r"\\".join(map(tex_escape, h)))
                      for _, h, a in COLS)
    body = "\n".join(" & ".join(tex_escape(r[k]).replace("–", "--") for k, _, _ in COLS) + r" \\"
                     for r in rows)
    margin = (8.5 - PDF_WIDTH_IN) / 2
    return "\n".join([
        r"\documentclass[10pt]{article}",
        # letter paper, portrait, a %g-inch text width: the title and notes wrap
        # to it, and the table is never wider
        r"\usepackage[letterpaper,hmargin=%gin,vmargin=0.75in]{geometry}" % margin,
        r"\usepackage{booktabs,makecell,adjustbox}",
        r"\usepackage[T1]{fontenc}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        r"\section*{%s}" % tex_escape(heading[0]),
        r"\noindent\emph{%s}\par\medskip" % tex_escape(heading[1]),
        r"\newsavebox{\tbl}",
        r"\begin{lrbox}{\tbl}\small\begin{tabular}{%s}" % spec,
        r"\toprule", head + r" \\", r"\midrule", body, r"\bottomrule",
        r"\end{tabular}\end{lrbox}",
        # logged so the generator can say whether the table had to be scaled
        r"\typeout{TABLEWIDTH \the\wd\tbl\space TEXTWIDTH \the\textwidth}",
        r"\noindent\adjustbox{max width=\textwidth}{\usebox{\tbl}}",
        r"\par\bigskip\noindent",
        r"\begin{minipage}{\textwidth}\small "
        + re.sub(r'"([^"]*)"', r"``\1''", tex_escape(note)).replace("--counter", r"\texttt{-{}-counter}")
        + r"\end{minipage}",
        r"\end{document}", ""])


def compile_pdf(name):
    """pdflatex results/NAME.tex, report the table's natural width, tidy up."""
    base = os.path.join(RES, name)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                    name + ".tex"], cwd=RES, check=True, stdout=subprocess.DEVNULL)
    m = re.search(r"TABLEWIDTH ([\d.]+)pt TEXTWIDTH ([\d.]+)pt", open(base + ".log").read())
    tw, xw = float(m.group(1)), float(m.group(2))
    for ext in ("aux", "log"):
        os.remove(base + "." + ext)
    print(f"wrote {base}.{{md,tex,pdf}}  table {tw / 72.27:.2f} in"
          + (f" -> scaled to {xw / 72.27:.2f} in" if tw > xw else ""))


# --- the summary: one row per grid size, a column group per method -----------

SUMMARY_METHODS = ["max-term", "sharpsat-td", "mc-sat"]
SUMMARY_TITLE = "SimpleGrid plan recognition by grid size and observations"
SUMMARY_CAPTION = ("Fully connected grids with 1 truck and multiple possible goal "
                   "destinations. \"Among top\": the runs in which the true goal has the "
                   "highest posterior, tied or alone. \"Is top\": the runs in which the "
                   "true goal alone has the highest posterior.")
# per method: (key, header)
SUB = [("time", ["Mean", "time (s)"]), ("among", ["Among", "top"]), ("istop", ["Is", "top"])]
LEAD = [("size", ["Grid", "size"]), ("goals", ["Goals"]),
        ("mindist", ["Min", "goal", "distance"]), ("obs", ["Obser-", "vations"]),
        ("vars", ["Mean", "CNF", "variables"]), ("clauses", ["Mean", "CNF", "clauses"])]


def min_goal_distance(problem):
    """The --mindist a problem was generated with, from its recorded ppgen settings."""
    m = re.search(r"^;;   --mindist (\d+)$", open(os.path.join(HERE, problem)).read(), re.M)
    if not m:
        raise SystemExit(f"{problem} records no --mindist")
    return int(m.group(1))


def summary_rows(final, sizes):
    """One row per grid size and number of observed actions."""
    rows = []
    for size, goals, _methods in SIZES:
        evs_all = sorted({ev for (ev, _m) in final if f"grid{size}-" in ev})
        for nobs in sorted({final[(ev, SUMMARY_METHODS[0])]["n_obs"] for ev in evs_all}):
            evs = [ev for ev in evs_all if final[(ev, SUMMARY_METHODS[0])]["n_obs"] == nobs]
            dists = {min_goal_distance(final[(ev, SUMMARY_METHODS[0])]["problem"]) for ev in evs}
            if len(dists) != 1:
                raise SystemExit(f"{size}: problems differ in --mindist: {sorted(dists)}")
            row = {"size": size.replace("x", "×"), "goals": str(goals),
                   "mindist": str(dists.pop()), "obs": str(nobs),
                   "vars": f"{sum(sizes[e][0] for e in evs) / len(evs):,.0f}",
                   "clauses": f"{sum(sizes[e][1] for e in evs) / len(evs):,.0f}"}
            for m in SUMMARY_METHODS:
                rs = [final[(ev, m)] for ev in evs]
                ok = [r for r in rs if r["status"] == "ok"]
                n = len(rs)
                row["unfinished", m] = n - len(ok)
                row["n"] = n
                row[m, "time"] = f"{sum(r['wall_s'] for r in ok) / len(ok):.1f}" if ok else "–"
                row[m, "among"] = f"{sum(r['correct'] for r in ok)}/{n}"
                row[m, "istop"] = f"{sum(1 for r in ok if r['correct'] and len(r['argmax']) == 1)}/{n}"
            rows.append(row)
    return rows


def latex_page(body_lines, caption):
    margin = (8.5 - PDF_WIDTH_IN) / 2
    return "\n".join([
        r"\documentclass[10pt]{article}",
        r"\usepackage[letterpaper,hmargin=%gin,vmargin=0.75in]{geometry}" % margin,
        r"\usepackage{booktabs,makecell,adjustbox}",
        r"\usepackage[T1]{fontenc}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        r"\section*{%s}" % tex_escape(SUMMARY_TITLE),
        r"\newsavebox{\tbl}",
        r"\begin{lrbox}{\tbl}\small",
        *body_lines,
        r"\end{lrbox}",
        r"\typeout{TABLEWIDTH \the\wd\tbl\space TEXTWIDTH \the\textwidth}",
        r"\noindent\adjustbox{max width=\textwidth}{\usebox{\tbl}}",
        r"\par\bigskip\noindent",
        r"\begin{minipage}{\textwidth}\small "
        + re.sub(r'"([^"]*)"', r"``\1''", tex_escape(caption)) + r"\end{minipage}",
        r"\end{document}", ""])


def cell(lines, align="r"):
    return r"\makecell[%sb]{%s}" % (align, r"\\".join(map(tex_escape, lines)))


def summary_caption(rows):
    """The fixed text, the number of examples per grid size, and -- only if
    there are any -- the runs that did not finish within 15 minutes."""
    per_size = collections.OrderedDict()
    for r in rows:
        per_size[r["size"]] = per_size.get(r["size"], 0) + r["n"]
    text = SUMMARY_CAPTION + " Examples (evidence files, each run with every method): " + \
        ", ".join(f"{s} {n}" for s, n in per_size.items()) + "."
    misses = [(r["size"], r["obs"], m, r["unfinished", m]) for r in rows
              for m in SUMMARY_METHODS if r["unfinished", m]]
    if misses:
        text += (" Not solved within 15 minutes (counted as misses, left out of the "
                 "mean times): " + "; ".join(
                     f"{s}, {o} observation{'' if o == '1' else 's'}, {m}: {k} run{'' if k == 1 else 's'}"
                     for s, o, m, k in misses) + ".")
    return text


def summary_tables(final, sizes):
    rows = summary_rows(final, sizes)
    dash = lambda s: tex_escape(s).replace("–", "--")
    caption = summary_caption(rows)

    # 1. one row per grid size; a three-column group per method
    md_head = ([" ".join(h).replace("- ", "") for _, h in LEAD]
               + [f"{m}<br>{' '.join(h)}" for m in SUMMARY_METHODS for _, h in SUB])
    md = [f"## {SUMMARY_TITLE}", "",
          "| " + " | ".join(md_head) + " |",
          "|" + "|".join(["--:"] * len(md_head)) + "|",
          *("| " + " | ".join([r[k] for k, _ in LEAD]
                              + [r[m, k] for m in SUMMARY_METHODS for k, _ in SUB]) + " |"
            for r in rows),
          "", textwrap.fill(caption, 80), ""]
    ncol = len(LEAD) + 3 * len(SUMMARY_METHODS)
    group = " & ".join([""] * len(LEAD)) + " & " + " & ".join(
        r"\multicolumn{3}{c}{%s}" % m for m in SUMMARY_METHODS) + r" \\"
    rules = " ".join(r"\cmidrule(lr){%d-%d}" % (len(LEAD) + 1 + 3 * i, len(LEAD) + 3 + 3 * i)
                     for i in range(len(SUMMARY_METHODS)))
    head = " & ".join([cell(h) for _, h in LEAD]
                      + [cell(h) for _ in SUMMARY_METHODS for _, h in SUB]) + r" \\"
    body = [" & ".join([dash(r[k]) for k, _ in LEAD]
                       + [dash(r[m, k]) for m in SUMMARY_METHODS for k, _ in SUB]) + r" \\"
            for r in rows]
    # 14 columns: tighter padding so it fits 7 inches at full size, not scaled down
    tex = latex_page([r"\setlength{\tabcolsep}{3pt}",
                      r"\begin{tabular}{%s}" % ("r" * ncol), r"\toprule", group, rules,
                      head, r"\midrule", *body, r"\bottomrule", r"\end{tabular}"],
                     caption)
    write_all("summary-by-grid", "\n".join(md), tex)


def write_all(name, md, tex):
    base = os.path.join(RES, name)
    open(base + ".md", "w").write(md)
    open(base + ".tex", "w").write(tex)
    compile_pdf(name)


def main():
    recs = [json.loads(l) for l in open(os.path.join(RES, "runs.jsonl"))]
    final = {}
    for r in recs:
        k = (r["evidence"], r["method"])
        if k not in final or r["limit_s"] > final[k]["limit_s"]:
            final[k] = r
    sizes = {}
    for line in open(os.path.join(RES, "cnf-sizes.txt")):
        ev, _h, v, c = line.split()
        sizes[ev] = (int(v), int(c))
    for size, goals, methods in SIZES:
        runs = [r for (ev, m), r in final.items() if f"grid{size}-" in ev and m in methods]
        nprob = len({r["problem"] for r in runs})
        two_pass = any(r["limit_s"] < 900 for r in recs
                       if f"grid{size}-" in r["evidence"] and r["method"] in methods)
        # The whole size, then one table per number of observed actions.
        for nobs in [None] + sorted({r["n_obs"] for r in runs}):
            rows = rows_for(size, goals, methods, final, sizes, nobs)
            heading = title(size, goals, nprob, nobs)
            name = f"table-{size}" + ("" if nobs is None else f"-obs{nobs}")
            base = os.path.join(RES, name)
            unfinished = sum(1 for r in runs if r["status"] != "ok"
                             and (nobs is None or r["n_obs"] == nobs))
            note = notes(unfinished, "addmc" in methods, two_pass)
            open(base + ".md", "w").write(markdown(heading, rows, note))
            open(base + ".tex", "w").write(latex(heading, rows, note))
            compile_pdf(name)
    summary_tables(final, sizes)


if __name__ == "__main__":
    main()
