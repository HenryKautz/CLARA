# RestrictedPlanning

How good, and how fast, is **restricted cost minimization** — FiFO's
`planner.sh --restrict steps|actions` — compared with EvalMaxSAT on the whole
theory? Run on the single-goal problems of [SimpleGrid](../SimpleGrid/README.md),
[TwoPackage](../TwoPackage/README.md) and [ThreePackage](../ThreePackage/README.md).

## The method

`planner.sh` plans in two steps: kissat finds the shortest horizon H with a plan,
ignoring costs, and then a MaxSAT solver minimizes cost over the whole theory at
H. Restricted minimization keeps the first step and shrinks the second. Every
action atom `(OCCURS a t)` that kissat's plan does not license is forced false
before the MaxSAT solve:

- **`steps`**: each of the SAT plan's actions is allowed only at the step it was
  taken, so the solver can only *drop* actions (a pointless load, a detour that
  can be cut out);
- **`actions`**: each ground action the SAT plan took is allowed at *any* step, so
  the solver can also move, reorder and repeat them.

The SAT plan satisfies both restrictions, so the restricted problem is never
unsatisfiable, and

  optimum ≤ `actions` cost ≤ `steps` cost ≤ SAT-plan cost.

`planner.sh` also reports the SAT plan's own cost (one more solve with every action
atom pinned), so all four numbers come from every restricted run. The FiFO
change, its tests and its documentation are FiFO commit 2b264a3, where the
option is marked **experimental** (FiFO's `discussion.md`, "Restricted Cost
Minimization"). These runs used the FiFO checkout just before that commit, in
which the kept SAT plan was named `<root>-sat.answer` rather than
`<root>-restrict-sat.answer`.

## The experiment

`compare.py BENCH` runs each single-goal problem three times with EvalMaxSAT, at
a fixed horizon (`--numslices`):

| Method | Run |
|---|---|
| full | `planner.sh --numslices H` — the optimum at H, proven (no run hit its limit) |
| steps | `planner.sh --numslices H --restrict steps` |
| actions | `planner.sh --numslices H --restrict actions` |

H is the goal's shortest horizon (**slack 0**, what the planner itself would
use) and that plus 4 (**slack 4**: a plan has room to waste steps, as when a
recognition theory fixes one horizon for every hypothesis). kissat is
deterministic, so the two restricted runs restrict the same SAT plan.

Problems: SimpleGrid 3×3–7×7 (one truck driving to a destination; 160 goals),
TwoPackage (one truck, two packages, free loads; 80 goals), ThreePackage (one
truck, three packages, loads and unloads cost 1; 96 goals). Slurm `cpu` nodes,
16 runs at a time; `run-easy.sh`, `run-three.sh`. Results: `results/*.jsonl`,
one record per run; tables: `python3 summarize.py`.

Columns: **SAT/steps/actions = opt** count the problems where that plan is
optimal; **excess** is the mean (cost − optimum) / optimum; **time** is the mean
wall time of a whole `planner.sh` run (translation, instantiation, kissat and
the MaxSAT solve or solves).  Each MaxSAT solve was limited to 1800 s.  On
SimpleGrid and TwoPackage every full run proved its optimum.

## Results

### SimpleGrid

| Grid | Slack | Problems | SAT = opt | steps = opt | actions = opt | SAT excess | steps excess | actions excess | Full time | steps time | actions time |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3×3 | 0 | 8 | 8 | 8 | 8 | 0.0% | 0.0% | 0.0% | 3.0 s | 2.9 s | 2.9 s |
| 3×3 | 4 | 8 | 8 | 8 | 8 | 0.0% | 0.0% | 0.0% | 6.0 s | 2.6 s | 3.0 s |
| 4×4 | 0 | 12 | 12 | 12 | 12 | 0.0% | 0.0% | 0.0% | 3.3 s | 2.8 s | 2.8 s |
| 4×4 | 4 | 12 | 12 | 12 | 12 | 0.0% | 0.0% | 0.0% | 8.6 s | 2.9 s | 3.8 s |
| 5×5 | 0 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 4.9 s | 3.0 s | 3.0 s |
| 5×5 | 4 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 13.8 s | 3.3 s | 5.1 s |
| 6×6 | 0 | 20 | 20 | 20 | 20 | 0.0% | 0.0% | 0.0% | 8.3 s | 3.5 s | 3.5 s |
| 6×6 | 4 | 20 | 20 | 20 | 20 | 0.0% | 0.0% | 0.0% | 22.6 s | 4.0 s | 7.3 s |
| 7×7 | 0 | 24 | 24 | 24 | 24 | 0.0% | 0.0% | 0.0% | 10.6 s | 4.3 s | 4.3 s |
| 7×7 | 4 | 24 | 24 | 24 | 24 | 0.0% | 0.0% | 0.0% | 30.5 s | 5.1 s | 9.6 s |

### TwoPackage

