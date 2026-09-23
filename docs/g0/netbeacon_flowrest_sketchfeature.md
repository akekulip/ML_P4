# G0 extraction: NetBeacon, Flowrest, SketchFeature

Paths are relative to `third_party/`. Paper cites give section and PDF page. NB = NetBeacon (USENIX Sec '23). FR-ToN = Flowrest ToN 2025 extension (Zenodo 15311319, author copy). SF = SketchFeature (`sf.txt`). **NOT FOUND** means searched in both artifact and paper without a hit. **INFERRED** means derived from code or arithmetic, not stated anywhere.

Compile check (run 2026-09-23, offline, local `bf-p4c 9.13.1`, `--target tofino --arch tna`, output kept in scratchpad; the switch was not touched):

| program | result | stages |
|---|---|---|
| NetBeacon/switch/data_plane/switch.p4 | 0 errors, 15 warnings (14 "no size defined", 1 uninitialised out-param) | 12 (0–11), every stage used |
| Flowrest/P4/Full_version/unibs_flowrest.p4 | 0 errors, 4 warnings | 10 |
| Flowrest conference per-flow / per-packet | 0 errors, 3 warnings each | 12 / 8 |

The switch runs 9.13.2. Whether 9.13.1 results carry over is INFERRED (same minor line).

## NetBeacon (commit 06c6127; shipped config = PeerRush P2P task, 3 classes)

| item | value | cite |
|---|---|---|
| Slots | 65536 per register array; 16-bit index | NetBeacon/switch/data_plane/headers.p4:35-36; NB §7.2 p.12 |
| Per-slot state | 32-bit stored flow hash, 8-bit result, 32-bit last-seen, plus 11 feature registers | switch.p4:20-276 |
| Hash | one `Hash<bit<32>>(CRC32)` with `@symmetric` src/dst addr and port, so both directions share a slot. Index = low 16 bits of the **same** hash, and the collision check compares all 32 bits. No seed or custom polynomial; keying it needs a `CRCPolynomial<>` init value (INFERRED) | switch.p4:16-18, 547, 583, 606 |
| Ways | 1 (direct-mapped) | switch.p4:583 |
| Admission (new flow at an occupied slot) | Takeover only if the Flow_Size_Tree score is >50 **and** `!(result<50 && now−last_seen < timeout)`, i.e. the incumbent is determined (result ≥50) or idle ≥ timeout. Otherwise result=0 and the per-packet fallback runs. Init happens by recirculating to port 68, which rewrites the hash and result registers | switch.p4:606-624, 596-601; NB §5.2 p.9, Alg.1 p.10 |
| Short-flow-predicted flows | Never take a slot, even a free one | switch.p4:608 |
| Timeout | `timeout_thres 256` in units of `global_tstamp>>20` ns = 1.048576 ms, so **≈268 ms** (the comment says "ms", INFERRED correction). The paper gives no value (NOT FOUND) | headers.p4:38; switch.p4:581 |
| Timestamp | `last_classified` is rewritten on **every** packet of the stored flow, so it is really last-seen time. It is **not** refreshed at takeover. Until the new owner's 2nd packet arrives, the slot still carries the old owner's idle time and can be stolen again (INFERRED from code) | switch.p4:259-276, 607, 626 |
| Reclamation | Lazy: a slot is overwritten only when a colliding long-predicted flow arrives. "Determined" = result+50. The shipped controller sets determined **only at the 2048-packet phase**; the confidence threshold line is commented out. So in shipped form, flows shorter than 2048 packets are freed only by timeout | controller.py:229-235; NB App.C p.19 |
| Verdict memo | Digest when result>50 goes to the exact-match `Flow_result` table (size 3000, two entries per flow). The controller does a FIFO: at ≥1500 flows it deletes the oldest 10 | switch.p4:466-480, 713-715; parsers.p4:104-105; controller.py:32, 53-74 |
| Short-flow predictor | XGBoost, 1 tree, 182 leaves (paper: depth 8), on 7 per-packet features. Output `round(sigmoid·100)`; long if **>50**. Labels come from the 80th percentile of flow length, using the first N=7 packets; 82% accuracy | model_generation/models/flow_size_predict_1xgb.txt; tree_to_table/xgb.py:89; switch.p4:438-460, 608; NB §5.2 p.9 |
| Fallback | `Pkt_Tree`: 1-tree RF, depth 9, 387 leaves, 3 classes. Features: proto, total_len, diffserv, ttl, tcp_dataOffset, tcp_window, udp_length. Applied whenever result==0: short flows, denied collisions, and a stored flow's 1st packet | switch.p4:486-504, 722-724; controller.py:254; models/class_pkt_1rf_0.dot |
| Full model | Phases at packets {2,4,8,32,256,512,2048}, with one depth-9 RF tree per phase. Features: pkt size max/min/avg/var_approx, min IPD, bin_3=[48,64) and bin_5=[80,96) counts. Size is zoomed >>2 and variance uses shift approximations, so the emulator must copy the exact integer arithmetic. The P4 also has a 1024 branch, but no 1024 model ships (INFERRED harmless) | model_representation.py:58-100; switch.p4:579, 639-712; NB §7.2 p.12 |
| Training scripts | **NOT FOUND.** Only exported trees ship (README: sklearn 0.24.2, xgboost 1.6.0) | NetBeacon/README.md, model_generation/ReadMe.md |
| Shipped models / tables | `model_generation/models/*.dot` (8 RF) + `flow_size_predict_1xgb.txt`. Compiled tables: `switch/control_plane/{flow_size_and_class_pkt,bin_table_and_class_flow}.pkl`. **Verified**: both pickles load in Python 3.12 (`encoding='latin1'`) and give 182 flow-size, 387 pkt-tree and 1703 flow-tree entries, which fit the P4 sizes 185/390/1710. Emulating full vs fallback offline is feasible at table level | pickles; switch.p4:458, 502, 528 |
| Datasets | Not in repo. PeerRush (3:6:2, 2.57M train / 246k test flows), FacetTraffic+Univ2, MAWI 2020-01-15 + self-made DDoS, ISCXVPN. Where to get PeerRush: NOT FOUND in artifact | NB §7.1-7.3 pp.12-13, Table 4 |
| Published provisioning | IndexSize 16 (65536). High load = median 1555 new flows/s (P2P), 3144 (covert), 13357 (DDoS). **0.85% of flows fall back at high P2P load.** Fig 15d uses 58000 flows on 8192 registers | NB Table 4 p.12, §7.2 p.12, Fig 15 p.14 |
| Prior attack discussion | §8 names "resource exhausting" (DoC) and "low-rate-long-flow" attacks. It argues fallback limits the harm but does not measure it | NB §8 pp.15-16 |
| Target | Tofino-1, 12 stages, 17.29% SRAM, 31.25% TCAM (P2P task). SDE version NOT FOUND. Ports are hard-coded: egress 65, recirc 68 (pipe 0). Registers are per pipe and recirculation always lands in pipe 0, so ingress must be on pipe 0 (INFERRED). The controller imports the **python2.7** bfrt path and needs a python3 path on 9.13 | headers.p4:30-31; controller.py:6; NB §7.2 p.12 |

## Flowrest (commit 13a527c; Full_version = UNIBS-2009, 8 classes)

| item | value | cite |
|---|---|---|
| Slots | 65536; 16-bit index | Flowrest/P4/Full_version/include/types.p4:14,16 |
| Hash | Flow ID from `Hash<bit<32>>(CRC32)`; index from a **separate** `Hash<bit<16>>(CRC16)` (TNA default polynomial). Not symmetric, no seed. The paper's simulator uses crcmod with the TNA constants, but that simulator is **NOT FOUND** in the repo | unibs_flowrest.p4:223-235; FR-ToN §IV-C p.8 |
| Ways | 1 | unibs_flowrest.p4:385 |
| Gate | Only flows **pre-listed** in `flow_action_table` (20000 entries, filled from the test-set 5-tuples with f_action=1) are processed at all. Default miss sets f_action=0 and plain forwarding. As shipped, unseen or spoofed flows never touch the registers. To be a realistic victim, the port must flip the default (INFERRED) | unibs_flowrest.p4:366-377, 388, 484-486; Python/Full_version/generate_table_entries_from_RF.py:322-337 |
| Admission | Empty slot (status 0): take it. ID mismatch: if age < timeout, final_class=255 (unclassified) and a digest **per colliding packet**. Otherwise recirculate via port 68 (pipe bits kept) and re-init | unibs_flowrest.p4:407-436, 238-243 |
| Timeout | `timeout_threshold 512` in units of `global_tstamp[47:20]` ≈1.049 ms, so **≈537 ms** (INFERRED). The paper tunes it per task by simulation | types.p4:17; unibs_flowrest.p4:381; FR-ToN §V p.10 |
| Timestamp | `reg_time_occ` is updated on every packet of the owner (last-seen) | unibs_flowrest.p4:399, 417, 447 |
| Reclamation | Classification happens at packet 3 (`pkt_count==3`) and sends a digest. The controller sets f_action=0 for the flow and **zeroes all 8 registers** at that index (asynchronous). Otherwise the slot frees only by timeout at a collision | unibs_flowrest.p4:450-468; control_plane_unibs.py:120-152; FR-ToN §V-C pp.10-11 |
| Short-flow predictor | **None** (NOT FOUND) | — |
| Fallback | **No model.** Denied flows get no verdict (class 255) and default forwarding. The conference per-packet P4 is a standalone alternative, not a fallback. FR-ToN explicitly contrasts itself with NetBeacon's fallback | unibs_flowrest.p4:425-427; FR-ToN §VII p.15 |
| Full model | 3-tree RF, depth 8, 5 features, 8 classes (verified by loading). P4 feature order: dst port, pkt_len_max, pkt_len_total, 3rd-packet total_len, ack count. Mapping to training column order is INFERRED | Python/Full_version/model_unibs_8_3_5.sav; unibs_flowrest.p4:303-331 |
| Loadable offline? | All three `.sav` fail under sklearn 1.9 (node dtype) and **load under sklearn 1.2.2** (verified with `uv run --with scikit-learn==1.2.2`) | Python/*/*.sav |
| Training | Notebooks need pandas, sklearn, seaborn and CSVs not in repo (`unibs2009_{train,test}_3_pkt.csv`). Runnable once data is fetched (INFERRED) | Python/Full_version/Unibs_flowrest_analysis.ipynb |
| Datasets | UNSW-IoT, IoT-23, ToN-IoT, UNIBS-2009, CICIDS2017 Friday. Train/test CSVs are in the IMDEA Box folder (the link returns HTTP 200; contents not checked) | Flowrest/README.md; FR-ToN §VI-B pp.11-12 |
| Published provisioning | Default 65536. UNIBS with 4096 entries and 1 s timeout gives 0% collisions and 99.4% of flows classified. The paper also says "collision probability close to 0%" in all its cases. HW tests used tcpreplay plus 40 Gbps MoonGen background, which as shipped would miss the gate (INFERRED) | FR-ToN §VII p.13, fn.4 p.10, §VI-A p.11 |
| Target | Tofino-1 (Edgecore Wedge100BF-QS, BFN-T10032Q), **SDE 9.7.0**. Forward port 260 is hard-coded. The controller already handles the python3 path | FR-ToN §VI-A p.11; unibs_flowrest.p4:403; control_plane_unibs.py:9-20 |

## SketchFeature (commit 8fcb53b)

- **Code layout:** `CPU/sketchfeature.py` (86 lines; class with Count-Min sketch plus Bloom filter), `CPU/main.py` (m=3 MB, d=3, BF 2 MB, d_bf=3, 50 bins over 0–1500), and `ML/ML.ipynb` (1-D CNN, TensorFlow 2.11). **No P4 in the repo.** The paper gives only Code 1 (SF App.D p.17).
- **CPU-code defects:**
  - It hashes with Python's builtin `hash()`, which is salted per process, so runs differ unless `PYTHONHASHSEED` is fixed (CPU/sketchfeature.py:15, 25).
  - `ql<<8 + i` parses as `ql<<(8+i)` (lines 13, 23).
  - `decoding` raises an error when the membership test fails (lines 80-86).
- **Data-plane memory and stages:**
  - The P4 prototype uses 3 MB: 1.5 MB Bloom filter and 1.5 MB sketch, which is 35.54% SRAM, **7 of 12 stages**, SDE 9.0.0 (SF App.D p.17).
  - The accuracy evaluation used **6 MB** instead (2 MB Bloom filter). The ~13% F1 drop (DDoS 0.746, botnet 0.715) comes from that 6 MB setting (SF §VI p.12).
  - So the plan's "13% F1, 3 MB, 7 stages" mixes two configurations.
  - Table III and the body text disagree on hash-unit, ALU and TCAM use (19.05 vs 11.11%, 21.43 vs 12.50%, 0.60 vs 0.35%).
- **Hash:** one `hash_function.get({flow_id, ql})`, with 3+3 layers made by **overlapping slices** of one 32-bit value (offsets 0/4/8 and 2/6/10). The algorithm and seed are NOT FOUND. The slices are correlated (INFERRED).
- **Decoding and classification run in the control plane.** There is no per-packet verdict.
- **What baseline 13 would need:**
  - A Python port of the fixed CPU sketch with a fixed hash (for example CRC32 with a salt).
  - A per-window reset policy, which the paper does not specify (NOT FOUND).
  - Decoded histograms mapped to the victim's features. NetBeacon's bin_3/bin_5 need 16-byte bins aligned at 48/80. Max, min, mean and variance are only approximate from histograms. min-IPD needs a second IPD sketch.
  - The victim classifier retrained on decoded features, because the "same classifier" cannot consume raw histograms.
  - Cost charged at 3 MB/7 stages. Accuracy should be quoted at 6 MB, or re-measured at 3 MB.

## Implications for G1/G2

1. **Emulator for NetBeacon.** It can replay the shipped `.pkl` ternary tables directly: feature tables, then the range-mark tree tables. That gives bit-faithful full (Flow_Tree) and fallback (Pkt_Tree) verdicts plus the flow-size gate. It must copy the exact integer feature arithmetic, the CRC32-symmetric index, 256×1.048 ms idle timeout, the "determined only at 2048" rule, the 1500-flow FIFO memo, and the stale-timestamp-after-takeover behaviour. Test these against a trace-driven reference before any attack run.
2. **Missing for NetBeacon:** the PeerRush pcaps and the training scripts. G1 on NetBeacon is limited to the shipped PeerRush models unless PeerRush is obtained. Retraining at other thresholds, or for MAWI/ISCXVPN, needs re-implementation from paper §4/§7 (not the artifact).
3. **Flowrest is a weak C1 victim.** It has no fallback model, so a downgrade means no verdict at all, not a worse one. The gap is full accuracy against a default action. Also, the shipped whitelist gate makes it immune to unseen flows. To use it, the gate default must change, and that change must be stated as our modification. It fits better as a "no-fallback" point in the generality sweep.
4. **Flowrest slot holding is bounded.** Reaching packet 3 frees the slot, so an attacker flow holds a slot for at most about 2×537 ms, and then only through collisions or timeout. Every denied colliding packet also sends a digest, which opens a control-plane load side-channel.
5. **Blocker, kill criterion (h).** NetBeacon already fills all 12 stages on 9.13.1, so the defense cannot sit next to the unmodified P2P build. The fallback is a trimmed-phase build or the BoS host (plan §5 (h)).
6. **Ports for hardware.** NetBeacon needs a python3 controller port, remapped ports, and pipe-0 ingress. Flowrest needs port 260 remapped. Neither needs extern changes to compile.
7. **K1 is realistic.** Both use unseeded default CRCs (NetBeacon: index = low bits of the collision-check hash). The keyed-hash baseline needs a `CRCPolynomial` init or salt, and is cheap to add.
