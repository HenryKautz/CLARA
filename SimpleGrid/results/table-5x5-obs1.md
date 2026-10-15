## SimpleGrid 5×5, 1 observed action

*4 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 16 | 760–865 | 5,249–5,995 | 25.6 | 36.8 | 16/16 | 0/16 | 0.250 |
| sharpsat-td | 16 | 760–865 | 5,249–5,995 | 35.0 | 103.5 | 6/16 | 2/16 | 0.250 |
| mc-sat | 16 | 760–865 | 5,249–5,995 | 219.4 | 333.6 | 6/16 | 6/16 | 0.243 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel (ADDMC: 2), each first limited to 1 minute and rerun with 15
minutes if it timed out (its time is then that of the rerun); every run
finished. "Top scorers" are the hypotheses sharing the highest posterior, so a
tie counts as among them but not as sole.
