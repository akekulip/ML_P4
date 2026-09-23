# G0: Brain-on-Switch (BoS, NSDI'24) extraction

Sources: artifact `Brain-on-Switch/` at commit 38aafd9 (paths below are relative to `third_party/`); paper arXiv 2403.11090 (page numbers follow the arXiv PDF). Abbreviations: TB = `Brain-on-Switch/p4/testbed_version/`, NV = `Brain-on-Switch/p4/normal_version/`. NV and TB share the flow manager, hashes, timeout and escalation code; the only differences are the timestamp source, the pipe layout and the statistics counters.

## 1. Flow manager
| Parameter | Value | Source |
|---|---|---|
| Slots | 65,536 (`MAX_FLOW_NUM`), index = low 16 bits of the hash | TB/headers.p4:83-84; TB/prepare.p4:41-42; paper Fig. 8 "Flow Capacity 65536" (p.9) |
| Ways | 1 (direct-mapped). One `r_flow_info` register holds {id, timestamp} | TB/flow_manager.p4:8 |
| Index hash | CRC-32 poly 0x04C11DB7, reflected, **init 0**, xor-out 0xFFFFFFFF, over (sip, dip, sport, dport, proto) | TB/prepare.p4:28-42 |
| TrueID hash | CRC-32C poly 0x1EDC6F41, same init and xor-out, 32 bits | TB/prepare.p4:3-18; paper A.1.4 fn.2 (p.18) |
| Direction | `@symmetric` on the IP pair and the port pair, so both directions of a flow share a slot | TB/prepare.p4:11-12, 36-37 |
| Seed | Compile-time constants only; no control-plane knob. A keyed variant means editing `init` and recompiling | TB/prepare.p4:3-10 (INFERRED from the extern signature) |
| TIMEOUT 3906 | Unit 65,536 ns, so 3906 × 65.536 µs ≈ 256 ms. It is an idle timeout measured from the incumbent's last packet | TB/headers.p4:80-81; paper A.4 (p.21) "256 ms" |
| Clock | TB reads timestamps written into the MAC addresses by the replayer; NV uses `global_tstamp[47:16]` | TB/prepare.p4:53-54; NV/prepare.p4:53-54; paper A.3 (p.21) |

**Claim and free.** `ra_flow_info` (TB/flow_manager.p4:10-30) returns a one-hot predicate:
- 1: same id, live. Refresh the timestamp and run the RNN.
- 2: different id, live. **Collision**; the timestamp is not refreshed.
- 4: same id, idle for more than 256 ms. Reset the flow state.
- 8: different id, idle for more than 256 ms. **Replace** the incumbent.

Slots are never freed explicitly. A slot is reclaimed lazily by the first new flow that hashes to it once the incumbent has been idle for 256 ms. Every incumbent packet refreshes the timer, so an incumbent that sends one packet every <256 ms holds its slot indefinitely. On a timeout the per-flow counters, the ambiguity counter and the escalation flag reset (TB/pkt_cnt.p4:28; TB/ambiguous_cnt.p4:19,27; TB/BoS_testbed.p4:168-171). The arithmetic is unsigned 32-bit on `ts[47:16]`, so it wraps after about 78 h (INFERRED).

## 2. Collision handling
- **Global packet counter.** `r_ig_global_pkt_cnt[7:0]` counts every IPv4 ingress packet, recirculated ones included, and wraps every 256 (TB/ig_global_cnt.p4:8; TB/BoS_testbed.p4:138).
- **`tab_global_collision_escalation_threshold`.** 256 exact entries (TB/ig_global_cnt.p4:21). They are installed by `setup_threshold()` as `threshold(i) = floor(i × 0.05)` for i = 0…255 (TB/setup/setup_threshold.py:44-47), with `collision_escalation_ratio=0.05` (TB/setup/setup_all.py:29).
- **Budget register.** For a colliding packet (predicate 2), if `cnt < threshold(i)` the packet goes to IMIS and `cnt++`. Otherwise `cnt` is clamped to the threshold and the packet goes to the per-packet tree (TB/ig_global_cnt.p4:30-45; TB/BoS_testbed.p4:192-200). The clamp at i ∈ [0,19] (threshold 0) **resets the budget every 256 packets**.
- **Resulting fraction.** In every 256-packet window at most 12 colliding packets go to IMIS, paced at one new slot per 20 packets. The code therefore implements **5% of all packets**, per packet, not 5% of colliding flows. One colliding flow can be split between IMIS and the tree. The paper instead describes "IMIS (3%) / (5%)" as the percentage of *flows* without storage (p.11, Figs. 11-12). The **published default is fallback to the per-packet tree** (p.11 "default handling"; `fall_back_to_imis=0.0` in `Brain-on-Switch/model/opts.py:58`).
- The paper states the flow manager is deployed in ingress only; the egress-collision corner case is not handled (A.1.4, p.18).

