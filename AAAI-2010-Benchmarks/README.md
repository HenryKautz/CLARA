# Ramírez & Geffner Plan-Recognition Benchmarks

Two problems from the classic Ramírez & Geffner plan-recognition benchmarks
(AAAI-10), each in two versions:

- the dataset's original form;
- the recognition instance generated from it for FiFO.

These are copies of FiFO's `SatPlan/Examples/Plan_Recognition/`, with the same
directory names. That directory's README, FiFO's `benchmarks.md` and
`discussion.md` are the sources for what follows.

## Where they come from

The problems are taken from the PUCRS goal-plan-recognition dataset
(<https://github.com/pucrs-automated-planning/goal-plan-recognition-dataset>,
curated by Pereira, Oren & Meneguzzi for AAAI-17). That dataset preserves the six
original R&G domains as its `*-aaai` problems, alongside nine newer ones.

| Directory | Source | What it is |
|---|---|---|
| `BlockWords/` | dataset `blocks-world/block-words-aaai_p01` | Eight letter-labeled blocks. There are 21 candidate goals, each stacking a tower that spells an English word. The hidden goal spells **CORE** (`hyp16` in generation order; `hyp0` is DRAW). |
| `IntrusionDetection/` | dataset `intrusion-detection/intrusion-detection-aaai_p10`, unmodified | An attacker does recon on ten hosts, then gathers information, vandalizes or steals data. There are 10 candidate goals, each an attacker objective over a subset of the hosts. The hidden goal is *information gathered on all ten hosts* (`hyp0`). |
| `BlocksWorldCosts/` | generated from `BlockWords/` | The full recognition instance; see below. |
| `IntrusionDetectionCosts/` | generated from `IntrusionDetection/` | The full recognition instance; see below. |

The one change to an original is in BlockWords. FiFO has no `=`, so the domain
drops the `(not (= ?x ?y))` guards on stack/unstack. In the 4-operator blocks
world they are redundant (see the comment in `block-words.pddl`).

## The original problems

`BlockWords/` and `IntrusionDetection/` keep the instance in the dataset's own
format, plus a concrete planning problem derived from it:

