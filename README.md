Files for UVA DARPA CLARA: plan-recognition benchmarks, made and solved with
[FiFO](https://github.com/HenryKautz/FiFO).

## Contents

Each benchmark directory has its own README, describing its problems, how they
were made, and its results.

The four grid benchmarks were **regenerated on 2026-10-31**, and on
2026-11-01 ThreePackage and FourPackage were made again without road
knockout and TwoPackageOneway was added (see
[The 2026-10-31 regeneration](#the-2026-10-31-regeneration)); the versions
before 2026-10-31, with their results, were in `OldVersions/`, deleted from the
tree on 2026-11-01 (7731002); they are in git at
[ac6aa16](https://github.com/HenryKautz/CLARA/tree/ac6aa16/OldVersions), and
`git checkout ac6aa16 -- OldVersions` restores them.

| Directory | What it holds | README |
|---|---|---|
| `SimpleGrid/` | One truck on an N×N grid (3×3–10×10) heading for one of N−1 destinations. | [SimpleGrid/README.md](SimpleGrid/README.md) |
| `TwoPackage/` | One truck, two packages with two destinations each, 3×3–7×7; four hypotheses (at least one package delivered). | [TwoPackage/README.md](TwoPackage/README.md) |
| `TwoPackageOneway/` | TwoPackage with 25% of the roads one-way. | [TwoPackageOneway/README.md](TwoPackageOneway/README.md) |
| `ThreePackage/` | One truck, three packages with two destinations each, all to be delivered, 5×5–7×7; eight hypotheses (destination combinations). | [ThreePackage/README.md](ThreePackage/README.md) |
| `FourPackage/` | Two trucks, four packages with three destinations each, 6×6–15×15; twelve hypotheses (at least one package delivered). | [FourPackage/README.md](FourPackage/README.md) |
| `scripts/` | The one pipeline that made and solved all five (below). | [scripts/README.md](scripts/README.md) |
| `reassemble.sh`, `unassemble.sh` | Files over GitHub's 100 MB limit (large d4 circuits) are committed as 90 MB `F.part-*` pieces, and `F` itself is git-ignored. After cloning or pulling, run `./reassemble.sh` to rebuild every `F` from its pieces. Before committing a new large file, run `./unassemble.sh` to split it and add it to `.gitignore`. Both are safe to run again: they report files that are already done. | |
| `AAAI-2010-Benchmarks/` | Ramírez & Geffner's BlockWords and IntrusionDetection, original and as recognition instances, with exact posteriors. | [AAAI-2010-Benchmarks/README.md](AAAI-2010-Benchmarks/README.md) |
| `OldVersions/` (deleted; in git at [ac6aa16](https://github.com/HenryKautz/CLARA/tree/ac6aa16/OldVersions)) | The grid benchmarks as they were before 2026-10-31 (old domain; FourPackage with goal preferences), their results and scripts; `RestrictedPlanning/` (FiFO's experimental `planner.sh --restrict` evaluated on them); and `make-fifo-files.py`/`.lisp`, which wrote the `wff/`, `scnf/` and `wcnf/` files of the old SimpleGrid, TwoPackage and AAAI-2010-Benchmarks (it still has those directories' old paths). | [OldVersions/README.md](https://github.com/HenryKautz/CLARA/blob/ac6aa16/OldVersions/README.md) |

## The datasets at a glance

All five grid families are made by FiFO's `ppgen.sh` with `--style grid
--airports 0 --airplanes 0 --handle-cost 1 --preferences none --domain
clara-logistics`, four problems per size (`--seed 1`…`4`), and solved by the
pipeline below: planning with tt-open-wbo-inc and EvalMaxSAT, recognition
with max-term, SharpSAT-TD and MC-SAT (30 minutes per run), d4 compilation
(2 hours).

| Family | Sizes | Other `ppgen.sh` settings | Hypotheses |
|---|---|---|---|
| SimpleGrid | 3×3–10×10 (32 problems) | `--trucks 1 --packages 0 --destinations N−1 --require all --mindist N+1` (3 at 3×3) `--drive-cost 1` | N−1 truck destinations |
| TwoPackage | 3×3–7×7 (20) | `--trucks 1 --packages 2 --destinations 2 --require some --drive-cost 1` | 4 literals |
| TwoPackageOneway | 3×3–7×7 (20) | TwoPackage's, plus `--oneway 25` | 4 literals |
| ThreePackage | 5×5–7×7 (12) | `--trucks 1 --packages 3 --destinations 2 --require all --drive-cost 2` | 8 destination combinations |
| FourPackage | 6×6–15×15 (40) | `--trucks 2 --packages 4 --destinations 3 --require some --drive-cost 2` | 12 literals |

No family uses `--knockout`.  Each problem's header lists every setting it was
made with.

**Where each method timed out** — the smallest size at which a run failed by
timeout or memory, after which that method was stopped (— means it finished
every size it was given; tt and EvalMaxSAT plan each hypothesis as a goal, 30
minutes per solver call; recognition only runs on sizes that were planned):

| Family | tt-open-wbo-inc | EvalMaxSAT | max-term | SharpSAT-TD | MC-SAT | d4 |
|---|---|---|---|---|---|---|
| SimpleGrid | — | — | — | 7×7 | 7×7 | 10×10 (1 of 4 compiled) |
| TwoPackage | — | — | — | 4×4 | 4×4 | — |
| TwoPackageOneway | — | — | — | 4×4 | 5×5 | 7×7 (3 of 4 compiled) |
| ThreePackage | 6×6 | 6×6 | 5×5 | 5×5 | 5×5 | 6×6 |
| FourPackage | 9×9 | 7×7 | 6×6 | 6×6 | 6×6 | 6×6 (none compiled) |

MC-SAT also often failed to mix (a frozen chain, status `nomix`) on the sizes
it did finish; the family READMEs give its counts.

**Original problems** (2026-11-02, `scripts/plan-originals.py`, one Slurm job
per family via `scripts/run-originals.sh`, no evidence).  Each top-level
`gridNxN-K.pddl` was also planned as it is, its goal the disjunction of the
hypotheses.  tt-open-wbo-inc found the shortest feasible horizon H0 with
kissat (`--maxslices 200`); then tt-open-wbo-inc, and EvalMaxSAT at
`--numslices H0`, minimised cost at each of H0..H0+4 (`--longer 4`, since H0
is set by the quickest hypothesis, which need not be the cheapest) and kept
the cheapest plan.  30 minutes per solver call, 24 hours per run, the same
stop rule; an EvalMaxSAT plan counts only when it proved the optimum at all
five horizons.  Plans are `<F>/gridNxN-K-tt.answer` and `-eval.answer`,
records `<F>/results/originals.jsonl`.

| Family | tt-open-wbo-inc plans | EvalMaxSAT proved | Stopped at |
|---|---|---|---|
| SimpleGrid | 32/32 | 32/32 | — |
| TwoPackage | 20/20 | 20/20 | — |
| TwoPackageOneway | 20/20 | 20/20 | — |
| ThreePackage | 8/12 (5×5, 6×6) | 4/12 (5×5) | tt 7×7, EvalMaxSAT 6×6 |
| FourPackage | 40/40 | 38/40 (all through 13×13, 3 at 14×14, 3 at 15×15) | EvalMaxSAT 14×14 |

In all 234 plans (120 tt-open-wbo-inc, 114 EvalMaxSAT) the kept horizon was H0: no longer horizon gave a cheaper
plan.  tt-open-wbo-inc's plans were optimal wherever EvalMaxSAT proved one.
Every plan was checked against the goal plans (any goal plan also solves the
original): H0 equals the smallest shortest horizon among the problem's goals
(no larger, where only some goals were planned), and every proved optimum
is no more than — in fact equal to — the cheapest goal plan within
H0..H0+4.  No check failed; FourPackage from grid10x10-2 on, and ThreePackage
grid6x6-4, have no goal plans to check against.  FourPackage's originals are
far easier than its goals (the quickest delivery decides H0: 11 at 15×15).

## The 2026-10-31 regeneration

Every problem of SimpleGrid, TwoPackage, ThreePackage and FourPackage was made
again (`scripts/make-problems.py`) with the `ppgen.sh` settings recorded in the
old problem's header, except:

- **domain `clara-logistics`**, FiFO's current one: `load` and `unload` cost
  `(handle-cost)` = 1 each, and there is no `transfer` action.  SimpleGrid and
  TwoPackage used to be planned with the domain FiFO later kept as
  `clara-logistics-old` (free handling, `transfer`; deleted from FiFO's
  library on 2026-11-04, FiFO ffdc377); ThreePackage and FourPackage used a
  local `clara-logistics-handling.pddl`, the same domain under another name.
- **no goal weights or preferences**: the goal is only the hard `(or …)` (or,
  in ThreePackage, `(and (or …) …)`) of the problem.  FourPackage's
  `--preferences 8 8` is gone.

The same seeds give the same grids, roads, starts and destinations; the script
checks that every new problem matches its old one apart from `(handle-cost)` and
the preferences.

**2026-11-01.**  ThreePackage and FourPackage had been made with
`--knockout 20` and `--knockout 40` (that share of the roads removed, keeping
a spanning tree); they were made again without it, from the same seeds, which
leaves their starts and destinations as they were and restores every road.
**TwoPackageOneway** was added: TwoPackage's settings and seeds plus
`--oneway 25`, which makes a quarter of the two-way roads one-way while
keeping every place reachable.  For these three families the script checks
the settings block instead (knockout gone, `--oneway 25` present), and the
planner searches horizons from scratch rather than starting from the old
plan's.  The 2026-10-31 knockout versions and their results are in git at
commit d228f28.

The pipeline (`scripts/`, one Slurm job per family, `scripts/run-family.sh`):

1. **`plan-goals.py`** — each hypothesis as a hard goal (`goals/<goal>.pddl`),
   planned at its **shortest horizon** twice: by `tt-open-wbo-inc-Glucose4_1`
   (anytime) and by `EvalMaxSAT_bin` (exact) at the same horizon.  The evidence
   is cut from EvalMaxSAT's plan when it proved its optimum within 30 minutes,
   else from tt-open-wbo-inc's (`goals/<goal>.answer`; both plans are kept as
   `-tt.answer` / `-eval.answer`).  Then `recognition/<problem>.pddl`: the goal
   as one disjunction of the hypotheses, at the **recognition horizon**, the
   largest of their shortest horizons.
2. **Evidence**, pinned to time steps: none (`evidence/<problem>-none.txt`),
   the first 25% of the plan's actions, rounded up (`-obs25.txt`), and all of
   them (`-obs100.txt`).  Counted in actions, not time steps.
3. **`run-recognize.py`** — the posterior of the hypotheses only, by
   `recognize.sh` with `max-term` (EvalMaxSAT), `sharpsat-td` and `mc-sat`,
   30 minutes per run.
4. **`compile-d4.py`** — each problem's evidence-free recognition theory
   compiled by d4, 2 hours per problem; each circuit's count checked against
   SharpSAT-TD.

**Stop rule**, for every solver and method separately: when a run fails by
timeout or by running out of memory at some grid size, its other runs at that
size are killed and nothing is run at that size or larger.

`python3 scripts/summarize.py --family F` writes the tables in each family's
`tables.md`.

Where each method stopped is tabulated in
[The datasets at a glance](#the-datasets-at-a-glance); details are in each
family's README.

d4 differs from the stop rule in one way: it finishes the size where a
compilation first fails, then tries nothing larger.  Circuits from SimpleGrid
8×8, TwoPackage 7×7 and some smaller ones are **unverified**: SharpSAT-TD's
count check did not finish in 30 minutes.  No check that finished disagreed.

## File types

The four grid benchmarks share one layout (each family's README lists it):

- **`*.pddl` — problems and domains.**  PDDL, made with FiFO's `ppgen.sh`.  Each
  problem opens with comment lines recording every `ppgen.sh` setting, so it can
  be regenerated exactly.  Its goal is the disjunction of the recognition
  hypotheses (ThreePackage: a conjunction of disjunctions, whose combinations
  are the hypotheses).
- **`goals/<goal>.pddl` — single-goal variants**: the problem with one
  hypothesis as its hard goal.
- **`*.answer` — plans**, as written by `planner.sh`: `SAT`, the cost as
  `(*OBJECTIVE* n)`, then the trajectory — `(HOLDS fluent t)` for what is true
  at time step `t`, and `(OCCURS action t)` for the action taken at step `t`.
- **`evidence/*.txt` — observations pinned to time steps**: one `(and ...)` of
  `(occurs action t)` literals (`<problem>-none.txt`: the empty `(and)`).  Use
  with `recognize.sh --evidence-kind fifo` or `planner.sh --evidence-file`.
  Each is a single form, which is what `recognize.sh` needs to negate it.
- **`recognition/<problem>.pddl` — the recognition problem**, with its
  recognition horizon in the header.
- **`scnf/`, `circuits/` — the evidence-free recognition theory** (FiFO's
  symbolic CNF) at that horizon, and its d4 circuit where d4 succeeded.  A pinned
  observation is a set of unit literals over the theory's atoms, so one theory
  and one circuit serve every evidence file of a problem.
- **`results/*.jsonl` — one JSON record per run**, appended as runs finish; a
  rerun supersedes the earlier record.  `scripts/summarize.py` turns them into
  `tables.md`.

`OldVersions/` (in git at ac6aa16) keeps the old conventions (also `-ordN.txt`
ordering evidence, and `wff/`/`wcnf/` copies of the theories); see the READMEs
there and
[OldVersions/make-fifo-files.py](https://github.com/HenryKautz/CLARA/blob/ac6aa16/OldVersions/make-fifo-files.py).
