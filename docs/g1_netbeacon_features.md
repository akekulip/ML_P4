# G1: NetBeacon features, phase schedule and table fidelity

This note covers NetBeacon at commit 06c6127, the shipped PeerRush build with 3 classes. Every path below is relative to `third_party/NetBeacon/`. The code is `src/dgrade/netbeacon.py` and the tests are `tests/test_dgrade_netbeacon.py`.

- **INFERRED** means the value was derived from the code and has not been observed on the switch.
- "sw" is shorthand for `switch/data_plane/switch.p4`, "hdr" for `headers.p4`, "prs" for `parsers.p4`, "ctl" for `switch/control_plane/controller.py`, and "mr" for `model_generation/model_representation.py`.

## 1. Table fidelity result

`TableModel` evaluates the shipped `.pkl` tables in the same way the switch matches them:

1. **Feature tables.** These are ternary tables. Where several entries match, the one with the lowest `$MATCH_PRIORITY` wins. A miss leaves the range-mark field at 0 (sw:559-572).
2. **Range-mark code.** Each code is cut to the width of its metadata field (hdr:219-233).
3. **Model table.** This is also ternary but has no priorities. Phase tables additionally match `total_pkts` exactly.
4. **Action data.** For the class tables, `result = argmax+1`, plus 50 in the 2048 phase (ctl:217, 229-235).

The lowest-number-wins rule is the only one under which the generator's layout makes sense. The generator emits the `[t_i, end)` entry one priority number below the wider `[start, end)` entry that it overrides (`model_generation/tree_to_table/utils.py:124-137`). Reversing the rule drops agreement with the `.dot` trees to about 70% (measured on phases 2 and 32).

The test compared `TableModel` against the `.dot` tree (or, for the flow-size table, against the XGBoost score). Each model got 12,000 integer rows plus one row at each edge of every leaf's box. For the XGBoost tree a leaf box is `ceil(lo) ≤ x < ceil(hi)`, because its splits are strict `<`:

- 45% of the random values sit within ±1 of a threshold.
- 35% are drawn from [min threshold − 10, max threshold + 10].
- 20% are drawn from the key's whole data-plane domain.
- The random rows reach only 58–94% of leaves on their own, so the leaf-box rows were added. For every model, including all 182 Flow_Size_Tree entries, the test asserts that every model-table entry is hit at least once.

| model | model-table entries (= .dot leaves) | agreement | misses | ambiguous hits |
|---|---|---|---|---|
| Pkt_Tree (`class_pkt_1rf_0.dot`) | 387 | **100%** | 0 | 0 |
| Flow_Size_Tree (`flow_size_predict_1xgb.txt`, compared as a score) | 182 | **100%** | 0 | 0 |
| Flow_Tree at phase 2 / 4 / 8 / 32 | 288 / 385 / 398 / 252 | **100%** each | 0 | 0 |
| Flow_Tree at phase 256 / 512 / 2048 | 141 / 95 / 144 | **100%** each | 0 | 0 |

**No mismatches.** The shipped tables were built from these `.dot` and dump files, and no test is marked xfail.

This agreement holds for integer keys compared exactly, which is how the switch compares them. Two differences from the original models remain:

- **sklearn casts inputs to float32** before comparing them with thresholds. For keys above 2^24 (large `flow_iat_min` and `pkt_size_var_approx` values), sklearn on the training machine can therefore disagree with the switch within one float32 ulp of a threshold. The `.dot` export also rounds thresholds to 3 decimals. `DotTree` compares in float64.
- **The XGBoost dump has no `base_score`.** The table uses round(sigmoid(sum of leaves)·100), as in `tree_to_table/xgb.py:86-89`, which is equivalent to base_score 0.5.

## 2. Per-packet features (Pkt_Tree fallback, and the Flow_Size_Tree gate)

Both models use all seven keys. Pkt_Tree has 387 leaves and depth 9. Flow_Size_Tree is one XGBoost tree with 182 leaves.

| training name | switch key | definition in the switch | unit | key bits | range-mark field (bits) |
|---|---|---|---|---|---|
| proto | `hdr.ipv4.protocol` (sw:324) | IPv4 protocol. Only 6 and 17 reach the pipeline: the parser rejects anything else, fragments, and packets with IP options (prs:58-62) | code | 8 | feat8 (8), hdr:224 |
| total_len | `hdr.ipv4.total_len` (sw:300) | IPv4 Total Length, i.e. the IP packet length without the Ethernet header | bytes | 16 | feat5 (144), hdr:221 |
| diffserv | `hdr.ipv4.diffserv` (sw:332) | the whole ToS byte (DSCP and ECN) | code | 8 | feat9 (24), hdr:225; the action parameter is 32 bits, cut to 24 (sw:329) |
| ttl | `hdr.ipv4.ttl` (sw:316) | IPv4 TTL as the packet arrives | hops | 8 | feat7 (64), hdr:223 |
| tcp_dataOffset | `ig_md.tcp_data_offset` (sw:292) | TCP data offset; **0 for UDP** (prs:71, 80) | 32-bit words | 4 | feat4 (8), hdr:220 |
| tcp_window | `ig_md.tcp_window` (sw:284) | TCP window field, unscaled; **0 for UDP** (prs:70, 79) | bytes | 16 | feat3 (48), hdr:219 |
| udp_length | `ig_md.udp_length` (sw:308) | UDP header Length field; **0 for TCP** (prs:69, 81) | bytes | 16 | feat6 (72), hdr:222; the action parameter is 80 bits, cut to 72 (sw:305) |

