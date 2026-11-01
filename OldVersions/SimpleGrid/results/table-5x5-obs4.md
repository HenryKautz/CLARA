## SimpleGrid 5×5, 4 observed actions

*4 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 16 | 760–865 | 5,252–5,998 | 36.1 | 118.9 | 16/16 | 0/16 | 0.278 |
| sharpsat-td | 16 | 760–865 | 5,252–5,998 | 34.6 | 87.6 | 4/16 | 4/16 | 0.277 |
| mc-sat | 16 | 760–865 | 5,252–5,998 | 200.1 | 311.2 | 5/16 | 5/16 | 0.303 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each first limited to 1 minute and rerun with 15 minutes if it
timed out (its time is then that of the rerun); every run finished. "Top
scorers" are the hypotheses sharing the highest posterior, so a tie counts as
among them but not as sole.