| File | Contents |
|---|---|
| `template.pddl` | the initial state, with the goal left as a `<HYPOTHESIS>` placeholder |
| `hyps.dat` | the candidate goals, one comma-separated conjunction per line |
| `real_hyp.dat` | the hidden true goal (one line of `hyps.dat`) |
| `obs.dat` | the observed action sequence, in order (100% observability) |
| `evidence-partial.txt` | a 50%-observability slice of `obs.dat`, as one `occur-in-order` form |
| `pb1.pddl` | `template.pddl` with the hidden goal substituted in |
| `pb1.answer` | the plan FiFO's `planner.sh` found for `pb1.pddl` |
| `intermediates/pb1.wff` | the pddl2fifo translation (regression-checked by FiFO's `tests/run-test-pddl.sh`) |

The `pb1` problems pin down a single hypothesis and solve for feasibility only:

- **BlockWords** is inherently sequential (one hand). Its plan takes 10 actions, so
  pass `--maxslices 12`.
- **IntrusionDetection** parallelizes over independent hosts and solves at 3
  slices.

Neither original has action costs, so a SAT solver is free to include
superfluous actions.

## The generated recognition instances

A genuine recognition instance keeps *all* the hypotheses and asks for the
posterior over them given the observations. FiFO's
`SatPlan/Examples/Plan_Recognition/make-recognition-instance.lisp` builds one
from a dataset problem, with these changes:

1. **Uniform action costs.** Every action gets `(increase (total-cost) 1)`, so
   plan cost = plan length. The distribution over trajectories is then the
   Boltzmann model `P(plan) ∝ exp(−β·length)` that Ramírez & Geffner assume,
   with `β = cost / scale` (the scnf weight scale, default 1). Without costs,
   every trajectory consistent with the evidence weighs the same and the
   posterior is a mere volume count.
2. **A disjunctive goal over derived predicates.** Each hypothesis becomes a
   nullary derived predicate `hypI`, equal to the conjunction of its goal
   literals. The goal is `(or (hyp0) … (hypN))`, so one theory ranges over every
   hypothesis, and each hypothesis is a single atom `(HOLDS (hypI) numslices)`.
3. **Ordered, incremental evidence.** `evidence-K.txt` (K = 1…5) holds the first
   K observations of `evidence-partial.txt` as an `occur-in-order` form. That is
   partial observability: the order is known, the times are not.

Each generated directory holds:

- `<domain>-costs.pddl` (the domain, with costs and the `hypI` derived predicates);
- `problem.pddl` (the disjunctive goal);
- `evidence-1.txt` … `evidence-5.txt`;
- `runs/` (the results below).

To regenerate one, from FiFO's `SatPlan/Examples/Plan_Recognition`:

```sh
sbcl --script make-recognition-instance.lisp \
     BlockWords/block-words.pddl BlockWords/template.pddl \
     BlockWords/hyps.dat BlockWords/evidence-partial.txt \
     BlocksWorldCosts            # optional 6th argument: the uniform cost (default 1)
```

**Horizon.** No hypothesis should be eliminated by the horizon alone. So the
shared horizon H is the *maximum*, over hypotheses, of each single-hypothesis
goal's minimum feasible horizon:

- **IntrusionDetection: H = 6.**
- **BlockWords: H = 15** (`hyp15` needs 15 slices).

The per-hypothesis sweep is in `runs/horizons/`. A k-observation sequence also
needs at least k+1 slices, and a disjunctive goal does not raise the
reachability lower bound, so always set `--numslices`/`--minslices` explicitly.

## Results recorded in FiFO

### MAP is the cheapest explanation, not the most likely one

The MAP plan is the single lowest-cost plan that embeds the observations in
order and satisfies some hypothesis. It is found by weighted MaxSAT at H.
"Recognized" is the hypothesis holding at that plan's final slice. Results are in
`runs/map/`.

| Domain | Observations | H | Vars | Clauses | Time | MAP cost | Recognized | True |
|---|--:|--:|--:|--:|--:|--:|:--:|:--:|
| IntrusionDetection | 1 | 6  | 1 056 | 2 240   | 3.3 s | 14 | hyp3  | hyp0  |
| IntrusionDetection | 3 | 6  | 1 068 | 2 282   | 3.9 s | 16 | hyp3  | hyp0  |
| IntrusionDetection | 5 | 6  | 1 080 | 2 324   | 2.2 s | 18 | hyp2  | hyp0  |
| BlockWords         | 1 | 15 | 3 681 | 240 552 | 8.4 s | 4  | hyp5  | hyp16 |
| BlockWords         | 3 | 15 | 3 711 | 240 666 | 9.1 s | 7  | hyp5  | hyp16 |
| BlockWords         | 5 | 15 | 3 741 | 240 780 | 9.7 s | 10 | **hyp16** | hyp16 |

MAP is wrong in five of the six rows. This is MAP's cost bias, not an encoding
defect: it recognizes the cheapest-to-reach hypothesis.

- **BlockWords** flips to the true CORE at 5 observations. By then the prefix
  contains `stack R E`, a CORE move but not a move of the cheaper decoy CROW.
- **IntrusionDetection** never recovers `hyp0`. The observed recons are the first
  step of every attack, and the true goal (all ten hosts) is the most expensive
  hypothesis.

Raw marginals over the disjunctive theory would be worse, not better.
`P(G | O) ∝ Z_{G,O}` favors goals with more and cheaper trajectories. That is,
it builds in a prior proportional to each goal's own weighted count `Z_G`. FiFO's
`discussion.md`, "Goal Posteriors and the Per-Goal Normalization (Z_G) Issue",
discusses this. Exact counting also timed out at these horizons (ADDMC, 240 s
cap).

### Ramírez & Geffner's normalized posterior

FiFO's `recognize.sh` computes R&G's tractable approximation to `Z_{G,O}/Z_G`.
For each hypothesis it finds the cheapest plan that complies with the
observations and the cheapest that does not, then computes

`Δ_I = c(¬O) − c(O)`, `P(O | hypI) = σ(β·Δ_I)`, `P(hypI | O) ∝ π_I · σ(β·Δ_I)`.

The results below use uniform priors, β = 1 and the same H as above. Results are
in `runs/recognize/`.

| Domain | Observations | H | 2n MaxSAT runs | Wall-clock | Recognized (posterior) | True-goal posterior |
|---|--:|--:|--:|--:|:--|--:|
| IntrusionDetection | 1 | 6  | 20 | ≈ 1 m 53 s | hyp0 — 5-way tie (0.16) | 0.16 (tied 1st) |
| IntrusionDetection | 3 | 6  | 20 | 1 m 53 s   | **hyp0** (0.37) | 0.37 (1st) |
| IntrusionDetection | 5 | 6  | 20 | ≈ 1 m 53 s | **hyp0** (0.67) | 0.67 (1st) |
| BlockWords | 1 | 15 | 42 | ≈ 6.7 min | (large tie, 0.05) | 0.05 (tied) |
| BlockWords | 3 | 15 | 42 | ≈ 6.7 min | hyp10 (0.21) | 0.12 (2nd) |
| BlockWords | 5 | 15 | 42 | ≈ 6.7 min | **hyp16** — tie w/ hyp15 (0.31) | 0.31 (tied 1st) |

The normalization recovers what MAP could not:

- **IntrusionDetection** puts `hyp0` at or above every rival and sharpens it from
  a 5-way tie to 0.67. Reconning a host is on the optimal path for the all-hosts
  goal (Δ = 0) but wasteful for a targeted attack (Δ < 0).
- **BlockWords** moves the true `hyp16` from a large tie to 2nd, then to tied
  first with `hyp15`, the word sharing the observed prefix.

These timings come from FiFO's older `recognize.sh`, which ran `planner.sh` 2n
times. The current one instantiates once and clamps the 2n solves, taking
4.1 s on IntrusionDetectionCosts at H = 6. Its summary tables are identical to
the old method's.

## Exact posteriors: SharpSAT-TD and d4 knowledge compilation (2026-10-19)

The tables above come from MaxSAT: max-term, i.e. R&G's `c(¬O) − c(O)`, keeps only
each partition function's dominant (cheapest-plan) term. This section computes
the same per-hypothesis posterior **exactly**, by weighted model counting over
every plan at the horizon:

`P(hypI | O) ∝ π_I · P(hypI | T, O) / P(hypI | T)`, with uniform priors π.

That posterior was measured three ways:

- **max-term**: `recognize.sh --counter max-term`, the exact MaxSAT solver rc2.
  It reproduces the R&G table above number for number, but runs in seconds
  instead of minutes, because the current `recognize.sh` instantiates once and
  clamps the 2n solves.
- **sharpsat-td**: `recognize.sh --counter sharpsat-td`. The posterior is formed
  from 2(1 + n) exact weighted model counts.
- **d4**: knowledge compilation. `marginals.sh --solver d4 --save-circuit`
  compiles each theory **once** into a d-DNNF circuit. P(h | T) is read from the
  circuit, and P(h | T, O) comes from the same circuit with the observation
  literal clamped (no recompilation). The posterior is formed exactly as for
  sharpsat-td.

  d4 was run twice per theory: on the full theory, and with `--project`. The
  projected compile keeps only the actions, the final-slice goal atoms (the
  hypotheses among them), the weighted atoms and the observation atom. A SAT
  check first proves that these atoms determine all the others, which makes
  the projected marginals exactly the full ones.

The horizons are the benchmarks' own, H = 6 and H = 15. Every run had a
**60-minute limit**, enforced on its whole process tree; the solvers inside got
the same `--timeout`. Everything was run by `run-benchmarks.py`, which records
each run in `results/runs.jsonl`. The tables are printed by `summarize.py`.

### What is saved here

For each instance and evidence prefix, NAME = `<instance>-obsK` (K = 1, 3, 5),
plus `IntrusionDetectionCosts-obs3-H5`, the H = 5 cross-check theory:

- `wff/NAME.wff`: the FiFO source. It is pddl2fifo's translation of the
  problem, as `recognize.sh` normalized it, with the observation monitor's
  axioms for `evidence-K.txt` appended as a FiFO formula. It sets its own
  horizon and includes `wff/satplan.wff`, a copy of FiFO's SatPlan axioms, so
  instantiating it alone gives the clauses of `scnf/NAME.scnf`. They are the
  same clauses but in another order: the planner appends the axioms after the
  problem's clauses.
- `scnf/NAME.scnf`: the instantiated (symbolic) theory, with the monitor axioms
  folded in; this is what the runs used. `scnf/NAME-assertion.txt` holds the
  one literal to condition on.
- `wcnf/NAME-2020.wcnf`, `wcnf/NAME-2024.wcnf`: the weighted CNF in the MCC 2020
  dialect (ADDMC) and the MCC 2024 dialect (SharpSAT-TD).
  `wcnf/NAME-ev-2020.wcnf` and `wcnf/NAME-ev-2024.wcnf` are the same with the
  literal added as a unit clause. `wcnf/NAME.map` maps each DIMACS variable to
  its FiFO atom, and is the same for all four.
- `circuits/`: the saved d-DNNF circuits. **No compile finished at the benchmark
  horizons**, full or projected (see Results), so there is no circuit for
  them. The one circuit here is for the cross-check at H = 5 described below:
  `IntrusionDetectionCosts-obs3-H5.dnnf`, compiled in 55 s, 60 MB as text. Its
  theory is `scnf/IntrusionDetectionCosts-obs3-H5.scnf`, and
  `query-h5-circuit.lisp` reproduces that posterior from it without
  recompiling.

`../make-fifo-files.py` writes `wff/`, `scnf/` and `wcnf/`. It regenerates each
theory with `recognize.sh --stop-after scnf` and requires it to be
byte-identical to the one the runs used. (Until 2026-10-20 the theories and
their weighted CNFs were in `theories/`, in the 2024 dialect only.)

### Theory sizes

| Theory | H | Variables | Clauses |
|---|--:|--:|--:|
| IntrusionDetectionCosts-obs1 | 6 | 1,056 | 2,239 |
| IntrusionDetectionCosts-obs3 | 6 | 1,068 | 2,281 |
| IntrusionDetectionCosts-obs5 | 6 | 1,080 | 2,323 |
| BlocksWorldCosts-obs1 | 15 | 3,681 | 240,551 |
| BlocksWorldCosts-obs3 | 15 | 3,711 | 240,665 |
| BlocksWorldCosts-obs5 | 15 | 3,741 | 240,779 |

### Results

| Instance | Obs. | Method | Status | Time | Recognized (posterior) | True goal: posterior, rank |
|---|--:|---|---|--:|---|---|
| IntrusionDetectionCosts | 1 | max-term | ok | 7.7 s | 5-way tie incl. hyp0, hyp1, hyp2… (0.158) | 0.158, 1 (tied ×5) |
| IntrusionDetectionCosts | 1 | sharpsat-td | ok | 41.7 s | 5-way tie incl. hyp0, hyp1, hyp2… (0.100) | 0.100, 1 (tied ×5) |
| IntrusionDetectionCosts | 1 | d4 | timeout (1.00 h limit) | 1.00 h | – | – |
| IntrusionDetectionCosts | 1 | d4-project | timeout (1.00 h limit) | 1.00 h | – | – |
| IntrusionDetectionCosts | 1 | mc-sat | ok | 3.8 min | hyp6 (0.931) | 0.029, 3 |
| IntrusionDetectionCosts | 3 | max-term | ok | 9.8 s | hyp0 (0.367) | 0.367, 1 |
| IntrusionDetectionCosts | 3 | sharpsat-td | ok | 1.6 min | hyp1 (0.108) | 0.101, 3 |
| IntrusionDetectionCosts | 3 | d4 | timeout (1.00 h limit) | 1.00 h | – | – |
| IntrusionDetectionCosts | 3 | d4-project | timeout (1.00 h limit) | 1.01 h | – | – |
| IntrusionDetectionCosts | 3 | ddnnf | timeout (1.00 h limit) | 1.00 h | – | – |
| IntrusionDetectionCosts | 3 | mc-sat | did not mix | 3.6 min | – | – |
| IntrusionDetectionCosts | 5 | max-term | ok | 9.8 s | hyp0 (0.666) | 0.666, 1 |
| IntrusionDetectionCosts | 5 | sharpsat-td | ok | 48.8 s | hyp1 (0.117) | 0.101, 3 |
| IntrusionDetectionCosts | 5 | d4 | timeout (1.00 h limit) | 1.00 h | – | – |
| IntrusionDetectionCosts | 5 | d4-project | timeout (1.00 h limit) | 1.00 h | – | – |
| IntrusionDetectionCosts | 5 | mc-sat | did not mix | 3.7 min | – | – |
| BlocksWorldCosts | 1 | max-term | ok | 48.7 s | 19-way tie incl. hyp0, hyp1, hyp2… (0.051) | 0.051, 1 (tied ×19) |
| BlocksWorldCosts | 1 | sharpsat-td | timeout (1.00 h limit) | 1.03 h | – | – |
| BlocksWorldCosts | 1 | d4 | timeout (1.00 h limit) | 1.00 h | – | – |
| BlocksWorldCosts | 1 | d4-project | timeout (1.00 h limit) | 1.02 h | – | – |
| BlocksWorldCosts | 3 | max-term | ok | 1.0 min | hyp10 (0.212) | 0.120, 2 (tied ×2) |
| BlocksWorldCosts | 3 | sharpsat-td | timeout (1.00 h limit) | 1.03 h | – | – |
| BlocksWorldCosts | 3 | d4 | timeout (1.00 h limit) | 1.00 h | – | – |
| BlocksWorldCosts | 3 | d4-project | timeout (1.00 h limit) | 1.01 h | – | – |
| BlocksWorldCosts | 5 | max-term | ok | 1.0 min | 2-way tie incl. hyp15, hyp16 (0.314) | 0.314, 1 (tied ×2) |
| BlocksWorldCosts | 5 | sharpsat-td | ok | 56.6 min | hyp16 (0.644) | 0.644, 1 |
| BlocksWorldCosts | 5 | d4 | timeout (1.00 h limit) | 1.01 h | – | – |
| BlocksWorldCosts | 5 | d4-project | timeout (1.00 h limit) | 1.02 h | – | – |

The *Time* column is the run's wall clock: for sharpsat-td and max-term the whole `recognize.sh` run, for d4 the compile (plus the queries had it finished). *Recognized* is the argmax, ties kept. `mc-sat` and `ddnnf` were run as cross-checks on IntrusionDetectionCosts only (see Checks below). A 5-way tie at 0.100 for sharpsat-td with 1 observation is a near-uniform posterior (0.0997–0.1003), not a decisive one.

**d4 compilation.** All twelve compiles, full and projected, hit the 60-minute limit. The projection was proved exact in each case and kept 461 of about 1,060 atoms on IntrusionDetectionCosts and 2,038 of about 3,700 on BlocksWorldCosts, but that was not enough. So there are no load or query times to report at the benchmark horizons. On the H = 5 cross-check theory, compiling took 55 s. Loading the saved binary circuit took 0.35 s, and the two queries took 0.8 s (no evidence) and 0.6 s (evidence clamped).

### Reading the results

**Where the exact methods finished.**
SharpSAT-TD counts IntrusionDetection at H = 6 in under two minutes per
evidence set. FiFO's `benchmarks.md` had recorded every weighted model count
timing out there (ADDMC, 240 s cap). On BlockWords at H = 15 SharpSAT-TD
finished only with 5 observations (57 min), presumably because the longest
prefix constrains the plans the most.
d4 compiled nothing at the benchmark horizons in an hour, full or projected,
and neither did FiFO's own d-DNNF compiler (IntrusionDetectionCosts obs3, given
a 48 GB heap and a 100 M-node limit). Knowledge compilation pays when one
circuit serves many queries. It cannot pay here, where the circuit cannot be
built at all.

