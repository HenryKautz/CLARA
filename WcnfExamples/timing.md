# Timing of the marginal computations on SimpleGrid

What has been run so far on these problems, by method.  The SharpSAT-TD and
MC-SAT times are from the SimpleGrid plan-recognition sweep
(`../SimpleGrid/results/runs.jsonl`); the specialized method was timed on this
folder's examples (2026-10-17).

| Grid | Method | What each run computes | Runs | Time, this folder's example (s) | Mean (s) | Median (s) | Max (s) |
|---|---|---|--:|--:|--:|--:|--:|
| 3×3 | Specialized (walk DP) | exact, **all marginals**, without and with evidence | 3 | 0.025 | 0.024 | 0.025 | 0.025 |
| 4×4 | Specialized (walk DP) | exact, **all marginals**, without and with evidence | 3 | 0.026 | 0.026 | 0.026 | 0.026 |
| 5×5 | Specialized (walk DP) | exact, **all marginals**, without and with evidence | 3 | 0.030 | 0.029 | 0.030 | 0.030 |
| 6×6 | Specialized (walk DP) | exact, **all marginals**, without and with evidence | 3 | 0.035 | 0.035 | 0.035 | 0.036 |
| 7×7 | Specialized (walk DP) | exact, **all marginals**, without and with evidence | 3 | 0.042 | 0.042 | 0.042 | 0.043 |
| 3×3 | SharpSAT-TD | exact, **goal atoms at the final slice only** | 16 | 16.2 | 15.8 | 16.2 | 17.2 |
| 4×4 | SharpSAT-TD | exact, **goal atoms at the final slice only** | 36 | 19.7 | 20.0 | 20.2 | 20.8 |
| 5×5 | SharpSAT-TD | exact, **goal atoms at the final slice only** | 64 | 26.8 | 35.1 | 28.8 | 103.5 |
| 6×6 | SharpSAT-TD | exact, **goal atoms at the final slice only** | 100 | 37.3 | 37.6 | 37.5 | 44.2 |
| 3×3 | MC-SAT (WalkSAT) | approximate, **all marginals** sampled; only the goal atoms kept | 16 | 14.1 | 14.4 | 14.6 | 15.7 |
| 4×4 | MC-SAT (WalkSAT) | approximate, **all marginals** sampled; only the goal atoms kept | 36 | 32.8 | 32.9 | 32.9 | 34.0 |
| 5×5 | MC-SAT (WalkSAT) | approximate, **all marginals** sampled; only the goal atoms kept | 64 | 178.6 | 210.1 | 181.9 | 333.6 |
| 6×6 | MC-SAT (WalkSAT) | approximate, **all marginals** sampled; only the goal atoms kept | 100 | 360.3 | 349.2 | 356.5 | 406.2 |

## What the times measure

- **SharpSAT-TD and MC-SAT** times are whole `recognize.sh` runs: planning the
  horizon, grounding the theory, and then the inference, for one problem and one
  evidence file.  Each run does the inference twice, with and without the
  evidence (the recognition posterior divides one by the other).  SharpSAT-TD,
  asked for k goal atoms, makes k + 1 exact counts per theory — 2(k + 1) per run;
  it never computes the other variables' marginals.  MC-SAT makes one sampling
  run per theory (WalkSAT's default sample count) that estimates every
  variable's marginal at once, but recognize.sh keeps only the goal atoms'.
- For SharpSAT-TD and MC-SAT, **Runs** is every evidence file of that grid size
  (4 problems × each possible goal × each number of observations, 1 to N−1); the
  mean, median and maximum are over all of them, and every run finished.  "This folder's example" is the
  run on the same problem and the same 2-observation evidence as the files here.
- The runs went 8 at a time, wall-clock time, each limited to 1 minute (3×3,
  4×4; 5×5 SharpSAT-TD) or 15 minutes (6×6; 5×5 MC-SAT, and the 12 5×5
  SharpSAT-TD runs that exceeded a minute, rerun).
- The **specialized method** is `exact-marginals.py`: a forward/backward dynamic
  program over the truck's walks, specific to this domain, that gives every
  variable's exact marginal with and without the evidence in one run.  Its
  times are 3 runs per example (awake time, one at a time): the whole script,
  including starting Python (about 20 ms) and reading the map and weighted CNF,
  but not grounding the theory, which FiFO had already done.  So it is not
  comparable run for run with the recognize.sh times, which include planning and
  grounding; its point is that the exact answer itself is cheap here.
- No 7×7 runs of SharpSAT-TD or MC-SAT exist yet (they are part of the sweep
  now running).

## Approximate marginal files

Not available: the sweep recorded only each run's posterior over the goals and
deleted the rest of its output, so the full MC-SAT marginal estimates for these
problems were not kept.
