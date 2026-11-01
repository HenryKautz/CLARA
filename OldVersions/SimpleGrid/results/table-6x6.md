## SimpleGrid 6×6, all evidence lengths

*5 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 100 | 1,440–1,596 | 10,334–11,482 | 29.6 | 70.1 | 100/100 | 0/100 | 0.203 |
| sharpsat-td | 100 | 1,440–1,596 | 10,334–11,482 | 37.6 | 44.2 | 23/100 | 19/100 | 0.209 |
| mc-sat | 100 | 1,440–1,596 | 10,334–11,482 | 349.2 | 406.2 | 17/100 | 17/100 | 0.186 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 15 minutes; every run finished. "Top scorers"
are the hypotheses sharing the highest posterior, so a tie counts as among them
but not as sole.
