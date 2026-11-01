## Problems

| Problem | Roads | Goals planned | Shortest horizon (min–max) | Recognition horizon | Optimal cost (min–max) | Actions (min–max) | Plan time (mean / max) | Evidence files (obs) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| grid5x5-1 | 32 | 8/8 | 13–18 | 18 | 22–28 | 14–17 | 123 s / 355 s | 16 |
| grid5x5-2 | 32 | 8/8 | 21–24 | 24 | 34–40 | 20–23 | 881 s / 1,853 s | 16 |
| grid5x5-3 | 32 | 8/8 | 16–22 | 22 | 30–38 | 18–22 | 386 s / 713 s | 16 |
| grid5x5-4 | 32 | 8/8 | 23–27 | 27 | 40–46 | 23–26 | 983 s / 1,789 s | 16 |
| grid6x6-1 | 48 | 8/8 | 18–24 | 24 | 28–40 | 17–23 | 309 s / 635 s | 16 |
| grid6x6-2 | 48 | 8/8 | 20–29 | 29 | 32–50 | 19–28 | 2,046 s / 3,777 s | 16 |
| grid6x6-3 | 48 | 8/8 | 32–38 | 38 | 56–68 (4 unproved) | 31–37 | 3,062 s / 5,493 s | 16 |
| grid6x6-4 | 48 | 8/8 | 21–27 | 27 | 38–46 | 22–26 | 1,045 s / 1,985 s | 16 |
| grid7x7-1 | 67 | 8/8 | 27–35 | 35 | 46–62 (8 unproved) | 26–34 | 2,924 s / 6,097 s | 16 |
| grid7x7-2 | 67 | 8/8 | 24–30 | 30 | 40–52 (3 unproved) | 23–29 | 3,061 s / 5,251 s | 16 |
| grid7x7-3 | 67 | 8/8 | 27–32 | 32 | 48–56 (3 unproved) | 27–31 | 3,170 s / 4,929 s | 16 |
| grid7x7-4 | 67 | 8/8 | 24–31 | 31 | 42–54 (5 unproved) | 24–30 | 4,410 s / 5,664 s | 16 |

## Recognition

| Grid | Observed actions | Method | Evidence files | Runs | Ok | Timeout | Killed | Error | Accuracy | Top-k | P(true) | Mean time | Max time |
|---|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 5×5 | 4 | max-term | 32 | 7 | 0 | 1 | 6 | 0 | – | – | – | – | – |
| 5×5 | 4 | sharpsat-td | 32 | 7 | 0 | 4 | 3 | 0 | – | – | – | – | – |
| 5×5 | 8 | max-term | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 5×5 | 8 | sharpsat-td | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 6×6 | 4 | max-term | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 6×6 | 4 | sharpsat-td | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 6×6 | 8 | max-term | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 6×6 | 8 | sharpsat-td | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 7×7 | 4 | max-term | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 7×7 | 4 | sharpsat-td | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 7×7 | 8 | max-term | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |
| 7×7 | 8 | sharpsat-td | 32 | not run | 0 | 0 | 0 | 0 | – | – | – | – | – |

| Method | Finished runs | Accuracy | Top-k | P(true) | Tied top goal |
|---|--:|--:|--:|--:|--:|
| max-term | 0 | – | – | – | – |
| sharpsat-td | 0 | – | – | – | – |

## d4 compilation

| Problem | Horizon | CNF vars | CNF clauses | Status | Compile time | d4 time | Circuit nodes | d4 peak memory | Checked by |
|---|--:|--:|--:|---|--:|--:|--:|--:|---|
| grid5x5-1 | 18 | 8,492 | 37,961 | ok (limit 3600 s) | 214 s | 174 s | 93,041 | 560 MB | count (verify-count.py, 580 s) |
| grid5x5-2 | 24 | 11,726 | 50,966 | ok (limit 3600 s) | 272 s | 182 s | 32,573 | 383 MB | unverified (count timed out at 7,200 s) |
| grid5x5-3 | 22 | 10,716 | 46,735 | ok (limit 3600 s) | 1,198 s | 1,148 s | 1,866,595 | 6,541 MB | count |
| grid5x5-4 | 27 | 13,553 | 57,674 | ok (limit 3600 s) | 1,684 s | 1,629 s | 311,315 | 2,979 MB | unverified (count timed out) |
| grid6x6-1 | 24 | 16,554 | 74,815 | timeout (limit 3600 s) | 3,605 s | – | – | 11,216 MB | – |
| grid6x6-2 | 29 | 21,127 | 90,872 | timeout (limit 3600 s) | 3,608 s | – | – | 25,627 MB | – |
| grid6x6-3 | 38 | 27,424 | 119,801 | timeout (limit 3600 s) | 3,611 s | – | – | 4,156 MB | – |
| grid6x6-4 | 27 | 19,941 | 84,316 | timeout (limit 3600 s) | 3,614 s | – | – | 18,335 MB | – |
| grid7x7-1 | – | – | – | not run | – | – | – | – | – |
| grid7x7-2 | – | – | – | not run | – | – | – | – | – |
| grid7x7-3 | – | – | – | not run | – | – | – | – | – |
| grid7x7-4 | – | – | – | not run | – | – | – | – | – |
