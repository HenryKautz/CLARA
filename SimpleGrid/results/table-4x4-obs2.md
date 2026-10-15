## SimpleGrid 4×4, 2 observed actions

*3 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 12 | 400 | 2,611 | 16.2 | 16.7 | 12/12 | 0/12 | 0.333 |
| sharpsat-td | 12 | 400 | 2,611 | 20.1 | 20.4 | 8/12 | 4/12 | 0.381 |
| mc-sat | 12 | 400 | 2,611 | 32.9 | 33.9 | 4/12 | 4/12 | 0.352 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel (ADDMC: 2), each first limited to 1 minute and rerun with 15
minutes if it timed out (its time is then that of the rerun); every run
finished. "Top scorers" are the hypotheses sharing the highest posterior, so a
tie counts as among them but not as sole.
