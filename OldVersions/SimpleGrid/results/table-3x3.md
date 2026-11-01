## SimpleGrid 3×3, all evidence lengths

*2 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 16 | 141 | 819–820 | 11.9 | 13.2 | 16/16 | 0/16 | 0.500 |
| sharpsat-td | 16 | 141 | 819–820 | 15.8 | 17.2 | 9/16 | 7/16 | 0.500 |
| mc-sat | 16 | 141 | 819–820 | 14.4 | 15.7 | 8/16 | 8/16 | 0.511 |
| addmc | 16 | 141 | 819–820 | 9.2 | 9.7 | 9/16 | 7/16 | 0.500 |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel (ADDMC: 2), each limited to 1 minute; every run finished. "Top
scorers" are the hypotheses sharing the highest posterior, so a tie counts as
among them but not as sole.