- **Key widths** come from mr:11-12.
- **The feature tables are shared.** Pkt_Tree and Flow_Size_Tree read the same feature tables, whose thresholds are the union of both models' thresholds (mr:26-29).
- **Parser rejects.** UDP packets with source port 68 are also rejected (prs:82-85).
- **Flow_Size_Tree** writes `ig_md.flow_size = round(sigmoid(margin)·100)` (sw:438-460; `tree_to_table/xgb.py:89`). A flow is predicted long iff `flow_size > 50` (sw:608).

## 3. Per-flow features (Flow_Tree, one tree per phase)

Every phase tree uses all seven features. The feature tables are keyed on `total_pkts: exact` plus the feature value, as ternary (sw:338-392). Each value is read at the phase packet itself, after that packet has updated the registers (sw:628-637).

**N** below is the phase packet count, which equals `total_pkts`. The count includes the flow's first packet, which initialises the registers (sw:610-619, 29, 51, 77, 100).

| training name | switch key | definition in the switch | unit | key bits | range-mark field (bits) |
|---|---|---|---|---|---|
| pkt_size_max | `ig_md.max_pkt_length` (sw:63-83, 364) | max of `total_len` over the first N packets | bytes | 16 | feat13 (80), hdr:230 |
| pkt_size_min | `ig_md.min_pkt_length` (sw:86-106, 372) | min of `total_len` over the first N packets | bytes | 16 | feat14 (48), hdr:231 |
| pkt_size_avg | `ig_md.pkt_size_avg` (sw:640, 648, …, 696) | `total_bytes >> log2(N)`, i.e. floor(Σ total_len / N). `total_bytes` is a 32-bit sum (sw:20-39) | bytes | 32 | feat12 (72), hdr:229 |
| pkt_size_var_approx | `ig_md.pkt_length_power_sum` after the phase fix-up (sw:642-644, …, 698-700) | S = Σ SQR(total_len>>2) over N packets (sw:182-203, 579). The phase shift gives S·16/N: `<<3,<<2,<<1,>>1,>>4,>>5,>>7` for N = 2,4,8,32,256,512,2048. The switch then subtracts SQR(pkt_size_avg) (sw:206-216). The result is an approximate E[L²] − mean², **in unsigned 32-bit arithmetic** | bytes² | 32 | feat16 (80), hdr:233 |
| flow_iat_min | `ig_md.min_ipd` (sw:159-179, 380) | min of successive inter-packet gaps over packets 2..N. Timestamps are `(bit<32>)global_tstamp >> 10` (sw:617, 635), gaps come from sw:142, and the register starts at 0xFFFFFFFF (sw:170) | ≈1.024 µs ticks | 32 | feat15 (72), hdr:232 |
| bin_3 | `ig_md.bin1` (sw:110-122, 340) | count of packets in the first N with `total_len & 0xFFF0 == 48`, i.e. [48, 64). The pkl bin table is `[[80,65520],[48,65520]]`, and it is loaded **reversed** (ctl:263), so bin1 = 48. See `tree_to_table/utils.py:145-151` and ctl:124-149 | packets | 16 | feat10 (32), hdr:227 |
| bin_5 | `ig_md.bin2` (sw:124-136, 348) | count of packets with `total_len` in [80, 96). **The register is 8 bits and wraps at 256** (sw:124) | packets | 8 | feat11 (24), hdr:228; the action parameter is 32 bits, cut to 24 (sw:346) |

The key widths match mr:61.

Points the emulator must reproduce (none of this affects table fidelity):

- **Variance wraps.** A negative "variance", caused by SQR approximation or by the floor in the mean, wraps to a value near 2^32. The trees contain thresholds in that region:
  - Near 2^32: phases 2, 4, 32 and 256 have `pkt_size_var_approx` thresholds between 4,294,964,992 and 4,294,967,168.
  - Near 2^31: phases 2, 4, 8 and 32 also have thresholds between 2,147,483,632 and 2,147,672,070.5.
  - For packets of at most 1,500 bytes, a genuine variance is below 2^20, and a small negative one wraps to just under 2^32. Neither explains values near 2^31. That weakens the inference that training reproduced the switch's unsigned 32-bit wrap. The training arithmetic may have wrapped differently (for example a signed type, or a different shift order), and the training scripts are not in the artifact. **Open; not settled here.**
