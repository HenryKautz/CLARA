# ThreePackage

Plan-recognition problems between [TwoPackage](../TwoPackage/README.md) and
[FourPackage](../FourPackage/README.md) in difficulty: one truck, three packages,
and every package must be delivered.  The file types are described in the
[top-level README](../README.md).

## Layout

```
gridNxN-K.pddl                    problems; clara-logistics-handling.pddl, their domain
goals/
  <combo>.pddl                    the problem with one goal combination as its goal
  <combo>.answer                  a plan for it at its shortest horizon
evidence/
  <combo>-obsK.txt                its first K actions, pinned to time steps (K = 4, 8)
  <combo>-ordK.txt                the same actions as an ordering only
recognition/gridNxN-K.pddl        the recognition problem: the goal as the disjunction
                                  of its 8 combinations, with its recognition horizon
scnf/<problem>.scnf               the evidence-free recognition theory (compile-d4.py)
circuits/<problem>.dnnf           its d4 circuit, where d4 succeeded
scripts/                          the pipeline (below) and summarize.py
results/                          one JSON record per run
*.log, tables.md                  the runs' logs; summarize.py's tables
```

`<combo>` names a problem and one destination per package, e.g.
`grid5x5-1-pkg1-p2-4-pkg2-p3-4-pkg3-p4-3`.

## Problems

`gridNxN-K.pddl`, N = 5, 6, 7, four per size (K is the seed;
`scripts/make-problems.sh`):
- an N×N grid with no airports; 20% of the roads between adjacent places are
  knocked out, keeping a random spanning tree so every place stays reachable;
- one truck and three packages, placed at random;
- domain `clara-logistics-handling.pddl` (as FourPackage): drives cost 2, each
  `load` and `unload` costs 1, no transfer action;
- each package has two possible destinations, never its own start (packages may
  share one), and **every** package must reach one of its own (`ppgen.sh
  --require all`): the goal is a conjunction of three binary disjunctions,
  `(and (or (at pkg1 a) (at pkg1 b)) (or (at pkg2 c) (at pkg2 d)) (or (at pkg3 e) (at pkg3 f)))`;
- no preferences.

The **hypotheses** are the goal's 2³ = 8 combinations, one destination per
package, so chance is 1/8.  All of FiFO's runs here used the installed FiFO, whose
SatPlan axioms use the `mutex` encoding at every size (FourPackage kept the
original pairwise encoding up to 11×11); the two encodings have the same plans.

## The pipeline

`scripts/run-all.sh`, one Slurm job (`sbatch`, see its header):

1. **`plan-goals.py`** — for each problem and each combination, `goals/<combo>.pddl`
   with that combination as its goal, planned by `planner.sh`: kissat searches
   horizons upward from the reachability bound to the shortest one with a plan,
   and an exact MaxSAT solver minimizes cost there.  The plan's first 4 and 8
   actions, sorted by time step, become the evidence (exactly K actions, even
   when the K-th shares its step with one not taken).  Once a problem's 8 goals
   are planned, `recognition/<problem>.pddl` is written: its goal rewritten as
   `(or (and …) … (and …))` over the 8 combinations — the same plans — so
   `recognize.sh` scores combination I through a derived atom `rechypI`.  Its
   **recognition horizon** is the largest of the 8 shortest horizons: the
   shortest horizon at which every combination can be achieved, so that no
   hypothesis is refuted by the horizon alone.
2. **`run-recognize.py`** — `recognize.sh --evidence-kind fifo` on every pinned
   evidence file, with `max-term` (Ramírez & Geffner's cheapest-plan
   difference, exact MaxSAT by EvalMaxSAT) and `sharpsat-td` (exact weighted
   model counting), at the recognition horizon, 10 minutes per run, 14 at a
   time.  **As soon as a method times out at a size, its other runs at that size
   are killed and none at that size or larger is started.**
3. **`compile-d4.py`** — each problem's evidence-free recognition theory compiled
   by d4 (`marginals.sh --solver d4 --project`), 1 hour per problem, 4 at a
   time, stopping after the first size where a compilation times out; each
   circuit's model count is checked against sharpSAT's count of the theory.
   (TwoPackage's script with ThreePackage's paths.)
4. `summarize.py > tables.md`.

**What changed on the way** (all in the scripts and records):
- The first 26 5×5 goals were minimized with WMaxCDCL.  It then failed to
  finish within 1800 s on six 5×5 goals at horizons 24–27, which EvalMaxSAT
  solved in 6–18 minutes, so EvalMaxSAT was used from then on (the `solver`
  field of each record).
