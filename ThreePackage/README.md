# ThreePackage

One truck, three packages, every package delivered; regenerated 2026-11-01
with every road present (no `--knockout`).  The 2026-10-31 regeneration, which
kept the old 20% knockout, is in git at commit d228f28; the version before
that, with its results, is
[OldVersions/ThreePackage](../OldVersions/ThreePackage/README.md).  How the
problems were made and solved is in the [top-level README](../README.md) and
[scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 5, 6, 7, K = 1..4 (the seed): an N×N grid with no
airports and every road between adjacent cells, in both directions; one truck
and three packages placed at random, two possible destinations per package
(never its own start), and the goal that
**every** package reaches one of its own (`ppgen.sh --require all`):
`(and (or (at pkg1 a) (at pkg1 b)) (or (at pkg2 c) (at pkg2 d)) (or (at pkg3 e) (at pkg3 f)))`.
Drives cost 2, each load and unload 1 (domain `clara-logistics.pddl`, the same
actions and costs as the old `clara-logistics-handling.pddl`).  No preferences.
The seeds are the old ones, and dropping `--knockout` leaves the starts and
destinations as they were: each problem is the knockout problem of the same
name with its missing roads restored.

The **hypotheses** are the goal's 2³ = 8 combinations, one destination per
package.  `recognition/<problem>.pddl` writes the goal as `(or (and …) … (and
…))` over them — the same plans — and `recognize.sh` scores combination I
through a derived atom `rechypI` (the header lists which is which); chance is
1/8.

## Layout

```
gridNxN-K.pddl              problems; clara-logistics.pddl, their domain
goals/
  <goal>.pddl               the problem with one hypothesis as its hard goal
  <goal>-tt.answer          tt-open-wbo-inc's plan at the goal's shortest horizon
  <goal>-eval.answer        EvalMaxSAT's, when it proved its optimum within 30 minutes
  <goal>.answer             the plan the evidence was cut from (EvalMaxSAT's, else tt's)
evidence/
  <problem>-none.txt        no observations: (and)
  <goal>-obs25.txt          the first 25% of the plan's actions (rounded up), pinned
  <goal>-obs100.txt         all of the plan's actions, pinned
recognition/<problem>.pddl  the goal as one disjunction of the hypotheses; its header
                            lists them, their shortest horizons, and the
                            RECOGNITION HORIZON (the largest), which every run uses
scnf/<problem>.scnf         the evidence-free recognition theory (compile-d4.py)
circuits/<problem>.dnnf     its d4 circuit, where d4 succeeded; one over 100 MB is
                            committed as .part-* pieces: cat <problem>.dnnf.part-* > <problem>.dnnf
results/                    plans.jsonl, runs.jsonl, compile-d4.jsonl: a record per run
tables.md                   scripts/summarize.py's tables
*.log                       the stages' logs
```

`<goal>` is the problem name followed by one destination per package, e.g.
`grid5x5-1-pkg1-p2-4-pkg2-p3-4-pkg3-p4-3`.  The true hypothesis of
`<goal>-obs*.txt` is that combination's `rechypI`.

## Results

Full tables: [tables.md](tables.md).  Every limit below is wall-clock time
for the whole run; when a run of some kind failed by timeout or memory at a
size, that kind of run was stopped there for that size and every larger one
("killed" in the tables).

**Planning** (30 minutes per solver run).  At 5×5 tt-open-wbo-inc planned all
32 goals (mean 98 s) and EvalMaxSAT proved every plan optimal (mean 251 s);
tt's plans were all already optimal.  Mean horizon 18.2.  At 6×6 EvalMaxSAT
timed out on `grid6x6-1-pkg1-p1-3-pkg2-p6-1-pkg3-p3-6` (horizon 24) and
tt-open-wbo-inc on `grid6x6-2-pkg1-p4-3-pkg2-p1-2-pkg3-p6-5`, so both stopped
at 6×6.  Before that, all eight goals of grid6x6-1 had been planned, so that
one 6×6 problem has a recognition problem (horizon 24); of the 16 6×6 goals
planned in all, EvalMaxSAT proved 5 and the other 11 use tt's plans.  7×7
was not planned.

Restoring the roads did not make these problems easier than the knockout
version (commit d228f28): the 5×5 horizons are shorter (mean 18.2 against
20.9), but with more roads there are more drive actions per step, the solvers
take about twice as long at 5×5, and both planners still stop at 6×6.

**Recognition** (30 minutes per run).  Every method stopped at 5×5, the
smallest size, on the evidence-free runs: max-term finished one problem
(403 s) and timed out on another; SharpSAT-TD finished one (631 s) and timed
out on another; MC-SAT timed out on its first.  No run with evidence was
reached.

**d4** (2 hours per compilation).  All four 5×5 theories compiled (mean
2186 s; grid5x5-3 took 6647 s and 16.5 GB for a 940 MB circuit).  sharpSAT
confirmed the circuit's model count for three of them; on grid5x5-4 the check
ran out of its 30 minutes, so that circuit is unverified (d4 is known to
miscompile larger theories; see
[OldVersions/SimpleGrid/results/compile-d4.md](../OldVersions/SimpleGrid/results/compile-d4.md)).
The one 6×6 theory (grid6x6-1) timed out after 2 hours at 25 GB.  No count
check disagreed.
