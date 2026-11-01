# FourPackage

Two trucks, four packages, at least one delivered; regenerated 2026-10-31 (the
version before, with goal preferences, and its results, is
[OldVersions/FourPackage](../OldVersions/FourPackage/README.md)).  How the
problems were made and solved is in the [top-level README](../README.md) and
[scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 6..15, K = 1..4 (the seed): an N×N grid with no
airports, 40% of the roads knocked out (a random spanning tree is kept, so every
place stays reachable), two trucks and four packages placed at random, three
possible destinations per package (never its own start), and the goal that
**at least one** package reaches one of its destinations (`ppgen.sh --require
some`): a disjunction of twelve literals `(at pkgI <place>)`.  Drives cost 2,
each load and unload 1 (domain `clara-logistics.pddl`, the same actions and
costs as the old `clara-logistics-handling.pddl`).

**No preferences.**  The old version also made each goal literal a preference
of weight 8 (`--preferences 8 8`); now the hard disjunction is the only goal.

The **hypotheses** are the twelve literals, named `at-pkgI-<place>` by
`recognize.sh`; chance is 1/12.  FiFO's SatPlan axioms use the linear `mutex`
encoding at every size (the old version kept the pairwise one up to 11×11);
the two have the same plans.

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
circuits/<problem>.dnnf     its d4 circuit, where d4 succeeded
results/                    plans.jsonl, runs.jsonl, compile-d4.jsonl: a record per run
tables.md                   scripts/summarize.py's tables
*.log                       the stages' logs
```

`<goal>` is the problem name followed by the hypothesis's package and place,
e.g. `grid6x6-1-pkg1-p1-4`.  The true hypothesis of `<goal>-obs*.txt` is that
goal's.

## Results

Full tables: [tables.md](tables.md).  Every limit below is wall-clock time;
when a run of some kind failed by timeout or memory at a size, that kind of
run was stopped there for that size and every larger one ("killed" in the
tables).  Sizes run in parallel, so runs at larger sizes that had already
finished when a stop came are kept.

**Planning** (30 minutes per solver call).  tt-open-wbo-inc planned every
goal from 6×6 to 9×9.  The 30 minutes bound each call of the solver, one per
horizon tried, so a whole tt run can take longer (up to 41 minutes at 10×10).
At 10×10 it timed out on `grid10x10-4-pkg2-p7-4`, after planning 40 of the 48
goals (two problems complete); 11×11 and up were not planned.  EvalMaxSAT
timed out on one 6×6 goal, so it stopped at 6×6; by then it had proved 46 of
the 48 6×6 plans optimal, 47 at 7×7 and 33 at 8×8, and tt's plans were
optimal in every one of those cases.  The evidence comes from EvalMaxSAT's
plan where it has one and from tt's otherwise (2, 1, 15, 48 and 40 goals at
6×6 … 10×10).

**Recognition** (30 minutes per run).  Every method stopped at 6×6, the
smallest size: with no evidence max-term finished one problem (1777 s) and
timed out on another; SharpSAT-TD and MC-SAT timed out on their first.  No
run with evidence was reached.

**d4** (2 hours per compilation).  None of the four 6×6 theories compiled
within 2 hours (peak memory up to 59 GB), so no larger size was tried.
