#!/usr/bin/env python3
"""make-tables.py -- summary tables of the recognize.sh sweep, per grid size.

Reads results/runs.jsonl (from run-recognize.py) and results/cnf-sizes.txt
(from cnf-size.sh), and writes results/table-NxN.{md,tex,pdf}: one row per
method, over the pinned (obsN) evidence of that grid size.  A run's final record
is the one at the longest time limit tried (1 min, then 15 min for a timeout).
"""
import collections, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
SIZES = [("3x3", 2, ["max-term", "sharpsat-td", "mc-sat", "addmc"]),
         ("4x4", 3, ["max-term", "sharpsat-td", "mc-sat"]),
         ("5x5", 4, ["max-term", "sharpsat-td", "mc-sat"])]

# (key, header lines, alignment)
COLS = [("method", ["Method"], "l"),
        ("goals", ["Possible", "goals"], "r"),
        ("runs", ["Runs"], "r"),
        ("vars", ["CNF", "variables"], "r"),
        ("clauses", ["CNF", "clauses"], "r"),
        ("long", ["Runs over", "1 min"], "r"),
        ("failed", ["Failed", "at 15 min"], "r"),
        ("mean_t", ["Mean", "time (s)"], "r"),
        ("max_t", ["Max", "time (s)"], "r"),
        ("in_top", ["True goal", "among top", "scorers"], "r"),
        ("alone", ["True goal", "is the sole", "top scorer"], "r"),
        ("p_true", ["Mean", "P(true", "goal)"], "r")]


def span(xs):
    lo, hi = min(xs), max(xs)
    return f"{lo:,}" if lo == hi else f"{lo:,}–{hi:,}"


def rows_for(size, goals, methods, final, sizes):
    rows = []
    for m in methods:
        rs = [r for (ev, meth), r in final.items() if meth == m and f"grid{size}-" in ev]
        ok = [r for r in rs if r["status"] == "ok"]
        cnf = [sizes[r["evidence"]] for r in rs]
        n = len(rs)
        rows.append({
            "method": m, "goals": str(goals), "runs": str(n),
            "vars": span([v for v, _ in cnf]), "clauses": span([c for _, c in cnf]),
            "long": str(sum(1 for r in rs if r["limit_s"] > 60)),
            "failed": str(n - len(ok)),
            "mean_t": f"{sum(r['wall_s'] for r in ok) / len(ok):.1f}" if ok else "–",
            "max_t": f"{max(r['wall_s'] for r in ok):.1f}" if ok else "–",
            "in_top": f"{sum(r['correct'] for r in ok)}/{n}",
            "alone": f"{sum(1 for r in ok if r['correct'] and len(r['argmax']) == 1)}/{n}",
            "p_true": f"{sum(r['posterior'][r['true_goal']] for r in ok) / len(ok):.3f}" if ok else "–",
        })
    return rows


def title(size, goals, n_problems):
    return (f"SimpleGrid {size.replace('x', '×')}: {goals} possible goals per problem "
            f"({n_problems} problems, pinned evidence)")


NOTES = ("Each run is one problem, one pinned evidence file (the first N drives of a "
         "plan) and one recognize.sh --counter method. CNF size is the instantiated "
         "problem plus evidence that every method starts from (max-term adds its own "
         "soft clauses); it depends on the problem and evidence, not the method. Times "
         "are wall-clock, 8 runs in parallel (ADDMC: 2), each first limited to 1 minute "
         "and rerun with 15 minutes if it timed out; a 15-minute rerun is counted in "
         "\"Runs over 1 min\" and its time is that of the rerun. \"Top scorers\" are the "
         "hypotheses sharing the highest posterior, so a tie counts as among them but "
         "not as sole.")


def markdown(size, goals, nprob, rows):
    head = "| " + " | ".join("<br>".join(h) for _, h, _ in COLS) + " |"
    align = "|" + "|".join(":--" if a == "l" else "--:" for _, _, a in COLS) + "|"
    body = ["| " + " | ".join(r[k] for k, _, _ in COLS) + " |" for r in rows]
    return "\n".join([f"## {title(size, goals, nprob)}", "", head, align, *body, "",
                      NOTES, ""])


def tex_escape(s):
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("×", r"$\times$")


def latex(size, goals, nprob, rows):
    spec = "".join(a for _, _, a in COLS)
    head = " & ".join(r"\makecell[%s]{%s}" % ("lb" if a == "l" else "rb", r"\\".join(map(tex_escape, h)))
                      for _, h, a in COLS)
    body = "\n".join(" & ".join(tex_escape(r[k]).replace("–", "--") for k, _, _ in COLS) + r" \\"
                     for r in rows)
    return "\n".join([
        r"\documentclass[10pt]{article}",
        r"\usepackage[landscape,margin=0.7in]{geometry}",
        r"\usepackage{booktabs,makecell}",
        r"\usepackage[T1]{fontenc}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        r"\section*{%s}" % tex_escape(title(size, goals, nprob)),
        r"\begin{tabular}{%s}" % spec,
        r"\toprule", head + r" \\", r"\midrule", body, r"\bottomrule",
        r"\end{tabular}",
        r"\par\bigskip\noindent",
        r"\begin{minipage}{0.95\linewidth}\small "
        + re.sub(r'"([^"]*)"', r"``\1''", tex_escape(NOTES)).replace("--counter", r"\texttt{-{}-counter}")
        + r"\end{minipage}",
        r"\end{document}", ""])


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
        nprob = len({r["problem"] for (ev, _), r in final.items() if f"grid{size}-" in ev})
        rows = rows_for(size, goals, methods, final, sizes)
        base = os.path.join(RES, f"table-{size}")
        open(base + ".md", "w").write(markdown(size, goals, nprob, rows))
        open(base + ".tex", "w").write(latex(size, goals, nprob, rows))
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                        f"table-{size}.tex"], cwd=RES, check=True,
                       stdout=subprocess.DEVNULL)
        for ext in ("aux", "log"):
            os.remove(base + "." + ext)
        print("wrote", base + ".{md,tex,pdf}")


if __name__ == "__main__":
    main()
