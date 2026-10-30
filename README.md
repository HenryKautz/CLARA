Files for UVA DARPA CLARA: plan-recognition benchmarks, made and solved with
[FiFO](https://github.com/HenryKautz/FiFO).

## Contents

Each benchmark directory has its own README, describing its problems, how they
were made, and its results.

| Directory | What it holds | README |
|---|---|---|
| `SimpleGrid/` | One truck on an N×N grid (3×3–10×10) heading for one of several destinations. | [SimpleGrid/README.md](SimpleGrid/README.md) |
| `TwoPackage/` | One truck, two packages with two destinations each, 3×3–7×7; four hypotheses.  Recognition by max-term, SharpSAT-TD, MC-SAT and d4. | [TwoPackage/README.md](TwoPackage/README.md) |
| `ThreePackage/` | One truck, three packages with two destinations each, all to be delivered, 5×5–7×7 with 20% of the roads knocked out; eight hypotheses (destination combinations).  Planning at every size; recognition and d4 stop at 5×5. | [ThreePackage/README.md](ThreePackage/README.md) |
| `FourPackage/` | Two trucks, four packages with three destinations each, 6×6–15×15 with 40% of the roads knocked out; twelve hypotheses, preferences.  Planning at every size; recognition mostly not run (too slow). | [FourPackage/README.md](FourPackage/README.md) |
| `RestrictedPlanning/` | Not a benchmark: FiFO's experimental `planner.sh --restrict` (cost minimization over the SAT plan's actions only) against EvalMaxSAT on the whole theory, on the SimpleGrid, TwoPackage and ThreePackage goals. | [RestrictedPlanning/README.md](RestrictedPlanning/README.md) |
| `AAAI-2010-Benchmarks/` | Ramírez & Geffner's BlockWords and IntrusionDetection, original and as recognition instances, with exact posteriors. | [AAAI-2010-Benchmarks/README.md](AAAI-2010-Benchmarks/README.md) |

At the top level:

```
make-fifo-files.py     writes the wff/, scnf/ and wcnf/ files of SimpleGrid,
                       TwoPackage and AAAI-2010-Benchmarks (see below)
make-fifo-files.lisp   its Lisp half
```

## File types

The grid benchmarks share one set of conventions; a directory's README says
where it departs from them.

- **`*.pddl` — problems and domains.**  PDDL, made with FiFO's `ppgen.sh`.  Each
  generated problem opens with comment lines recording every `ppgen.sh` setting,
  so it can be regenerated exactly.  The goal is a disjunction of literals;
  those literals are the recognition hypotheses.
- **`goals/<problem>-<goal>.pddl` — single-goal variants.**  The problem with
  its goal narrowed to one hypothesis.
- **`*.answer` — plans**, as written by `planner.sh`: `SAT`, the cost as
  `(*OBJECTIVE* n)`, then the trajectory — `(HOLDS fluent t)` for what is true
  at time step `t`, and `(OCCURS action t)` for the action taken at step `t`.
- **`evidence/*-obsN.txt` — observations pinned to time steps**: one
  `(and ...)` of `(occurs action t)` literals, the plan's first N actions.  Use
  with `recognize.sh --evidence-kind fifo` or `planner.sh --evidence-file`.
- **`evidence/*-ordN.txt` — the same observations as an ordering only**: one
  `(occur-in-order a1 ... aN)`, the Ramírez & Geffner observation model.  Use
  with `recognize.sh` (its default `--evidence-kind pddl`) or
  `planner.sh --pddl-evidence-file`.

  Each evidence file is a single form, which is what `recognize.sh` needs to
  negate it, and opens with the `evgen.sh` settings that made it.  The true goal
  is the one in the file name.
- **`wff/`, `scnf/`, `wcnf/` — the recognition theory** in FiFO source,
  instantiated, and as weighted CNF; see the next section.
- **`circuits/` — d4 circuits** of the theories, with a README on how each was
  checked.
- **`results/*.jsonl` — one JSON record per run**, appended as runs finish; a
  rerun supersedes the earlier record.  Each directory's `summarize.py`
  (SimpleGrid: `make-tables.py`) turns them into tables.

## FiFO files and weighted CNF

Every benchmark directory holds, for each problem:

- **`wff/P.wff`: the FiFO source.** It is the SatPlan encoding `pddl2fifo`
  produced for the recognition problem, i.e. the problem as `recognize.sh`
  normalizes it, with the goal's disjuncts as hypotheses. It is
  self-contained:
  - it sets its own horizon, `(option *satplan-numslices* H)`;
  - it includes `wff/satplan.wff`, a copy of FiFO's SatPlan axioms.

  So `(instantiate "P.wff")` alone gives the clauses of `scnf/P.scnf`.
- **`scnf/P.scnf`: the instantiated theory** (FiFO's symbolic CNF) that every
  experiment used. For SimpleGrid and TwoPackage it is evidence-free:
  observations pinned to time steps (`evidence/*-obsN.txt`) are unit literals
  over its atoms. For the AAAI-2010 benchmarks, each evidence prefix has its own
  theory, with the ordering evidence's monitor axioms folded in.
- **`wcnf/P-2020.wcnf` and `wcnf/P-2024.wcnf`: its weighted CNF**, in the MCC
  2020 dialect (ADDMC) and the MCC 2024 dialect (SharpSAT-TD); the two are not
  interchangeable. `wcnf/P.map` maps each variable number to its FiFO atom.

The WCNFs are written by FiFO's own writer.

FourPackage differs: its theories are too large for git, so it keeps only
`wff/`.  Sizes 12..15 include `wff/satplan-mutex.wff`, the axioms with the
linear mutex encoding.  Its own `scripts/make-formats.py` writes `wcnf/`.  See
[FourPackage/README.md](FourPackage/README.md).

`python3 make-fifo-files.py [--match REGEX] [--jobs N]` regenerates all three
for SimpleGrid, TwoPackage and AAAI-2010-Benchmarks from the problems (FiFO
installed). Nothing is solved. Each theory is rebuilt with `recognize.sh
--stop-after scnf` at the problem's horizon, as the experiments built it, and
must be byte-identical to the archived one; each `.wff` must instantiate to the
same clauses.

On 2026-10-20 all 59 problems passed both checks:

- 32 SimpleGrid problems;
- 20 TwoPackage problems;
- 7 AAAI-2010 theories, whose clauses come out in another order, since the
  planner appends the monitor axioms last.

The theories used to live in `circuits/` (SimpleGrid, TwoPackage) and
`theories/` (AAAI-2010). The seven solved SimpleGrid WCNF examples were the
top-level `WcnfExamples/` directory; they are now in `SimpleGrid/wcnf/`.
