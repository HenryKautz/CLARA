## SimpleGrid 8×8, 2 observed actions

*7 possible goals per problem; 4 problems; pinned evidence*

| Method | Runs | CNF<br>variables | CNF<br>clauses | Mean<br>time (s) | Max<br>time (s) | True goal<br>among top<br>scorers | True goal<br>is the sole<br>top scorer | Mean<br>P(true<br>goal) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| max-term | 28 | 3,808–4,096 | 28,563–30,755 | 61.3 | 64.6 | 28/28 | 0/28 | 0.143 |
| sharpsat-td | 5 of 28 | 3,808 | 28,563 | – | – | 0/5 | 0/5 | – |
| mc-sat | 5 of 28 | 3,808 | 28,563 | – | – | 0/5 | 0/5 | – |

Each run is one problem, one pinned evidence file (the first N drives of a plan)
and one recognize.sh --counter method. CNF size is the instantiated problem plus
evidence that every method starts from (max-term adds its own soft clauses); it
depends on the problem and evidence, not the method. Times are wall-clock, 8
runs in parallel, each limited to 20 minutes of awake time (sleep not counted);
10 runs did not finish; each counts as a miss in the top-scorer columns and is
left out of the times and mean P(true goal). "Top scorers" are the hypotheses
sharing the highest posterior, so a tie counts as among them but not as sole.
sharpsat-td was stopped after 34 runs, of which 0 finished, and not run on the
rest; mc-sat was stopped after 32 runs, of which 0 finished, and not run on the
rest. 5 of the unfinished runs were stopped by FiFO's 600 s limit on a single
solver call (one exact count), not by the run's own limit.
