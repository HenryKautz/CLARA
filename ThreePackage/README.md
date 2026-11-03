# ThreePackage

One truck, three packages, every package delivered; regenerated 2026-11-01
with every road present (no `--knockout`).  The 2026-10-31 regeneration, which
kept the old 20% knockout, is in git at commit d228f28; the version before
that, with its results, is
[OldVersions/ThreePackage](https://github.com/HenryKautz/CLARA/tree/ac6aa16/OldVersions/ThreePackage), deleted from the tree in 7731002.  How the
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
gridNxN-K-tt.answer         the problem's own plan (its goal, any one hypothesis) by
                            tt-open-wbo-inc, cheapest over horizons H0..H0+4
gridNxN-K-eval.answer       EvalMaxSAT's, where it proved the optimum at all five
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
results/                    plans.jsonl, originals.jsonl, runs.jsonl, compile-d4.jsonl:
                            a record per run
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

**Original problems** (2026-11-02, `scripts/plan-originals.py`, no evidence).
Each `gridNxN-K.pddl` was also planned as it is, its goal `(and (or …) …)`
(every package to one of its destinations).  tt-open-wbo-inc found the
shortest feasible horizon H0 with kissat (`--maxslices 200`); then
tt-open-wbo-inc, and EvalMaxSAT at `--numslices H0`, minimised cost at each of
H0..H0+4 (`--longer 4`) and kept the cheapest plan.  30 minutes per solver
call, 24 hours per run; an EvalMaxSAT plan counts only when it proved the
optimum at all five horizons.

- **5×5**: both solvers planned all four; mean H0 16.5, mean optimum 27.5,
  about 20 minutes per tt run and 33 per EvalMaxSAT run.
- **6×6**: tt-open-wbo-inc planned all four (mean H0 19.5, about 78 minutes
  per run, some of its solves cut off at 30 minutes with the best plan so
  far).  EvalMaxSAT timed out on grid6x6-1 and stopped, so its other three
  6×6 runs were killed: the 6×6 originals have tt plans only.
- **7×7**: at grid7x7-1's H0 (27) tt-open-wbo-inc found no plan at all in
  30 minutes, so tt stopped at 7×7 and the other three runs were killed.
  There are no 7×7 plans.

The kept plan's horizon was H0 every time: no longer horizon was cheaper.
tt's plans were optimal wherever EvalMaxSAT proved one.  Checked against the
goal plans (any goal plan also solves the original): H0 equals the smallest
shortest horizon among the goals for the five problems whose goals were all
planned (5×5 and grid6x6-1), and is no larger than it for grid6x6-2 and -3
(5 and 3 of 8 goals planned); grid6x6-4 has no goal plans to compare.  Every
5×5 optimum equals the cheapest goal plan within H0..H0+4.  No check failed.

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
[OldVersions/SimpleGrid/results/compile-d4.md](https://github.com/HenryKautz/CLARA/blob/ac6aa16/OldVersions/SimpleGrid/results/compile-d4.md)).
The one 6×6 theory (grid6x6-1) timed out after 2 hours at 25 GB.  No count
check disagreed.
