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
```

## References

- M. Ramírez & H. Geffner (2010). Probabilistic plan recognition using
  off-the-shelf classical planners. *AAAI-10*, 1121–1126. (The `*-aaai` problems;
  the Boltzmann plan model and the `c(G,O) − c(G,¬O)` baseline.)
- R. F. Pereira, N. Oren & F. Meneguzzi (2017). Landmark-based heuristics for
  goal recognition. *AAAI-17*. (The curated dataset.)