- Seven goals at 6×6–7×7 (horizons 31–38) got no plan from EvalMaxSAT within
  3600 s.  They were planned with FiFO's new `planner.sh --restrict actions` at
  the horizon already found: every action atom kissat's plan never used is
  forced false before the MaxSAT solve, so EvalMaxSAT searches only re-timings
  and subsets of kissat's actions.  3–7 minutes each, recorded as
  `EvalMaxSAT_bin --restrict actions`, not proven optimal.  (`--restrict` was
  new in the FiFO checkout, not yet committed or installed, when these ran.  On
  every SimpleGrid, TwoPackage and ThreePackage goal whose optimum is known,
  kissat's plan at the shortest horizon was already optimal, so these seven are
  probably optimal too.)  Sixteen more goals have EvalMaxSAT's best plan at its 3600 s limit,
  also unproven.  Evidence only needs a plan; costs marked unproven below.
- d4 was restarted as `scripts/run-d4.sh` after grid5x5-3's circuit (1.87M nodes)
  overflowed FiFO's default 2,000,000-node import cap: the cap raised to 20M, the
  count check given 30 minutes instead of 2.
- `run-recognize.py` first recorded three SharpSAT-TD runs as errors: the count
  had stopped at `recognize.sh --timeout` (600 s) a moment before the run limit.
  They are timeouts, and are recorded so (with a note); the runner now
  classifies them that way.

**To reproduce**, from the CLARA checkout (FiFO installed; every stage resumes
from `results/*.jsonl`):

```sh
bash ThreePackage/scripts/make-problems.sh
sbatch --export=ALL,TP_SCRIPTS=$PWD/ThreePackage/scripts -o ThreePackage/run-all.log \
       ThreePackage/scripts/run-all.sh                  # plan, evidence, recognition, d4
python3 ThreePackage/scripts/plan-goals.py --sizes 6 7 --restrict actions \
        --planner ~/Programming/FiFO/bin/planner.sh     # the 7 goals EvalMaxSAT left unplanned
sbatch --export=ALL,TP_SCRIPTS=$PWD/ThreePackage/scripts -o ThreePackage/d4.log \
       ThreePackage/scripts/run-d4.sh                   # d4 with the raised node cap
python3 ThreePackage/scripts/verify-count.py grid5x5-1 grid5x5-2 --limit 7200
```

## Results

The tables are `python3 scripts/summarize.py`, from `results/*.jsonl`.  Runs on
the UVA CS Slurm `cpu` partition, 2026-10-29 to 30.

### Problems

Plan time is a whole `planner.sh` run (horizon search, instantiation, MaxSAT).
"Unproved" counts the goals whose cost is not a proven optimum (above).

| Problem | Roads | Goals planned | Shortest horizon (min–max) | Recognition horizon | Optimal cost (min–max) | Actions (min–max) | Plan time (mean / max) | Evidence files (obs) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| grid5x5-1 | 32 | 8/8 | 13–18 | 18 | 22–28 | 14–17 | 123 s / 355 s | 16 |
| grid5x5-2 | 32 | 8/8 | 21–24 | 24 | 34–40 | 20–23 | 881 s / 1,853 s | 16 |
| grid5x5-3 | 32 | 8/8 | 16–22 | 22 | 30–38 | 18–22 | 386 s / 713 s | 16 |
| grid5x5-4 | 32 | 8/8 | 23–27 | 27 | 40–46 | 23–26 | 983 s / 1,789 s | 16 |
| grid6x6-1 | 48 | 8/8 | 18–24 | 24 | 28–40 | 17–23 | 309 s / 635 s | 16 |
| grid6x6-2 | 48 | 8/8 | 20–29 | 29 | 32–50 | 19–28 | 2,046 s / 3,777 s | 16 |
| grid6x6-3 | 48 | 8/8 | 32–38 | 38 | 56–68 (4 unproved) | 31–37 | 3,062 s / 5,493 s | 16 |
| grid6x6-4 | 48 | 8/8 | 21–27 | 27 | 38–46 | 22–26 | 1,045 s / 1,985 s | 16 |
| grid7x7-1 | 67 | 8/8 | 27–35 | 35 | 46–62 (8 unproved) | 26–34 | 2,924 s / 6,097 s | 16 |
| grid7x7-2 | 67 | 8/8 | 24–30 | 30 | 40–52 (3 unproved) | 23–29 | 3,061 s / 5,251 s | 16 |
| grid7x7-3 | 67 | 8/8 | 27–32 | 32 | 48–56 (3 unproved) | 27–31 | 3,170 s / 4,929 s | 16 |
| grid7x7-4 | 67 | 8/8 | 24–31 | 31 | 42–54 (5 unproved) | 24–30 | 4,410 s / 5,664 s | 16 |

Every goal was planned and every problem has its 16 pinned evidence files (and
16 ordering ones).  Horizons grow fast: the recognition horizons are 18–27 at
5×5 and 30–38 at 7×7 — longer than TwoPackage's 7×7 (16–19) and close to
FourPackage's 6×6 (22–35).

### Recognition

Columns as in TwoPackage, plus **Killed**: runs still going when another run of
the same method at that size timed out.  "not run": the method had stopped at a
smaller size.

