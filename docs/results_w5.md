# W5 / W6 results: MVM-Lite on BMv2

Tree: data-plane DT chosen on validation (grouped split, seed 0): depth None, class weight None, 1720 leaves, validation macro-F1 0.953, test macro-F1 0.856. Switch table: K=8 leaf entries, decayed LFU (gamma=0.99) in the controller, cold start per slice. Each slice is the chronological replay stream around an attack-phase change. BMv2 is a software switch: latencies show behavior, not ASIC performance.

## Correctness checks

| check | result |
|---|---|
| fidelity served eq tree | PASS |
| consistency switch eq policy | PASS |
| hit leaf correct | PASS |
| equivalence switch eq simulator | PASS |
| occupancy le K | PASS |

## Hit rate and latency per slice

| slice | queries | switch hit rate | simulator hit rate | fidelity | hit RTT p50 / p95 / p99 (ms) | miss service p50 / p95 / p99 (ms) | miss: backend p50 / writes p50 (ms) | mean service (ms) |
|---|---|---|---|---|---|---|---|---|
| benign flows, 04-27 to 04-28 | 30,000 | 0.8555 | 0.8555 | 1.0000 | 0.238 / 0.287 / 0.310 | 1.020 / 1.229 / 1.305 | 0.166 / 0.604 | 0.351 |
| full stream, 04-25 to 04-26 | 30,000 | 0.9221 | 0.9221 | 1.0000 | 0.211 / 0.251 / 0.276 | 0.846 / 1.102 / 1.204 | 0.128 / 0.491 | 0.274 |

## P4Runtime write rates on BMv2 (1000 range entries)

| operation | entries per second |
|---|---|
| single-entry INSERT requests | 3,866 |
| single-entry DELETE requests | 4,263 |
| INSERT, 100 entries per request | 33,622 |
| DELETE, 100 entries per request | 70,261 |
