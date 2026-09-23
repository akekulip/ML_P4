# W8 results: MVM on the Tofino-1 with Vision and Hulk

Tree: data-plane DT, grouped split seed 0, depth 10 (394 leaves), the deepest tree whose thermometer key (361 bits) fits the 440-bit ternary budget; validation macro-F1 0.942, test 0.815. Static feature tables: 720 fine + 369 coarse entries. Switch: UfiSpace S9180-32X (Tofino-1), SDE 9.13.2. Vision sends queries (dev port 9, 25G); hits are answered by the switch, misses are forwarded to Hulk (dev port 10, 25G), whose C backend runs the full tree on CPU and replies through the switch. K=8 is MVM with decayed LFU (gamma 0.99) in the switch controller, hits credited from direct counters every 20 ms. K=0 is CPU only: every query goes to Hulk. Each configuration was run three times from a cold cache.

## Correctness

- Runs: 36; queries answered: 1,080,000 of 1,080,000.
- Served class equals the offline tree on 100.0000% or more of answered queries in every run; served leaf equals the tree's leaf on 100.0000% or more.

## Hit rate at 1,000 queries/s against the simulators (K=8, 30,000 queries, 3 runs)

| slice | hardware switch hit rate | ideal decayed LFU (= BMv2) | hardware-policy simulator, lag 0 / 10 / 50 queries |
|---|---|---|---|
| full stream, 25 to 26 April | 0.9558 ± 0.0009 | 0.9633 | 0.9624 / 0.9601 / 0.9530 |
| benign flows, 27 to 28 April | 0.8461 ± 0.0015 | 0.8848 | 0.8827 / 0.8694 / 0.8581 |

## Latency at 1,000 queries/s (all runs pooled)

| path | median | 99th percentile |
|---|---|---|
| full stream, 25 to 26 April: on-chip pipeline (switch hit, ingress to egress) | 362 ns | 391 ns |
| full stream, 25 to 26 April: round trip at Vision, switch hit (K=8) | 102.5 µs | 133.0 µs |
| full stream, 25 to 26 April: round trip at Vision, miss answered by Hulk CPU (K=8) | 232.2 µs | 324.7 µs |
| full stream, 25 to 26 April: round trip at Vision, CPU only (K=0) | 300.7 µs | 338.1 µs |
| benign flows, 27 to 28 April: on-chip pipeline (switch hit, ingress to egress) | 362 ns | 391 ns |
| benign flows, 27 to 28 April: round trip at Vision, switch hit (K=8) | 103.4 µs | 134.1 µs |
| benign flows, 27 to 28 April: round trip at Vision, miss answered by Hulk CPU (K=8) | 238.3 µs | 315.6 µs |
| benign flows, 27 to 28 April: round trip at Vision, CPU only (K=0) | 300.7 µs | 333.8 µs |

CPU compute alone (Hulk, Intel(R) Xeon(R) Gold 6140 CPU @ 2.30GHz, one core, in memory, same tree): 29.9 ns per query (33.5 M queries/s), 0 mismatches, 31.5 ns per query (31.7 M queries/s), 0 mismatches.

## Control plane (K=8, 1,000 queries/s)

- Digests received per run: 2972; leaf installs per run: 2122.
- Controller time from digest receipt to completed table write (delete + insert): median 6.08 ms, 99th percentile 24.40 ms.

## Load sweep, full stream (3 runs each)

| offered queries/s | mode | answered | switch hit rate | answer rate (queries/s) | RTT median | RTT 99th |
|---|---|---|---|---|---|---|
| 1,000 | MVM (K=8) | 1.0000 | 0.9558 | 1,000 | 102.8 µs | 247.8 µs |
| 1,000 | CPU only (K=0) | 1.0000 | 0.0000 | 1,000 | 300.7 µs | 338.1 µs |
| 5,000 | MVM (K=8) | 1.0000 | 0.8086 | 5,001 | 102.9 µs | 309.3 µs |
| 5,000 | CPU only (K=0) | 1.0000 | 0.0000 | 5,001 | 298.7 µs | 349.3 µs |
| 20,000 | MVM (K=8) | 1.0000 | 0.6764 | 20,005 | 47.3 µs | 226.2 µs |
| 20,000 | CPU only (K=0) | 1.0000 | 0.0000 | 20,004 | 132.5 µs | 242.4 µs |
| 50,000 | MVM (K=8) | 1.0000 | 0.8029 | 50,011 | 39.3 µs | 179.0 µs |
| 50,000 | CPU only (K=0) | 1.0000 | 0.0000 | 50,006 | 107.3 µs | 185.2 µs |
| 100,000 | MVM (K=8) | 1.0000 | 0.7414 | 100,020 | 32.5 µs | 465.8 µs |
| 100,000 | CPU only (K=0) | 1.0000 | 0.0000 | 100,009 | 69.1 µs | 638.6 µs |