| Grid | Slack | Problems | SAT = opt | steps = opt | actions = opt | SAT excess | steps excess | actions excess | Full time | steps time | actions time |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3×3 | 0 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 2.9 s | 3.0 s | 3.0 s |
| 3×3 | 4 | 16 | 8 | 11 | 11 | 29.2% | 17.5% | 17.5% | 7.3 s | 3.3 s | 4.0 s |
| 4×4 | 0 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 4.5 s | 3.8 s | 3.8 s |
| 4×4 | 4 | 16 | 4 | 8 | 8 | 64.8% | 40.8% | 40.8% | 30.7 s | 4.5 s | 6.0 s |
| 5×5 | 0 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 7.0 s | 5.4 s | 5.5 s |
| 5×5 | 4 | 16 | 5 | 12 | 12 | 32.7% | 11.7% | 11.7% | 45.3 s | 6.8 s | 9.6 s |
| 6×6 | 0 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 17.4 s | 8.4 s | 8.4 s |
| 6×6 | 4 | 16 | 2 | 6 | 6 | 45.5% | 36.3% | 36.3% | 107.2 s | 11.0 s | 14.2 s |
| 7×7 | 0 | 16 | 16 | 16 | 16 | 0.0% | 0.0% | 0.0% | 85.2 s | 16.5 s | 16.6 s |
| 7×7 | 4 | 16 | 7 | 13 | 13 | 10.8% | 5.0% | 5.0% | 559.9 s | 20.4 s | 29.8 s |

### ThreePackage

Here the full EvalMaxSAT runs often did not finish: **Full proven** counts the
problems whose optimum it proved; the rest hit its 1800 s limit with a best plan
(then "optimum" means the cheapest plan of the three runs), and **Unfinished**
counts problems where it found no plan at all, which are left out of the table.
**Beats full** counts problems where a restricted plan was cheaper than the full
run's best.

| Grid | Slack | Problems | Full proven | SAT = opt | steps = opt | actions = opt | Beats full | SAT excess | steps excess | actions excess | Full time | steps time | actions time | Unfinished |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 5×5 | 0 | 32 | 32 | 32 | 32 | 32 | 0 | 0.0% | 0.0% | 0.0% | 236.2 s | 21.4 s | 21.8 s | 0 |
| 5×5 | 4 | 32 | 26 | 0 | 12 | 13 | 0 | 15.5% | 6.6% | 6.1% | 941.8 s | 21.8 s | 38.2 s | 0 |
| 6×6 | 0 | 22 | 19 | 22 | 22 | 22 | 0 | 0.0% | 0.0% | 0.0% | 808.6 s | 54.2 s | 55.3 s | 10 |
| 6×6 | 4 | 23 | 9 | 1 | 9 | 13 | 3 | 15.3% | 8.4% | 5.5% | 1609.3 s | 57.3 s | 85.7 s | 9 |
| 7×7 | 0 | 8 | 6 | 8 | 8 | 8 | 0 | 0.0% | 0.0% | 0.0% | 1359.3 s | 85.8 s | 86.2 s | 24 |
| 7×7 | 4 | 8 | 0 | 2 | 3 | 4 | 1 | 10.0% | 7.1% | 5.6% | 1891.9 s | 93.7 s | 106.1 s | 24 |

All 384 restricted ThreePackage runs finished (most in 1–2 minutes).  On the
67 problems where the full run found no plan, `actions` improved on the SAT plan
in 21 of 33 at slack 4 (mean cost 0.952 of the SAT plan's) and in none of 34 at
slack 0.

## What the numbers say

- **At the shortest horizon, kissat's plan was already optimal** — on every one
  of the 160 SimpleGrid, 80 TwoPackage and 62 ThreePackage problems where an
  optimum is known (proved, or the best of the three runs).  So at the horizon
  the planner itself uses, the restriction never changed the cost here, and
  neither would skipping the MaxSAT step altogether: a minimal-length plan in
  these domains leaves little to waste.  The value of `--restrict` at slack 0 is
  speed and certainty of an answer: it returns that plan with its cost in
  20–90 s where EvalMaxSAT on the whole theory took 4–23 minutes on average, and
  found nothing in 30 minutes on 24 of the 32 7×7 goals.
- **With slack, the SAT plan wastes and the restriction recovers part of it.**
  Four extra slices let kissat's plan run 11–65% over the optimum (TwoPackage),
  10–16% (ThreePackage).  Restricted minimization removes roughly half to
  two-thirds of that excess: on ThreePackage `actions` ends 5.5–6.1% above the
  optimum, `steps` 6.6–8.4%.
- **`actions` ≥ `steps`, but the gap is small.**  On TwoPackage the two gave the
  same cost every time; on ThreePackage `actions` was optimal more often (13
  against 9 of 23 at 6×6) for 1.5× the time.
- **Why it stops short.**  The restricted solver can drop and re-time the SAT
  plan's own actions, but never use a road the SAT plan did not drive.  A single
  truck's route cannot be shortened by dropping drives (each one is needed to get
  from one place to the next) — only by driving other roads, which the
  restriction forbids.  The FiFO test suite's 4×4 shows this cleanly: SAT plan
  22, optimum 14, both restrictions 22.
- **Where to go next** (the intermediate heuristics): allow, beside the SAT
  plan's actions, the actions *near* them — e.g. every drive from a place the
  truck visits, or every action within one step of the SAT plan's — so a shorter
  route becomes reachable while the search space stays small; or iterate:
  restrict, solve, and use the new plan's actions for the next restriction.
