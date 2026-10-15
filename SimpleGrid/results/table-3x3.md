## SimpleGrid 3×3: 2 possible goals per problem (4 problems, pinned evidence)

| Method | Possible<br>goals | Runs | CNF<br>variables | CNF<br>clauses | Runs over<br>1 min | Failed<br>at 15 min | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 2 | 16 | 141 | 819–820 | 0 | 0 | 11.9 | 13.2 | 16/16 | 0/16 | 0.500 |
| sharpsat-td | 2 | 16 | 141 | 819–820 | 0 | 0 | 15.8 | 17.2 | 9/16 | 7/16 | 0.500 |
| mc-sat | 2 | 16 | 141 | 819–820 | 0 | 0 | 14.4 | 15.7 | 8/16 | 8/16 | 0.511 |
| addmc | 2 | 16 | 141 | 819–820 | 0 | 0 | 9.2 | 9.7 | 9/16 | 7/16 | 0.500 |

Each run is one problem, one pinned evidence file (the first N drives of a plan) and one recognize.sh --counter method. CNF size is the instantiated problem plus evidence that every method starts from (max-term adds its own soft clauses); it depends on the problem and evidence, not the method. Times are wall-clock, 8 runs in parallel (ADDMC: 2), each first limited to 1 minute and rerun with 15 minutes if it timed out; a 15-minute rerun is counted in "Runs over 1 min" and its time is that of the rerun. "Top scorers" are the hypotheses sharing the highest posterior, so a tie counts as among them but not as sole.