## 3. Escalation
- **Ambiguity** (Alg. 1, p.6; A.2.1, p.19). CPR_c is the sum of 4-bit quantized probabilities over the windows since the last reset. The reset period is K=128 (TB/classify.p4:2-21, 34; `cpr_reset_period=128`, TB/setup/setup_threshold.py:8). A packet is ambiguous when the argmax class has `CPR < (i+1)·T_conf[c] − 1`. The threshold table is installed at TB/setup/setup_threshold.py:30-34, and the check is TB/BoS_testbed.p4:323-326.
- **Per-class T_conf and dataset T_esc.** These are read from `install/threshold.json` (TB/setup/setup_threshold.py:13-21), produced by `translate_threshold.py` from `p4/parameter/<ds>/threshold.json`. **NOT FOUND: neither file is shipped, and no script generates it.** The notebook `model/model_convertion.ipynb` emits the embedding, GRU and output tables only.
- **T_esc.** `act_t_esc(60)` is only the P4 default (TB/ambiguous_cnt.p4:10); the controller overwrites it. The counter never decays; it saturates and resets only on timeout. It fires when `ambiguous+1 ≥ T_esc` (TB/ambiguous_cnt.p4:17-32). The paper's example sweeps T_esc from 12 to 22 for ISCXVPN VoIP and picks the value that keeps escalations at **≤5% of flows** (Fig. 4, p.6). The per-dataset values are NOT FOUND.
- **Mechanics (TB).** In pipe B egress, the first packet with `need_escalation` sets an E2E mirror (TB/BoS_testbed.p4:329-335) to session 4+pipe, which goes to recirculation port 68+128·pipe (TB/setup/setup_mirror.py:12-27). AuxEgress tags it with EtherType 0xFFFF (TB/BoS_testbed.p4:374-376). On re-entry the parser sets `new_escalation_flag=0xFF` (TB/parsers.p4:97-99), ingress writes the flag and drops the copy (TB/BoS_testbed.p4:165,174-180). Later packets carrying the flag are forwarded to **escalation_port 28**; normal traffic goes to port 24 (TB/setup/setup_forward.py:12-30). The ternary entries have no explicit priority (INFERRED ambiguity). The packet that triggers escalation is itself not diverted.

## 4. Pre-analysis window
`pkt_cnt_initial_8` reads 0…6 for the first 7 packets and saturates at 7 (TB/pkt_cnt.p4:26-35). The RNN runs only when it equals 7 (TB/BoS_testbed.p4:187-188). The paper says these packets receive no verdict (A.1.6, p.19). In code they are forwarded to the normal port, but egress still runs the per-packet tree: TB writes the tree's class to `aux_md.pred` (TB/BoS_testbed.p4:338-348), and NV writes it to DSCP (NV/BoS_normal.p4:341). The statistics log them as "pre-analysis" (TB/BoS_testbed.p4:407-409).

