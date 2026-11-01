## SimpleGrid 5×5, all evidence lengths

*4 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 64 | 760–865 | 5,249–5,998 | 35.0 | 118.9 | 64/64 | 0/64 | 0.258 |
| sharpsat-td | 64 | 760–865 | 5,249–5,998 | 35.1 | 103.5 | 24/64 | 14/64 | 0.271 |
| mc-sat | 64 | 760–865 | 5,249–5,998 | 210.1 | 333.6 | 16/64 | 16/64 | 0.252 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each first limited to 1 minute and rerun with 15 minutes if it
timed out (its time is then that of the rerun); every run finished. "Top
scorers" are the hypotheses sharing the highest posterior, so a tie counts as
among them but not as sole.
