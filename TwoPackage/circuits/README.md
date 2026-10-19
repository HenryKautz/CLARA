# Compiled circuits

`gridNxN-k.scnf` is the ground FiFO theory and `gridNxN-k.dnnf` the d4 circuit
compiled from it (projected, no evidence) by `../compile-d4.py`; results are in
`../results/compile-d4.jsonl` and `../sweep.log`.  `grid7x7-1` and `grid7x7-4`
have a theory but no circuit: d4 did not finish within 1200 s.

Circuits over GitHub's 100 MB limit (`grid6x6-1`, `grid6x6-3`, `grid7x7-2`,
150–300 MB each) are committed as 90 MB pieces made with `split -b 90m`, and the
whole files are git-ignored.  To rebuild one:

```sh
cat grid6x6-1.dnnf.part-* > grid6x6-1.dnnf
```

## Verification

d4 can return a wrong circuit without any error, so each circuit was checked in
one of two ways:

- **count** — the circuit's model count equals sharpSAT's exact count of the
  CNF given to d4 (check limit 120 s), or, by `../verify-count.py`, of the
  theory itself with a limit of hours (`../results/verify-count.jsonl`).  The
  two are the same count: the projection is exact, so each projected model
  extends to exactly one model of the theory.
- **oracle** — evidence-query marginals from the circuit match `marginals.sh
  --solver sharpsat-td` on the theory, to within 2.1e-15
  (`../results/query-evidence.jsonl`).

| Circuit | Checked by |
|---|---|
| grid3x3-1 … grid3x3-4 | count |
| grid4x4-1 | oracle (count check timed out) |
| grid4x4-2, grid4x4-3, grid4x4-4 | count |
| grid5x5-1, grid5x5-2, grid5x5-3 | count |
| grid5x5-4 | oracle (count check timed out) |
| grid6x6-1, grid6x6-2, grid6x6-4 | count |
| grid6x6-3 | count, by verify-count.py: 25,217,036 models (sharpSAT 58 min) |
| grid7x7-2 | count, by verify-count.py: 20,152,168 models (sharpSAT 70 min) |
| grid7x7-3 | count |

grid6x6-3 and grid7x7-2 were unverified until 2026-10-19, when
`verify-count.py` (4-hour limit) confirmed both.  Every circuit here is now
checked.
