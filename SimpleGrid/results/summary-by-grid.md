## SimpleGrid plan recognition by grid size

| Grid size | Goals | Observations | Mean CNF variables | Mean CNF clauses | max-term<br>Mean time (s) | max-term<br>Among top | max-term<br>Is top | sharpsat-td<br>Mean time (s) | sharpsat-td<br>Among top | sharpsat-td<br>Is top | mc-sat<br>Mean time (s) | mc-sat<br>Among top | mc-sat<br>Is top |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3×3 | 2 | 1–2 | 141 | 820 | 11.9 | 16/16 | 0/16 | 15.8 | 9/16 | 7/16 | 14.4 | 8/16 | 8/16 |
| 4×4 | 3 | 1–3 | 400 | 2,611 | 16.0 | 36/36 | 0/36 | 20.0 | 20/36 | 8/36 | 32.9 | 15/36 | 15/36 |
| 5×5 | 4 | 1–4 | 812 | 5,624 | 35.0 | 64/64 | 0/64 | 35.1 | 24/64 | 14/64 | 210.1 | 16/64 | 16/64 |

Fully connected grids with 1 truck and multiple possible goal destinations.
"Among top": the runs in which the true goal has the highest posterior, tied or
alone. "Is top": the runs in which the true goal alone has the highest
posterior.