**The exact posterior is not max-term's, and the difference is the point.**

- **IntrusionDetection, H = 6: the exact posterior is nearly uniform.** Every
  hypothesis gets 0.092–0.117. The argmax is `hyp1` or a near-uniform tie, and
  the true `hyp0` ranks 3rd, at 0.101, with 3 and 5 observations alike.
  max-term ranks `hyp0` first and sharpens it to 0.67.

  Both are right about different models. max-term sees only the cheapest plan,
  in which reconning the observed hosts is free for the all-hosts goal and
  wasteful for every other goal. The exact count sums over *every* plan at
  H = 6, and Intrusion's actions are parallel and cheap to pad. Among all plans
  weighted by `exp(−length)`, a run of three recons is about as likely under
  every goal, so the evidence barely moves the posterior.

  At H = 5, one slice tighter, the exact posterior already concentrates on
  three goals (cross-check below). At H = 4 the evidence leaves only `hyp0`. The
  exact answer depends on the slack the horizon allows, which is the Z_G effect
  discussed in FiFO's `discussion.md`.
- **BlockWords, H = 15, 5 observations: exact counting is sharper than max-term.**
  It puts 0.644 on the true `hyp16` (CORE) and 0.268 on `hyp15`. max-term ties
  the two at 0.314. BlockWords is sequential, with one hand, so padding is
  constrained. Summing over all plans then separates the two words that share
  the observed prefix, where the single cheapest plan cannot.

