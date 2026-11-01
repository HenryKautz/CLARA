## SimpleGrid 3×3, 1 observed action

*2 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 8 | 141 | 819 | 11.7 | 12.6 | 8/8 | 0/8 | 0.500 |
| sharpsat-td | 8 | 141 | 819 | 15.7 | 17.2 | 5/8 | 3/8 | 0.500 |
| mc-sat | 8 | 141 | 819 | 14.6 | 15.7 | 4/8 | 4/8 | 0.453 |
| addmc | 8 | 141 | 819 | 9.4 | 9.7 | 5/8 | 3/8 | 0.500 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel (ADDMC: 2), each limited to 1 minute; every run finished. "Top
scorers" are the hypotheses sharing the highest posterior, so a tie counts as
among them but not as sole.
