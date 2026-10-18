## SimpleGrid 7×7, 6 observed actions

*6 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 24 | 2,436 | 17,942 | 39.6 | 49.7 | 24/24 | 0/24 | 0.205 |
| sharpsat-td | 24 | 2,436 | 17,942 | 94.6 | 182.9 | 4/24 | 4/24 | 0.222 |
| mc-sat | 24 | 2,436 | 17,942 | 735.1 | 784.9 | 3/24 | 3/24 | 0.140 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 20 minutes of awake time (sleep not counted);
6 runs did not finish within 20 minutes; each counts as a miss in the top-scorer
columns and is left out of the times and mean P(true goal). "Top scorers" are
the hypotheses sharing the highest posterior, so a tie counts as among them but
not as sole.