**Checks.** The two exact methods share no counting code, so where both finish,
each checks the other. At the benchmark horizons they never both finished. So
they were compared on IntrusionDetectionCosts obs3 at H = 5, where d4 compiles
in under a minute (`results/crosscheck-intrusion-obs3-h5.txt`). They agree to
the six digits printed on a non-trivial posterior: `hyp0` 0.3576, `hyp2` 0.3284,
`hyp6` 0.3140, the rest 0. At H = 4 they also agree, but vacuously (1 against 0).

MC-SAT was tried as an approximate third opinion and **does not mix** on these
theories. For 3 and 5 observations FiFO refuses the result, because some
hypothesis was sampled under the evidence but never without it. The one run it
accepted (1 observation) puts 0.93 on `hyp6`, the mark of a stuck chain.

**Bugs found and fixed along the way:**

- **SharpSAT-TD (fork 3c027a5).** flowcutter, stopped before its first
  decomposition, wrote its "no decomposition" message with a trailing NUL byte.
  sharpSAT parsed that byte as a line with `std::stoi` and aborted. Every
  BlockWords count failed this way: its 2,520-vertex primal graph gets no
  decomposition within the default 1 s, and with 30 s flowcutter finds only
  width 1,179.
- **FiFO (3cc3461).** On the `--hypotheses` path, `--node-limit` never reached
  the ddnnf and d4 back ends.

