# FourPackage

Two trucks, four packages, at least one delivered; regenerated 2026-11-01
with every road present (no `--knockout`).  The 2026-10-31 regeneration, which
kept the old 40% knockout, is in git at commit d228f28; the version before
that, with goal preferences, and its results, is
[OldVersions/FourPackage](../OldVersions/FourPackage/README.md).  How the
problems were made and solved is in the [top-level README](../README.md) and
[scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 6..15, K = 1..4 (the seed): an N×N grid with no
airports and every road between adjacent cells, in both directions; two
trucks and four packages placed at random, three possible destinations per
package (never its own start), and the goal that
**at least one** package reaches one of its destinations (`ppgen.sh --require
some`): a disjunction of twelve literals `(at pkgI <place>)`.  Drives cost 2,
each load and unload 1 (domain `clara-logistics.pddl`, the same actions and
costs as the old `clara-logistics-handling.pddl`).

**No preferences.**  The old version also made each goal literal a preference
of weight 8 (`--preferences 8 8`); now the hard disjunction is the only goal.
The seeds are the old ones, and dropping `--knockout` leaves the starts and
destinations as they were: each problem is the knockout problem of the same
name with its missing roads restored.

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
goal from 6×6 to 8×8.  The 30 minutes bound each call of the solver, one per
horizon tried, so a whole tt run can take longer.  At 9×9 it timed out on
`grid9x9-3-pkg2-p4-5` (83 minutes over its horizons), after planning 46 of
the 48 goals (grid9x9-1 and grid9x9-2 complete); 3 of the 10×10 goals had
been planned, and 11×11 and up were not.  EvalMaxSAT proved all 48 6×6 plans
optimal and 47 at 7×7, then timed out on `grid7x7-1-pkg4-p7-1` (horizon 18),
so it stopped at 7×7 (3 of the 8×8 plans were proved before that).  tt's plans
were optimal in every case EvalMaxSAT proved.  The evidence comes from
EvalMaxSAT's plan where it has one and from tt's otherwise (0, 1, 45, 46 and 3
goals at 6×6 … 10×10).  Mean horizon grows from 9.5 (6×6) to 14.0 (9×9).

Compared with the knockout version (commit d228f28), restoring the roads
shortened the plans and let EvalMaxSAT go one size further (it stopped at 6×6
before), but tt stopped one size earlier (at 10×10 before): with more roads
there are more drive actions per step.

**Recognition** (30 minutes per run).  Every method stopped at 6×6, the
smallest size.  With no evidence max-term finished three of the four
problems (mean 1421 s) and timed out on the fourth, so its runs with evidence
were killed; SharpSAT-TD and MC-SAT timed out on their first.  No run with
evidence finished.

**d4** (2 hours per compilation).  None of the four 6×6 theories compiled
within 2 hours (peak memory 36–46 GB), so no larger size was tried.
