## SimpleGrid 7×7, all evidence lengths

*6 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 144 | 2,436 | 17,937–17,942 | 40.0 | 49.8 | 144/144 | 0/144 | 0.181 |
| sharpsat-td | 144 | 2,436 | 17,937–17,942 | 105.2 | 328.9 | 31/144 | 31/144 | 0.200 |
| mc-sat | 144 | 2,436 | 17,937–17,942 | 737.3 | 784.9 | 28/144 | 28/144 | 0.191 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 20 minutes of awake time (sleep not counted);
38 runs did not finish; each counts as a miss in the top-scorer columns and is
left out of the times and mean P(true goal). "Top scorers" are the hypotheses
sharing the highest posterior, so a tie counts as among them but not as sole. 2
of the unfinished runs ended early with an error instead (no posterior).
