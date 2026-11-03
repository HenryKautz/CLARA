# TwoPackageOneway

[TwoPackage](../TwoPackage/README.md) with **25% of the roads one-way**: one
truck, two packages, at least one of them delivered.  Added 2026-11-01.  How
the problems were made and solved is in the [top-level README](../README.md)
and [scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 3..7, K = 1..4 (the seed): made with TwoPackage's
`ppgen.sh` settings plus `--oneway 25`.  An N×N grid with no airports, one
truck and two packages placed at random, two possible destinations per package
(never its own start; the packages may share one), and the goal that **at
least one** package reaches one of its destinations (`--require some`):
`(or (at pkg1 a) (at pkg1 b) (at pkg2 c) (at pkg2 d))`.  Drives cost 1, each
load and unload 1 (domain `clara-logistics.pddl`).  No preferences.

`--oneway 25` makes a quarter of the grid's two-way roads one-way, each in a
random direction, keeping every place reachable from every other: 3 of 12
roads at 3×3, 6 of 24 at 4×4, 10 of 40 at 5×5, 15 of 60 at 6×6, 21 of 84 at
7×7 (each problem's header says how many).  The same seed gives TwoPackage's
truck and package starts and destinations, so each problem is the TwoPackage
problem of the same name with one direction of those roads removed (compare
the two files' `road` facts).

The **hypotheses** are the four literals, named `at-pkgI-<place>` by
`recognize.sh`; chance is 1/4.

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

`<goal>` is the problem name followed by the hypothesis's object and place,
e.g. `grid4x4-1-pkg1-p2-3`.  The true hypothesis of `<goal>-obs*.txt` is that
goal's.

## Results

Full tables: [tables.md](tables.md).  Every limit below is wall-clock time
for the whole run; when a run of some kind failed by timeout or memory at a
size, that kind of run was stopped there for that size and every larger one
("killed" in the tables).  Accuracy scores a run 1/k when the true hypothesis
ties with k − 1 others for the highest posterior.

**Planning** (30 minutes per solver run).  Every goal at every size was
planned by tt-open-wbo-inc, and EvalMaxSAT proved every plan optimal; tt's
plans were all already optimal, so the evidence comes from EvalMaxSAT's
plans throughout.  Mean horizon grows from 7.2 (3×3) to 15.2 (7×7), about one
step longer than TwoPackage's at each size; the slowest size, 7×7, takes
56 s (tt) and 30 s (EvalMaxSAT) per goal on average.

**Original problems** (2026-11-02, `scripts/plan-originals.py`, no evidence).
Each `gridNxN-K.pddl` was also planned as it is, its goal the disjunction (any
one package delivered).  tt-open-wbo-inc found the shortest feasible horizon
H0 with kissat (`--maxslices 200`); then tt-open-wbo-inc, and EvalMaxSAT at
`--numslices H0`, minimised cost at each of H0..H0+4 (`--longer 4`) and kept
the cheapest plan.  30 minutes per solver call, 24 hours per run; an
EvalMaxSAT plan counts only when it proved the optimum at all five horizons.
Both solvers planned all 20 problems and EvalMaxSAT proved every optimum;
mean H0 grows from 6.0 (3×3) to 12.5 (7×7), where a run takes 87 s (tt) and
267 s (EvalMaxSAT) on average.  The kept plan's horizon was H0 every time:
no longer horizon was cheaper.  tt's plans were all optimal.  Checked against
the goal plans (any goal plan also solves the original): H0 equals the
smallest shortest horizon among each problem's goals, and every optimum
equals the cheapest goal plan within H0..H0+4 — all 20 problems pass.  Plans:
`gridNxN-K-tt.answer`, `gridNxN-K-eval.answer`; records:
`results/originals.jsonl`.

**Recognition** (30 minutes per run).

- **max-term** solved every run at every size (mean 10 s at 3×3, 330–380 s
  at 7×7).  With 25% of the plan observed its accuracy is 0.39–0.50 (chance
  0.25), mean posterior of the true goal 0.38–0.48; with the whole plan,
  accuracy 1.0 and mean posterior ≥ 0.981.
- **SharpSAT-TD** solved all of 3×3 (accuracy 0.375 at 25%, 1.0 at 100%;
  mean posterior 0.48 and 0.998).  At 4×4 it timed out on one
  evidence-free problem, so it stopped there.
- **MC-SAT** often failed to mix (status `nomix`: the chain froze, which is a
  failed estimate, not a timeout): at 3×3, 15 of 36 runs; at 4×4, 21 of 36.
  Where it did mix with the whole plan observed it agreed with the exact
  methods.  It timed out at 5×5 and stopped there.

**d4** (2 hours per compilation).  Every theory through 6×6 compiled, and
three of the four at 7×7; grid7x7-1 (the longest recognition horizon, 19)
timed out after 2 hours at 35 GB.  sharpSAT confirmed the circuit's model
count for 15 of the 19 circuits; on the other four the check ran out of its
30 minutes, so those are unverified.  No count check disagreed.