| Grid | Observed actions | Method | Evidence files | Runs | Ok | Timeout | Killed | Error |
|---|--:|---|--:|--:|--:|--:|--:|--:|
| 5×5 | 4 | max-term | 32 | 7 | 0 | 1 | 6 | 0 |
| 5×5 | 4 | sharpsat-td | 32 | 7 | 0 | 4 | 3 | 0 |
| 5×5 | 8 | max-term | 32 | not run | | | | |
| 5×5 | 8 | sharpsat-td | 32 | not run | | | | |
| 6×6, 7×7 | 4, 8 | both | 128 | not run | | | | |

**Neither method finished a single run within 10 minutes.**  The first 5×5 runs
(grid5x5-1, 4 observed actions, horizon 18) timed out, so by the rule above both
methods stopped at 5×5 after one batch; 8- and 4-action runs at 6×6 and 7×7 were
never started.

Two runs of that same evidence file were then made by hand with no limit
(`results/untimed-runs.jsonl`):
- **max-term finished in 13 minutes** (16 exact MaxSAT solves of about 49 s
  each; instantiation under a second) — and scored every hypothesis 1/8.  Each
  hypothesis cost the same with the evidence as without it, c(O) = c(¬O), at
  costs 22–28: the first 4 actions (drives toward the packages) fit an optimal
  plan for every combination, and at a horizon with slack an equally cheap plan
  avoiding exactly those pinned actions always exists.  So at 4 observations
  max-term gives no information here even when it finishes.
- **SharpSAT-TD did not finish in 3 hours**; Slurm stopped it at its limit.

### d4 compilation

| Problem | Horizon | CNF vars | CNF clauses | Status | Compile time | d4 time | Circuit nodes | d4 peak memory | Checked by |
|---|--:|--:|--:|---|--:|--:|--:|--:|---|
| grid5x5-1 | 18 | 8,492 | 37,961 | ok (limit 3600 s) | 214 s | 174 s | 93,041 | 560 MB | count (verify-count.py, 580 s) |
| grid5x5-2 | 24 | 11,726 | 50,966 | ok (limit 3600 s) | 272 s | 182 s | 32,573 | 383 MB | unverified (count timed out at 7,200 s) |
| grid5x5-3 | 22 | 10,716 | 46,735 | error (limit 3600 s) | 1,391 s | – | – | 6,541 MB | – |
| grid5x5-4 | 27 | 13,553 | 57,674 | error (limit 3600 s) | 2,050 s | – | – | 2,978 MB | – |
| grid6x6-1 | 24 | 16,554 | 74,815 | timeout (limit 3600 s) | 3,605 s | – | – | 11,216 MB | – |
| grid6x6-2 | 29 | 21,127 | 90,872 | timeout (limit 3600 s) | 3,608 s | – | – | 25,627 MB | – |
| grid6x6-3 | 38 | 27,424 | 119,801 | timeout (limit 3600 s) | 3,611 s | – | – | 4,156 MB | – |
| grid6x6-4 | 27 | 19,941 | 84,316 | timeout (limit 3600 s) | 3,614 s | – | – | 18,335 MB | – |
| grid7x7-1..4 | – | – | – | not run | – | – | – | – | – |

(CNF vars and clauses are those of d4's input: the whole theory, with the
projection given to d4 as a `c p show` line.)

d4 compiled grid5x5-1 and grid5x5-2 in 3–5 minutes.  On grid5x5-3 and
grid5x5-4 it produced a "projected" circuit that mentions an atom outside the
projection (a `TSEITIN` atom of the mutex encoding) — d4 did not honour its
projection — and FiFO refused it, on all three attempts, the same atom each
time.  All four 6×6 compilations hit the 1-hour limit, so 7×7 was not tried.
`verify-count.py` (TwoPackage's) checks the two circuits' model counts against
sharpSAT's exact count of the theory, given 2 hours each.  grid5x5-1's agrees
(1,295,682 models, counted in 580 s); grid5x5-2's count did not finish, so that
circuit is **unverified** — d4 has returned wrong circuits before (SimpleGrid,
from 8×8 on), so check it before relying on it.

## Summary

ThreePackage is far harder than TwoPackage, not "between" it and FourPackage in
the sense of being cheap to run:
- **Planning** is fine at every size: all 96 goals planned (73 proven optimal),
  but 5–100 minutes per goal at 6×6–7×7.
- **Recognition did not finish a run within 10 minutes at the smallest size.**
  An untimed max-term run takes about 13 minutes at 5×5 and, at 4 observed
  actions, does not discriminate (posterior 1/8 for every goal); exact counting
  takes more than 3 hours.
- **d4** compiles half the 5×5 theories, fails on the other half (an invalid
  projection), and none at 6×6 within an hour.

Runs that would answer more, but were not made because of the time they take:
max-term at 5×5 with a longer limit (≈13 min × 64 pinned files ≈ 14 CPU-hours,
more for 8 observations), and anything at 6×6–7×7.
