## SimpleGrid 5×5, 3 observed actions

*4 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 16 | 760–865 | 5,251–5,997 | 43.9 | 114.3 | 16/16 | 0/16 | 0.255 |
| sharpsat-td | 16 | 760–865 | 5,251–5,997 | 35.0 | 69.8 | 7/16 | 5/16 | 0.293 |
| mc-sat | 16 | 760–865 | 5,251–5,997 | 207.4 | 317.3 | 3/16 | 3/16 | 0.224 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each first limited to 1 minute and rerun with 15 minutes if it
timed out (its time is then that of the rerun); every run finished. "Top
scorers" are the hypotheses sharing the highest posterior, so a tie counts as
among them but not as sole.
