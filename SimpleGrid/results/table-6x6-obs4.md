## SimpleGrid 6×6, 4 observed actions

*5 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 20 | 1,440–1,596 | 10,337–11,481 | 29.7 | 35.3 | 20/20 | 0/20 | 0.204 |
| sharpsat-td | 20 | 1,440–1,596 | 10,337–11,481 | 37.9 | 44.2 | 6/20 | 4/20 | 0.216 |
| mc-sat | 20 | 1,440–1,596 | 10,337–11,481 | 349.6 | 406.2 | 5/20 | 5/20 | 0.246 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 15 minutes; every run finished. "Top scorers"
are the hypotheses sharing the highest posterior, so a tie counts as among them
but not as sole.
