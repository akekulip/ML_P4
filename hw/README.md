# MVM-Lite on the Tofino-1 testbed (W8)

## Topology

| role | host | interface / port |
|---|---|---|
| switch | UfiSpace S9180-32X (Tofino-1), `decps@10.10.54.81`, SDE 9.13.2 | dev port 9 → Vision, dev port 10 → Hulk (25G, RS-FEC) |
| query client | Vision `10.10.54.166` | `enp59s0f0np0`, MAC 3c:fd:fe:cc:5d:c0 |
| CPU backend | Hulk `10.10.54.158` | `enp59s0f1np1`, MAC 3c:fd:fe:e5:f9:91 |

Vision sends each query as Ethernet/IPv4/UDP(dst 50000) with a 56-byte MVM header: query id,
flags, class, leaf, two timestamps, and the ten order-preserving feature keys. The switch answers
hits itself and reflects them to Vision with the MAC addresses swapped. Misses go to Hulk and to the
controller as a digest. Hulk runs the full tree in C and replies through the switch.

## Encoding

Tofino-1 range keys are limited to about 20 bits per table. See `src/mvm/tofino_encode.py`.

- **Per-feature code tables.** Each feature has two static tables that write a thermometer code,
  one bit per tree threshold:
  - a fine table (`key[31:12]` exact, `key[11:0]` range), used for buckets that contain a threshold;
  - a coarse table (`key[31:12]` range), used everywhere else.
- **Leaf table.** `leaf_tbl` is ternary over the concatenated codes. Each leaf needs only two
  cared-for bits per feature, so each leaf is exactly one entry.
- **Tree choice.** Depth 10 (394 leaves, a 361-bit key) is the deepest tree that fits. Depth 12 needs 602 bits.
- **Exactness.** The switch path equals `tree.apply` exactly. This is checked offline by
  `tests/test_tofino_encode.py` and `experiments/w8_prepare.py`, and on hardware on every query.

## Files

- `experiments/w8_prepare.py` generates everything in `hw/build/`:
  - the tree and `model.json`;
  - the generated `mvm_tna.p4`;
  - `tree.bin`;
  - replay queries and expected answers.
- `hw/controller.py` runs on the switch with `bfrt_grpc`.
  - `setup`: ports, forwarding, static tables.
  - `run`: digests, decayed LFU with counter-polled hit credit, leaf installs and evictions.
- `hw/vision_client.c` is the paced `sendmmsg`/`recvmmsg` client. It writes per-query records.
- `hw/hulk_backend.c` has two modes:
  - `serve`: answers switch misses on CPU;
  - `bench`: in-memory CPU baseline.
- `hw/redeploy_switch.sh` compiles into `~/ml_p4/build_new`, swaps builds, relaunches `bf_switchd`
  and runs setup. It only ever replaces the MVM program.
- `hw/run_experiment.sh` runs one experiment. `hw/run_campaign.sh` runs the W8 campaign.
- `experiments/w8_report.py` writes `docs/results_w8.md` and the `figures/w8_*` files.

## Current switch state and hand-back

- **Running:** MVM (`mvm_tna`) is running on the switch, launched by `~/ml_p4/launch_mvm.sh` (Philip chose to leave it running).
- **Displaced:** the DNP3 anchor-fix program (`defense4_rrc_bor_unified12`) was displaced on 2026-09-23.
  Its launch state is saved in `~/ml_p4/snapshot_dnp3_20260923/`.
- **Restore:** run `~/ml_p4/RESTORE_dnp3_20260923.sh` on the switch.
  - It stops MVM with `pkill -x`, never `-f`.
  - It relaunches the DNP3 launcher.
  - It prints the DNP3 table-setup script to run afterwards.
