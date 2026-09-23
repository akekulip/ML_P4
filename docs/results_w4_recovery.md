# W4 / RQ4: adaptation after attack-phase changes (measured in flows)

Grouped split, depth 10, K=8, seeds 0-2 (mean). Only days that start a new attack phase (the set of attack types with >= 1% of the day's flows differs from the previous day) are counted; the stream's first day is a cold start and is skipped. Excess misses (primary) = misses in the first 10,000 flows of the phase beyond the policy's steady-state rate for the rest of that day. Flows to recover = flows until a 500-flow bin's miss rate is at most max(1.5 x steady, steady + 0.002). Static placement is excluded (it never adapts).

## full stream: excess misses in the first 10,000 flows of each phase

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-23 |      -21 |         -27 |   -40 |  1251 |
| 2019-04-25 |      188 |         310 |   306 |   239 |
| 2019-04-26 |      -94 |        -136 |  -210 |    30 |
| 2019-04-27 |      341 |         505 |   708 |  2789 |
| 2019-04-28 |       34 |          52 |    26 |   695 |
| 2019-04-29 |        3 |          11 |    11 |    11 |

## full stream: flows to recover

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-23 |      667 |         833 |   833 |  9333 |
| 2019-04-25 |      500 |         333 |   333 |     0 |
| 2019-04-26 |      500 |         500 |   500 |  1667 |
| 2019-04-27 |    16167 |       16167 | 16333 | 23167 |
| 2019-04-28 |     1500 |        1500 |  1500 |  1500 |
| 2019-04-29 |      167 |         333 |   333 |     0 |

## full stream: steady hit rate for the rest of the day

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-23 |    0.995 |       0.992 | 0.991 | 0.983 |
| 2019-04-25 |    0.994 |       0.99  | 0.989 | 0.932 |
| 2019-04-26 |    0.972 |       0.956 | 0.948 | 0.797 |
| 2019-04-27 |    0.983 |       0.974 | 0.969 | 0.77  |
| 2019-04-28 |    0.951 |       0.912 | 0.91  | 0.595 |
| 2019-04-29 |    0.995 |       0.99  | 0.99  | 0.97  |

## benign stream: excess misses in the first 10,000 flows of each phase

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-25 |      232 |         405 |   351 |   726 |
| 2019-04-26 |      312 |         445 |   528 |  2273 |
| 2019-04-27 |      171 |         335 |   316 |  1885 |
| 2019-04-28 |     -278 |        -546 |  -571 | -1541 |

## benign stream: flows to recover

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-25 |     3500 |        3500 |  3500 |  3667 |
| 2019-04-26 |     1333 |        1167 |  1167 |  4000 |
| 2019-04-27 |        0 |           0 |   833 |  4833 |
| 2019-04-28 |      667 |         667 |   500 |     0 |

## benign stream: steady hit rate for the rest of the day

| day        |   belady |   dlfu_0.99 |   lru |   lfu |
|:-----------|---------:|------------:|------:|------:|
| 2019-04-25 |    0.961 |       0.944 | 0.926 | 0.85  |
| 2019-04-26 |    0.952 |       0.92  | 0.912 | 0.689 |
| 2019-04-27 |    0.93  |       0.9   | 0.866 | 0.72  |
| 2019-04-28 |    0.921 |       0.854 | 0.851 | 0.518 |