## 5. Models
| Model | Shipped? | Retrain |
|---|---|---|
| Binary GRU RNN: S=8, embedding 10/8/6 bits, hidden bits 9/8/6/5 (p.9 Table 2; `model/opts.py`) | **Checkpoints yes**: `Brain-on-Switch/model/save/{ISCXVPN2016,BOTIOT,CICIOT2022,PeerRush}/brnn_*/brnn-best` (PyTorch zip). **Table entries no**: `p4/parameter/` and `install/` are absent | Convert with `model/model_convertion.ipynb` and then `TB/translate/translate_all.py`. Training: `model/train.py` (torch, timm-free) |
| Per-packet RF, 2 trees of depth 9 (A.1.5, p.19; `PerPacket/opts.py:2-3`) | **No.** `TB/per_packet.p4` is NetBeacon's example (line 2), and `TB/setup/install_per_packet_entry.py` is empty (line 15) | `PerPacket/train.py` (sklearn). The P4 encoding must be regenerated with NetBeacon's coder |
| IMIS: YaTC transformer, first 5 packets × 320 B (p.8) | **No.** The pretrained model is on Google Drive (`IMIS/YaTC/README.md:9`); no fine-tuned model is shipped | `IMIS/YaTC/finetune.py` on the escalated training flows. Needs timm, a GPU (`device='cuda'`, line 49), and MFR images |

**Anomalies.**
- The ISCXVPN checkpoint directory is named `…_single_…` (the L2 loss), while Table 2 says L1.
- `dataset/CICIOT2022/labels.json` duplicates the ISCXVPN labels, whereas the paper uses the 3 classes Power/Idle/Interact (p.8).
- The training IPD unit is 0.1 ms with a vocabulary of 2561 (`model/utils/data_loader.py:27`). The switch uses 16,384 ns bins (TB/embedding.p4:27), remapped by `translate_embed.py`.
- **No simulator is shipped.** `simulation_opts` is defined but unused (`model/opts.py:49-62`); the paper's simulator (p.11) is unreleased.

**Offline emulation of full vs fallback.**
- *Full:* feasible now. Load `brnn-best` into `model/model.py` on CPU and re-implement the P4 aggregation (floor(p·16), K=128, T_conf, T_esc).
- *Fallback:* the per-packet RF must be retrained. It is cheap.
- *Thresholds:* T_conf and T_esc must be re-derived from `aggregator.py`'s confidence CDF under the ≤5% rule.
- *IMIS:* optional. It needs YaTC fine-tuning on the RTX 2070 on this host.
- *Data:* all of it needs the processed `json/` from Drive.

## 6. Datasets
- **Download.** All four ship as `source/`, `pcap/` and `json/` in one Google Drive folder (`dataset/README.md:2`). Sizes: **NOT FOUND** (Drive not queried).
- **Flow counts** (p.9 Table 2, p.21-22):

  | Dataset | Train/test flows | Classes (flows per class) |
  |---|---|---|
  | ISCXVPN2016 | 7801/1951 | 6 |
  | BoT-IoT | 7835/1961 | 353/427/1593/7423 |
  | CICIoT2022 | 5332/1335 | 1131/4382/1154 |
  | PeerRush | 30770/7694 | 20919/9499/7846 |

- **Short flows are excluded.** Flows are split at 256 ms idle gaps, and flows with **fewer than 8 packets are discarded** (`dataset/pcap2json.py:28`; `PerPacket/train.py:23`).
- **Attack classes (H4).** Only **BoT-IoT** has them: DataExfiltration, Keylogging, OSScan and ServiceScan, and there is **no benign class** (`dataset/BOTIOT/labels.json`). **CICIoT2022 in BoS is device-state classification, not attacks** (p.8). Per-flow pcaps are included in `pcap/`.

## 7. Published provisioning and rates
- **Load.** 65,536 slots and a 256 ms timeout, with loads of 1000/2000/4000 new flows/s (p.9 Table 2). The testbed stress test reached 450k flows/s (p.9), and the simulation reached 7.8 M flows/s at 1.6 Tbps, with an 11.6% F1 drop (p.11).
- **Per-packet fallback at 2000 flows/s.** 2.77/1.43/2.05/5.22% of flows (p.9).
- **Escalation.** ≤5% of flows (p.6, Fig. 9 p.11).
- **Fallback accuracy.** Per-packet model accuracy 0.596/0.327/0.759/0.684 (Table 2). BoS macro-F1 at normal load: 0.925/0.974/0.925/0.937 (Table 3, p.10).
- **Collision counts.** No absolute collision counts are reported.

