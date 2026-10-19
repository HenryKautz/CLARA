Files for UVA DARPA CLARA.

## Layout

```
SimpleGrid/
  gridNxN-K.pddl                    problems
  goals/
    <problem>-<place>.pddl          single-goal variants of the problems
    <problem>-<place>.answer        a plan for each variant
  evidence/
    <problem>-<place>-obsN.txt      observations from those plans, pinned to time steps
    <problem>-<place>-ordN.txt      the same observations, as an ordering only
TwoPackage/
  gridNxN-K.pddl                    problems
  goals/
    <problem>-<pkg>-<place>.pddl    single-goal variants of the problems
    <problem>-<pkg>-<place>.answer  a plan for each variant
    <problem>-<pkg>-<place>-clean.answer  the same plan without the other package's loads/unloads
  evidence/
    <problem>-<pkg>-<place>-obsN.txt   observations from the cleaned plans, pinned to time steps
    <problem>-<pkg>-<place>-ordN.txt   the same observations, as an ordering only
  results/                          sweep results (compile-d4, query-evidence, recognition runs)
  circuits/                         theories and d4 circuits (see circuits/README.md)
```

## SimpleGrid

Plan-recognition problems in the `clara-logistics` PDDL domain, made with the
[FiFO](https://github.com/HenryKautz/FiFO) tools `ppgen.sh`, `planner.sh` and
`evgen.sh`.

**Problems** — `gridNxN-K.pddl`.  An N×N grid of places named `pR-C` (row,
column), with two-way roads between adjacent places and no airports, airplanes
or packages.  A single truck starts at the corner `p1-1`.  The goal is a
disjunction: the truck must reach any one of several possible destinations, all
at least a fixed number of road steps from `p1-1`.  `K` numbers the problems of
each size, which differ in the destinations chosen.  Each file opens with
comment lines recording the `ppgen.sh` settings that generated it, so it can be
regenerated exactly.

**`goals/`** — one entry per possible goal of a problem.
- `<problem>-<place>.pddl` is the problem with its goal narrowed to that single
  destination: the truck must end at `<place>`.  Everything else is unchanged.
- `<problem>-<place>.answer` is a shortest plan for it, as written by
  `planner.sh`: `SAT`, the plan's cost as `(*OBJECTIVE* n)`, then the trajectory
  — `(HOLDS fluent t)` for what is true at time step `t`, and `(OCCURS action t)`
  for the action taken at step `t`.  Each plan is one of possibly many shortest
  routes, so it stands for "an agent heading to `<place>`".

**`evidence/`** — what an observer sees of such an agent: the first `N` actions
of the plan in `goals/<problem>-<place>.answer`, in two forms.  Only actions are
observed, not the truck's location.  The file's true goal is `<place>`; a
recognizer is given the original problem's possible goals and the evidence, and
asked which goal is being pursued.  Longer prefixes (larger `N`) give more
evidence, up to the length of the plan.
- `<problem>-<place>-obsN.txt` pins each action to its time step: a single
  `(and ...)` of `(occurs (drive truck1 from to) t)` literals, the actions at
  steps 1..N.  This claims the agent started at once and was watched without
  gaps.  Use it with `recognize.sh --evidence-kind fifo`, or
  `planner.sh --evidence-file`.
- `<problem>-<place>-ordN.txt` gives the same actions as an ordering only: a
  single `(occur-in-order a1 ... aN)` — they happened in this order, at time
  steps it does not fix.  This is the Ramírez & Geffner observation model.  Use
  it with `recognize.sh` (its default `--evidence-kind pddl`), or
  `planner.sh --pddl-evidence-file`.
- Each file is one form, which is what `recognize.sh` needs to negate it.  The
  original problems can be given to `recognize.sh` directly: their goal literals
  `(at truck1 <place>)` are the hypotheses, e.g.
  `recognize.sh clara-logistics.pddl grid4x4-1.pddl evidence/grid4x4-1-p3-4-ord3.txt`.
- Each file opens with comment lines recording the `evgen.sh` settings that made
  it, with paths relative to `SimpleGrid/`: run `evgen.sh` with those settings
  from `SimpleGrid/` to regenerate it exactly.

## TwoPackage

Harder plan-recognition problems in the same domain, made the same way
(`TwoPackage/make-instances.sh N`).

**Problems** — `gridNxN-K.pddl`, N = 3..7, four per size.  An N×N grid with no
airports, one truck and two packages, all placed at random.  Each package has
two possible destinations, never its own starting place (the two packages may
share one).  The goal is that **at least one** package reaches one of its
destinations (`ppgen.sh --require some`), so the goal is a disjunction of four
literals `(at pkgI <place>)` — the recognition hypotheses.  The truck must
drive to a package, load it, drive on and unload it, so plans include `load`
and `unload` actions, not just drives.

**`goals/`** — one entry per goal literal: `<problem>-<pkg>-<place>.pddl`
narrows the goal to `(at <pkg> <place>)`, and `.answer` is a shortest plan for
it.  Loads and unloads cost nothing, so a cost-minimising planner may leave in a
pointless load of the *other* package; `-clean.answer` is the same plan without
any load or unload of the other package (still a valid plan), and the evidence
is taken from it.

**`evidence/`** — as for SimpleGrid, the first `N` actions of the cleaned plan,
now any of `drive`, `load` and `unload`, for N = 1 up to the smaller of
gridsize − 2 and the plan's length.  The true goal of
`<problem>-<pkg>-<place>-obsN.txt` is the hypothesis `at-<pkg>-<place>`, e.g.
`recognize.sh clara-logistics.pddl grid4x4-1.pddl evidence/grid4x4-1-pkg1-p2-3-obs2.txt --evidence-kind fifo`.

### TwoPackage results

Every evidence file (N = 1 … gridsize − 2) was run through `recognize.sh
--evidence-kind fifo` with three counters — `max-term` (Ramírez & Geffner's
cheapest-plan difference, MaxSAT only), `sharpsat-td` (exact weighted model
counting) and `mc-sat` (sampling) — by `run-recognize.py`: first at a 5-minute
limit per run, then the runs that timed out again at 20 minutes, a method
stopping at the size where it first times out.  Separately, `compile-d4.py`
compiled each problem's evidence-free theory to a d4 circuit, and
`query-evidence.py` conditioned it on evidence.  The tables are regenerated by
`python3 summarize.py` from `results/*.jsonl`.

**Accuracy counts ties fractionally.**  A run's *accuracy* is 1/k when the true
goal is among the k top-scoring goals, and 0 otherwise — the expected accuracy
of breaking the tie at random.  The `correct` field of the older records counts
any tie containing the true goal as a success (*top-k* below).  That inflates
max-term badly: its top goal is a tie in 216 of its 240 runs, because many
plans to different goals cost the same, so its top-k is 0.95 while its accuracy
is 0.41.  Chance is 0.25 (four hypotheses).

**Recognition**, the last attempt of each run (the 20-minute rerun where there
was one):

| Grid | Method | Runs | Ok | Timeout | Error | Accuracy | Top-k | P(true) | Mean time | Max time |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3×3 | max-term | 16 | 16 | 0 | 0 | 0.458 | 0.812 | 0.401 | 24 s | 27 s |
| 3×3 | mc-sat | 16 | 16 | 0 | 0 | 0.438 | 0.438 | 0.374 | 85 s | 98 s |
| 3×3 | sharpsat-td | 16 | 16 | 0 | 0 | 0.500 | 0.562 | 0.460 | 28 s | 29 s |
| 4×4 | max-term | 32 | 32 | 0 | 0 | 0.380 | 0.875 | 0.353 | 35 s | 39 s |
| 4×4 | mc-sat | 32 | 32 | 0 | 0 | 0.281 | 0.281 | 0.309 | 454 s | 617 s |
| 4×4 | sharpsat-td | 32 | 32 | 0 | 0 | 0.406 | 0.406 | 0.387 | 52 s | 191 s |
| 5×5 | max-term | 48 | 48 | 0 | 0 | 0.410 | 1.000 | 0.388 | 56 s | 67 s |
| 5×5 | mc-sat | 16 | 4 | 8 | 4 | 0.500 | 0.500 | 0.319 | 579 s | 596 s |
| 5×5 | sharpsat-td | 48 | 48 | 0 | 0 | 0.375 | 0.375 | 0.412 | 67 s | 102 s |
| 6×6 | max-term | 64 | 64 | 0 | 0 | 0.405 | 0.938 | 0.386 | 103 s | 144 s |
| 6×6 | sharpsat-td | 8 | 0 | 8 | 0 | – | – | – | – | – |
| 7×7 | max-term | 80 | 80 | 0 | 0 | 0.419 | 1.000 | 0.394 | 355 s | 636 s |

| Method | Finished runs | Accuracy | Top-k | P(true) | Tied top goal |
|---|--:|--:|--:|--:|--:|
| max-term | 240 | 0.411 | 0.954 | 0.386 | 216 |
| mc-sat | 52 | 0.346 | 0.346 | 0.329 | 0 |
| sharpsat-td | 96 | 0.406 | 0.417 | 0.411 | 2 |

MC-SAT was not run past 5×5, nor SharpSAT-TD past 6×6: each had timed out at
the size before.  MC-SAT's 5×5 accuracy is over the 4 runs that finished.

**d4 compilation** (compile time is the whole `marginals.sh --solver d4
--project` run; query time is one evidence query on the saved circuit):

| Problem | Horizon | CNF vars | Status | Compile time | d4 time | Circuit nodes | Query time | Checked by |
|---|--:|--:|---|--:|--:|--:|--:|---|
| grid3x3-1 | 7 | 671 | ok (limit 300 s) | 4.2 s | 0.1 s | 277 | 0.007 s | count |
| grid3x3-2 | 8 | 778 | ok (limit 300 s) | 4.2 s | 0.1 s | 964 | 0.009 s | count |
| grid3x3-3 | 8 | 778 | ok (limit 300 s) | 2.7 s | 0.1 s | 812 | 0.008 s | count |
| grid3x3-4 | 8 | 778 | ok (limit 300 s) | 2.8 s | 0.1 s | 408 | 0.007 s | count |
| grid4x4-1 | 12 | 2,184 | ok (limit 300 s) | 7.1 s | 4.0 s | 31,222 | 0.027 s | oracle |
| grid4x4-2 | 12 | 2,184 | ok (limit 300 s) | 7.6 s | 3.5 s | 37,036 | 0.028 s | count |
| grid4x4-3 | 9 | 1,602 | ok (limit 300 s) | 3.0 s | 0.5 s | 3,752 | 0.016 s | count |
| grid4x4-4 | 9 | 1,602 | ok (limit 300 s) | 2.5 s | 0.4 s | 3,391 | 0.016 s | count |
| grid5x5-1 | 8 | 2,226 | ok (limit 300 s) | 3.7 s | 0.1 s | 716 | 0.023 s | count |
| grid5x5-2 | 11 | 3,147 | ok (limit 300 s) | 9.2 s | 4.4 s | 24,607 | 0.040 s | count |
| grid5x5-3 | 12 | 3,454 | ok (limit 300 s) | 5.7 s | 2.6 s | 15,959 | 0.043 s | count |
| grid5x5-4 | 13 | 3,761 | ok (limit 300 s) | 18.1 s | 13.2 s | 69,156 | 0.053 s | oracle |
| grid6x6-1 | 14 | 5,908 | ok (limit 300 s) | 120.6 s | 106.5 s | 531,383 | 0.160 s | count |
| grid6x6-2 | 11 | 4,570 | ok (limit 300 s) | 16.3 s | 9.3 s | 47,943 | 0.065 s | count |
| grid6x6-3 | 16 | 6,800 | ok (limit 300 s) | 264.3 s | 244.0 s | 969,097 | 0.259 s | count (long) |
| grid6x6-4 | 14 | 5,908 | ok (limit 300 s) | 18.6 s | 11.7 s | 37,145 | 0.111 s | count |
| grid7x7-1 | 17 | 9,925 | timeout (limit 1200 s) | 1204.6 s | – | – | – | – |
| grid7x7-2 | 16 | 9,314 | ok (limit 1200 s) | 336.0 s | 306.1 s | 1,176,679 | 0.221 s | count (long) |
| grid7x7-3 | 16 | 9,314 | ok (limit 300 s) | 77.2 s | 66.3 s | 155,200 | 0.141 s | count |
| grid7x7-4 | 19 | 11,147 | timeout (limit 1200 s) | 1204.6 s | – | – | – | – |

**What the numbers say.**
- With ties split, max-term (0.41), SharpSAT-TD (0.41) and MC-SAT (0.35) are
  all above chance but far from reliable at these evidence lengths: one or a
  few observed actions rarely single out the goal.  Mean P(true goal) tells the
  same story (0.39, 0.41, 0.33).
- Exact counting stops early: SharpSAT-TD finishes every run through 5×5 but
  none on 6×6 within 20 minutes; MC-SAT is slow from 4×4 on.  Max-term
  finishes everything, up to 636 s on 7×7.
- **MC-SAT's 5×5 errors are a mixing failure.**  The four errors ("every
  posterior is zero", all on grid5x5-2) come from the sampler, not the problem.
  A rerun of one of them with its working files kept (2026-10-19, 47 min)
  finished, but MC-SAT never sampled either of package 1's goals, with or
  without the evidence (sampling efficiency 0.03–0.04): it put the whole
  posterior on package 2's goals, and the true goal — a package-1 goal — got 0.
  The per-hypothesis posterior divides P(h | T, O) by P(h | T); when the two
  chains settle in different modes, every goal has one of the two estimated as
  0, and every posterior comes out 0.  FiFO (2026-10-19) now reports a goal
  sampled under the evidence but never without it as a sampling failure,
  rather than as posterior 0, and warns when a goal was never sampled at all.
- d4 compiles every problem through 6×6 and two of four at 7×7; a compiled
  circuit then answers each evidence query in 0.26 s or less, matching
  SharpSAT-TD to 2·10⁻¹⁵ where both ran.  Every circuit used has been checked
  against an independent count (`circuits/README.md`).
