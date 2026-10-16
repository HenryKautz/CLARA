## SimpleGrid 6×6, 1 observed action

*5 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 20 | 1,440–1,596 | 10,334–11,478 | 31.2 | 70.1 | 20/20 | 0/20 | 0.200 |
| sharpsat-td | 20 | 1,440–1,596 | 10,334–11,478 | 37.7 | 41.7 | 4/20 | 4/20 | 0.200 |
| mc-sat | 20 | 1,440–1,596 | 10,334–11,478 | 350.0 | 398.6 | 4/20 | 4/20 | 0.182 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 15 minutes; every run finished. "Top scorers"
are the hypotheses sharing the highest posterior, so a tie counts as among them
but not as sole.
