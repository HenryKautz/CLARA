## SimpleGrid plan recognition by grid size

| Grid size | 3×3 | 4×4 | 5×5 |
|:--|--:|--:|--:|
| Goals | 2 | 3 | 4 |
| Observations | 1–2 | 1–3 | 1–4 |
| Mean CNF variables | 141 | 400 | 812 |
| Mean CNF clauses | 820 | 2,611 | 5,624 |
| max-term: Mean time (s) | 11.9 | 16.0 | 35.0 |
| max-term: Among top | 16/16 | 36/36 | 64/64 |
| max-term: Is top | 0/16 | 0/36 | 0/64 |
| sharpsat-td: Mean time (s) | 15.8 | 20.0 | 35.1 |
| sharpsat-td: Among top | 9/16 | 20/36 | 24/64 |
| sharpsat-td: Is top | 7/16 | 8/36 | 14/64 |
| mc-sat: Mean time (s) | 14.4 | 32.9 | 210.1 |
| mc-sat: Among top | 8/16 | 15/36 | 16/64 |
| mc-sat: Is top | 8/16 | 15/36 | 16/64 |

Fully connected grids with 1 truck and multiple possible goal destinations.
"Among top": the runs in which the true goal has the highest posterior, tied or
alone. "Is top": the runs in which the true goal alone has the highest
posterior.
