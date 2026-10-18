## SimpleGrid 4×4, 3 observed actions

*3 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 12 | 400 | 2,612 | 15.8 | 16.7 | 12/12 | 0/12 | 0.333 |
| sharpsat-td | 12 | 400 | 2,612 | 19.8 | 20.4 | 4/12 | 4/12 | 0.389 |
| mc-sat | 12 | 400 | 2,612 | 32.3 | 33.0 | 5/12 | 5/12 | 0.396 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 1 minute; every run finished. "Top scorers"
are the hypotheses sharing the highest posterior, so a tie counts as among them
but not as sole.
