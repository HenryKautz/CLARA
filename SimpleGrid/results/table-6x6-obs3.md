## SimpleGrid 6×6, 3 observed actions

*5 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 20 | 1,440–1,596 | 10,336–11,480 | 28.8 | 34.7 | 20/20 | 0/20 | 0.204 |
| sharpsat-td | 20 | 1,440–1,596 | 10,336–11,480 | 37.1 | 42.2 | 4/20 | 4/20 | 0.211 |
| mc-sat | 20 | 1,440–1,596 | 10,336–11,480 | 349.9 | 404.9 | 3/20 | 3/20 | 0.166 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 15 minutes; every run finished. "Top scorers"
are the hypotheses sharing the highest posterior, so a tie counts as among them
but not as sole.