## 8. Target and toolchain
- **Paper target.** Wedge 100BF-32X, 2 pipes, SDE 9.7.0 (A.3, p.20; `p4/README.md:13`). The compiler's `.conf` is hand-edited because the switch has only two pipes (the edit itself is not shipped).
- **TB layout.** A twisted two-pipe design: `Pipeline(SwitchIngress, AuxEgress) pipe_a` and `Pipeline(AuxIngress, SwitchEgress) pipe_b` (TB/BoS_testbed.p4:445-463). **Every packet recirculates once** through pipe 1's port 196 (TB/headers.p4:86; TB/BoS_testbed.p4:128).
- **NV layout.** A single pipe, `Switch(pipe) main` (NV/BoS_normal.p4:359). Only the mirrored escalation copies recirculate.
- **Stage use** (Fig. 8, p.9): all 12 ingress stages and egress stages 0–9. SRAM 18–23%, TCAM 0.7–1.7% (Table 4, p.10).

**Port to the UfiSpace S9180-32X with SDE 9.13.2.**
- **Pipe layout.** Port **NV, not TB**: it needs no `.conf` surgery and no pipe-1 ports. Vision and Hulk sit on dev ports 8–10, all in pipe 0 (`hw/README.md:7`). The mirror session must target pipe-0 recirculation port 68.
- **Pipe count.** The S9180-32X pipe count is INFERRED to be 2. Check it on the switch with `bfrt.tf1.device_configuration`.
- **Timestamps.** Use NV's `global_tstamp`. Otherwise the replayer must write timestamps and labels into the MACs (`src[2:0]` = label, TB/BoS_testbed.p4:124).
- **Externs.** CRCPolynomial `Hash`, `this.predicate` and saturating ops are all still present in TNA (INFERRED; unverified until the G4b compile). The `@stage` pins may need to move.
- **Control plane.** The control plane is TB-only `bfrt_python` (`bfrtcli`). NV has **no control plane**, so the mirror, forwarding and threshold scripts must be rewritten.
- **Co-residence.** BoS uses all ingress stages, so it cannot co-reside with MVM. It requires the snapshot/restore displacement.

**IMIS.**
- **Stack.** DPDK 20.11.9, PcapPlusPlus 22.11 patched for 64 lcores, libtorch 2.0.1+cu117 (`IMIS/system/README.md:7-14`). The paper setup used an A100 and CUDA 11.7 (p.8, p.20). The config expects about 33 cores and a 33 M mbuf pool (`configTemplate.json`).
- **CPU stand-in.** The analyzer has `#ifdef CUDA` paths (`IMIS/system/commune/analyzerWorker.cpp:46-52,122-126`). However, the warm-up at line 141 is hard-wired to `kCUDA`, and `CMakeLists.txt:3` declares `project(IMIS CXX CUDA)`, so both need patching. A labelled CPU stand-in on Hulk only needs YaTC inference on the first 5 packets, which is simpler as a Python or C service fed by `hw/hulk_backend.c`.

## Implications for G1/G2
1. **Emulator core.**
   - One-way table of 65,536 slots, CRC-32(init 0) index and CRC-32C id, symmetric, 256 ms idle replacement, no explicit free.
   - Per-packet collision budget: 5% of all packets per 256-packet window, then fallback to the tree.
   - 7-packet pre-analysis, K=128, non-decaying T_esc.
   - The exact behaviour of bf-p4c `@symmetric` is unknown: normalize the endpoint order and validate against hardware in E6.
2. **Missing pieces to build:**
   - T_conf and T_esc per dataset, re-derived under the ≤5% rule;
   - the per-packet RF;
   - P4 table entries (from the notebook);
   - the NV control plane;
   - YaTC fine-tuning (optional in G1; IMIS is out of scope).
3. **G1 population caveat.** The datasets drop flows shorter than 8 packets, so population (i) (short, late flows) must come from the raw `pcap/` or `source/`, or from MAWI. On those flows BoS's fallback is the per-packet tree, or the pre-analysis window.
4. **H4 blocker.** Only BoT-IoT has attack classes, and it has no benign class. CICIoT2022 is not an attack set. H4 needs TON_IoT pcaps or a benign mix, and the plan text for H4/H1 ("BoT-IoT / CICIoT2022 attack classes") must be corrected.
5. **Immediate action.** Fetch the Drive `json/` and `pcap/` directories and record their sizes. The G1 downgrade gap is RNN (shipped) vs retrained RF.