- **SQR is not a plain square.** It is a Tofino `MathUnit<bit<32>>(MathOp_t.SQR, 1)`. Whether it is exact for 9-bit inputs (1500>>2 = 375) is **not established here**. MathUnit is a table-driven approximation, and its exact output needs bf-p4c/model or switch confirmation.
- **Timestamps wrap every 4.295 s. INFERRED:** in P4-16 a cast binds tighter than `>>`. So `(bit<32>) global_tstamp >> 10` takes the low 32 bits of the nanosecond clock before shifting, which gives values below 2^22 that wrap every 2^32 ns ≈ 4.295 s.
  - A gap that spans a wrap reads as about 2^32 minus a small number.
  - A plain gap can never exceed 2^22 − 1 ≈ 4.19 M ticks.
  - The trees still contain `flow_iat_min` thresholds that the switch cannot produce, for example 297,764,320 at phase 2 and 29,778,175.5 at phase 8. So the training features were likely computed without this wrap.
  - The same precedence gives `now_timestamp` (sw:581) values in [0, 4096) units of 2^20 ns, wrapping every 4.295 s. The wrap cuts both ways:
    - **Looks active.** An incumbent idle for just over a multiple of 4.295 s can look recently active.
    - **Looks timed out.** The register stores a value in [0, 4096) (sw:262), and `last_classified = now − value` is 32-bit arithmetic (sw:268). Once `now` wraps past the stored value, `last_classified ≥ 2^32 − 4096`, which is ≥ 256. So **every undetermined incumbent is evictable** (sw:609) from the wrap until its next packet refreshes the register (sw:626). This opens a periodic eviction window every ~4.295 s, independent of how recently the flow was active.
- **The 1024 phase does nothing useful.** There is a code branch for N = 1024 (sw:687-694), but no 1024 entries exist in any feature table or in Flow_Tree. At packet 1024 every range mark is 0, Flow_Tree misses, and the stored result is kept.

## 4. Phase schedule and verdict timeline

| state of the flow | verdict carried in `ig_md.result` | cite |
|---|---|---|
| Flow is in the verdict memo (`Flow_result` hit: determined, and among the last ≤1500 digests) | memo result (class+1+50), with no feature updates | sw:605, 466-480; ctl:53-74 |
| First packet, or a new flow at a slot, **no takeover** (predicted short, or incumbent undetermined and idle < 256 ticks) | `result = 0`, so **Pkt_Tree per packet**. A Pkt_Tree miss leaves 0 | sw:606-624, 722-724 |
| First packet **with takeover** (predicted long, and the incumbent is determined or idle ≥ timeout) | Pkt_Tree verdict of that packet. The packet recirculates, and the recirculated copy writes that verdict (carried in TTL, sw:729) into the result register (sw:596-601). **INFERRED from code.** | sw:608-623, 596-601 |
| Stored flow, packet N ∈ {2, 4, 8, 32, 256, 512, 2048} | Flow_Tree verdict for phase N (class+1; **+50 at 2048, which marks the flow determined**). The packet is recirculated to store it. If result > 50 a digest is sent to the memo | sw:639-716; ctl:229-235 |
| Stored flow, packet between phases | the last phase verdict, sticky. Before phase 2 that is the first packet's Pkt_Tree verdict | sw:603, 627 |
| Stored flow after 2048 (result > 50) | frozen at the 2048 verdict. The features stop updating (`result<50` gate) | sw:627 |
| Flow with no storage slot | **Pkt_Tree on every packet** (the fallback). This is the downgrade G1 measures | sw:623, 722-724 |

**Phases.** The phases are {2, 4, 8, 32, 256, 512, 2048} (mr:100; sw:639-702).

**Before the first phase.** A flow's only packet before phase 2 is packet 1, and it always gets the per-packet verdict.

**Confidence rule.** The shipped controller marks a flow determined **only** at the 2048 phase. Its confidence-threshold rule is commented out (ctl:231-232).

**Freeing slots.** An undetermined incumbent loses its slot only after being idle ≥ `timeout_thres` = 256 units of `now_timestamp` (hdr:38; sw:609). One unit is 2^20 ns, so this is about 268 ms. It is also subject to both directions of the wrap noted in §3, including the eviction window every ~4.295 s.

**Slot-model facts the emulator must copy:**
- **Takeover does not refresh the timestamp.** The takeover branch (sw:610-620) does not call `Update_last_classified_timestamp`, which runs only for a packet whose flow hash matches the stored one (sw:626). The newcomer therefore inherits the old owner's `last_classified` value until its own second packet, and during that gap another long-predicted flow can take the slot from it. **INFERRED from code.**
- **Hash collisions go undetected.** Flow identity is only the 32-bit CRC32 hash. The switch compares it with the stored hash (sw:606), and the slot index is the low 16 bits of the same hash (sw:583). Two flows with equal 32-bit hashes share one slot's state undetected: their packets update the same features and read the same verdict.
