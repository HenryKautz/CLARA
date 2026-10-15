## SimpleGrid 4×4: 3 possible goals per problem (4 problems, pinned evidence)

| Method | Possible<br>goals | Runs | CNF<br>variables | CNF<br>clauses | Runs over<br>1 min | Failed<br>at 15 min | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 3 | 36 | 400 | 2,610–2,612 | 0 | 0 | 16.0 | 17.7 | 36/36 | 0/36 | 0.333 |
| sharpsat-td | 3 | 36 | 400 | 2,610–2,612 | 0 | 0 | 20.0 | 20.8 | 20/36 | 8/36 | 0.368 |
| mc-sat | 3 | 36 | 400 | 2,610–2,612 | 0 | 0 | 32.9 | 34.0 | 15/36 | 15/36 | 0.364 |

Each run is one problem, one pinned evidence file (the first N drives of a plan) and one recognize.sh --counter method. CNF size is the instantiated problem plus evidence that every method starts from (max-term adds its own soft clauses); it depends on the problem and evidence, not the method. Times are wall-clock, 8 runs in parallel (ADDMC: 2), each first limited to 1 minute and rerun with 15 minutes if it timed out; a 15-minute rerun is counted in "Runs over 1 min" and its time is that of the rerun. "Top scorers" are the hypotheses sharing the highest posterior, so a tie counts as among them but not as sole.
