## SimpleGrid plan recognition by grid size and observations

| Grid size | Goals | Min goal distance | Observations | Mean CNF variables | Mean CNF clauses | max-term<br>Mean time (s) | max-term<br>Among top | max-term<br>Is top | sharpsat-td<br>Mean time (s) | sharpsat-td<br>Among top | sharpsat-td<br>Is top | mc-sat<br>Mean time (s) | mc-sat<br>Among top | mc-sat<br>Is top |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3×3 | 2 | 3 | 1 | 141 | 819 | 11.7 | 8/8 | 0/8 | 15.7 | 5/8 | 3/8 | 14.6 | 4/8 | 4/8 |
| 3×3 | 2 | 3 | 2 | 141 | 820 | 12.1 | 8/8 | 0/8 | 16.0 | 4/8 | 4/8 | 14.2 | 4/8 | 4/8 |
| 4×4 | 3 | 5 | 1 | 400 | 2,610 | 16.2 | 12/12 | 0/12 | 20.1 | 8/12 | 0/12 | 33.4 | 6/12 | 6/12 |
| 4×4 | 3 | 5 | 2 | 400 | 2,611 | 16.2 | 12/12 | 0/12 | 20.1 | 8/12 | 4/12 | 32.9 | 4/12 | 4/12 |
| 4×4 | 3 | 5 | 3 | 400 | 2,612 | 15.8 | 12/12 | 0/12 | 19.8 | 4/12 | 4/12 | 32.3 | 5/12 | 5/12 |
| 5×5 | 4 | 6 | 1 | 812 | 5,622 | 25.6 | 16/16 | 0/16 | 35.0 | 6/16 | 2/16 | 219.4 | 6/16 | 6/16 |
| 5×5 | 4 | 6 | 2 | 812 | 5,623 | 34.4 | 16/16 | 0/16 | 36.0 | 7/16 | 3/16 | 213.4 | 2/16 | 2/16 |
| 5×5 | 4 | 6 | 3 | 812 | 5,624 | 43.9 | 16/16 | 0/16 | 35.0 | 7/16 | 5/16 | 207.4 | 3/16 | 3/16 |
| 5×5 | 4 | 6 | 4 | 812 | 5,625 | 36.1 | 16/16 | 0/16 | 34.6 | 4/16 | 4/16 | 200.1 | 5/16 | 5/16 |
| 6×6 | 5 | 7 | 1 | 1,557 | 11,192 | 31.2 | 20/20 | 0/20 | 37.7 | 4/20 | 4/20 | 350.0 | 4/20 | 4/20 |
| 6×6 | 5 | 7 | 2 | 1,557 | 11,193 | 28.8 | 20/20 | 0/20 | 37.7 | 5/20 | 3/20 | 350.1 | 3/20 | 3/20 |
| 6×6 | 5 | 7 | 3 | 1,557 | 11,194 | 28.8 | 20/20 | 0/20 | 37.1 | 4/20 | 4/20 | 349.9 | 3/20 | 3/20 |
| 6×6 | 5 | 7 | 4 | 1,557 | 11,195 | 29.7 | 20/20 | 0/20 | 37.9 | 6/20 | 4/20 | 349.6 | 5/20 | 5/20 |
| 6×6 | 5 | 7 | 5 | 1,557 | 11,196 | 29.6 | 20/20 | 0/20 | 37.7 | 4/20 | 4/20 | 346.2 | 2/20 | 2/20 |

Fully connected grids with 1 truck and multiple possible goal destinations.
"Among top": the runs in which the true goal has the highest posterior, tied or
alone. "Is top": the runs in which the true goal alone has the highest
posterior. Examples (evidence files, each run with every method): 3×3 16, 4×4
36, 5×5 64, 6×6 100.