## Running (FiFO installed, scripts on PATH)

From this directory:

```sh
# MAP: the cheapest plan over all hypotheses that embeds 5 observations in order
planner.sh BlocksWorldCosts/problem.pddl --domain BlocksWorldCosts/block-words-costs.pddl \
    --minslices 9 --maxslices 12 --pddl-evidence-file BlocksWorldCosts/evidence-5.txt

# Exact marginals with the d4 compiler (about 5 s; sharpsat-td about 1 min; ADDMC
# cannot finish one count in 10 min)
planner.sh IntrusionDetectionCosts/problem.pddl \
    --domain IntrusionDetectionCosts/intrusion-detection-costs.pddl \
    --numslices 4 --marginals --counter d4 \
    --pddl-evidence-file IntrusionDetectionCosts/evidence-3.txt

# Ramírez & Geffner posterior
recognize.sh IntrusionDetectionCosts/intrusion-detection-costs.pddl \
    IntrusionDetectionCosts/problem.pddl IntrusionDetectionCosts/evidence-3.txt --horizon 6

# The exact-posterior sweep of the section above (resumes from results/runs.jsonl;
# --methods, --obs, --limit, --jobs, --match select what runs), then its tables
python3 run-benchmarks.py --limit 3600 --jobs 4
python3 summarize.py
```

## References

- M. Ramírez & H. Geffner (2010). Probabilistic plan recognition using
  off-the-shelf classical planners. *AAAI-10*, 1121–1126. (The `*-aaai` problems;
  the Boltzmann plan model and the `c(G,O) − c(G,¬O)` baseline.)
- R. F. Pereira, N. Oren & F. Meneguzzi (2017). Landmark-based heuristics for
  goal recognition. *AAAI-17*. (The curated dataset.)
