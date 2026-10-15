## SimpleGrid 3×3, 2 observed actions

*2 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 8 | 141 | 820 | 12.1 | 13.2 | 8/8 | 0/8 | 0.500 |
| sharpsat-td | 8 | 141 | 820 | 16.0 | 16.7 | 4/8 | 4/8 | 0.500 |
| mc-sat | 8 | 141 | 820 | 14.2 | 15.7 | 4/8 | 4/8 | 0.570 |
| addmc | 8 | 141 | 820 | 9.0 | 9.7 | 4/8 | 4/8 | 0.500 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel (ADDMC: 2), each first limited to 1 minute and rerun with 15
minutes if it timed out (its time is then that of the rerun); every run
finished. "Top scorers" are the hypotheses sharing the highest posterior, so a
tie counts as among them but not as sole.
