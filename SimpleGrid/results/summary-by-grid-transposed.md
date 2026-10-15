## SimpleGrid plan recognition by grid size and observations

| Grid size | 3×3 | 3×3 | 4×4 | 4×4 | 4×4 | 5×5 | 5×5 | 5×5 | 5×5 |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Observations | 1 | 2 | 1 | 2 | 3 | 1 | 2 | 3 | 4 |
| Goals | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 4 |
| Min goal distance | 3 | 3 | 5 | 5 | 5 | 6 | 6 | 6 | 6 |
| Mean CNF variables | 141 | 141 | 400 | 400 | 400 | 812 | 812 | 812 | 812 |
| Mean CNF clauses | 819 | 820 | 2,610 | 2,611 | 2,612 | 5,622 | 5,623 | 5,624 | 5,625 |
| max-term: Mean time (s) | 11.7 | 12.1 | 16.2 | 16.2 | 15.8 | 25.6 | 34.4 | 43.9 | 36.1 |
| max-term: Among top | 8/8 | 8/8 | 12/12 | 12/12 | 12/12 | 16/16 | 16/16 | 16/16 | 16/16 |
| max-term: Is top | 0/8 | 0/8 | 0/12 | 0/12 | 0/12 | 0/16 | 0/16 | 0/16 | 0/16 |
| sharpsat-td: Mean time (s) | 15.7 | 16.0 | 20.1 | 20.1 | 19.8 | 35.0 | 36.0 | 35.0 | 34.6 |
| sharpsat-td: Among top | 5/8 | 4/8 | 8/12 | 8/12 | 4/12 | 6/16 | 7/16 | 7/16 | 4/16 |
| sharpsat-td: Is top | 3/8 | 4/8 | 0/12 | 4/12 | 4/12 | 2/16 | 3/16 | 5/16 | 4/16 |
| mc-sat: Mean time (s) | 14.6 | 14.2 | 33.4 | 32.9 | 32.3 | 219.4 | 213.4 | 207.4 | 200.1 |
| mc-sat: Among top | 4/8 | 4/8 | 6/12 | 4/12 | 5/12 | 6/16 | 2/16 | 3/16 | 5/16 |
| mc-sat: Is top | 4/8 | 4/8 | 6/12 | 4/12 | 5/12 | 6/16 | 2/16 | 3/16 | 5/16 |

Fully connected grids with 1 truck and multiple possible goal destinations.
"Among top": the runs in which the true goal has the highest posterior, tied or
alone. "Is top": the runs in which the true goal alone has the highest
posterior.
