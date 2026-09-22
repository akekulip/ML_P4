# Research findings (2026-09-22)

Three agents checked the brief before any code was written: datasets, toolchain, and prior work.
The facts below are sourced. Items marked *unverified* still need a local check. Every item a
check resolves gets updated in place.

## 1. Datasets

### TON_IoT (UNSW Canberra, Moustafa)
- **Access and license:** https://research.unsw.edu.au/projects/toniot-datasets. Direct browse from UNSW SharePoint, with no form. Free for academic use; the 8 listed papers must be cited; commercial use needs permission.
- **Train_Test_Network.csv:**
  - 461,043 rows: 300,000 normal and 161,043 attack (arXiv 2007.05922).
  - Per class: 20,000 each of backdoor, ddos, dos, injection, password, ransomware, scanning and xss; mitm has 1,043 (arXiv 2212.13994, Table 1).
  - 44 columns: `src_ip, src_port, dst_ip, dst_port, proto, service, duration, src_bytes,
    dst_bytes, conn_state, missed_bytes, src_pkts, src_ip_bytes, dst_pkts, dst_ip_bytes, dns_query,
    dns_qclass, dns_qtype, dns_rcode, dns_AA, dns_RD, dns_RA, dns_rejected, ssl_version, ssl_cipher,
    ssl_resumed, ssl_established, ssl_subject, ssl_issuer, http_trans_depth, http_method, http_uri,
    http_version, http_request_body_len, http_response_body_len, http_status_code, http_user_agent,
    http_orig_mime_types, http_resp_mime_types, weird_name, weird_addl, weird_notice, label, type`.
    Source: the Hugging Face mirror `codymlewis/TON_IoT_network`.
  - **No `ts` column** (strongly indicated; *confirm with `head -1` on the official file*). It is a class-balanced sample, so it is almost certainly not in time order. **Use: training and tuning only.**
- **Full processed network dataset:**
  - About 21.98M Zeek flows, 45 features including `ts`.
  - Per class: benign 788,599; scanning 7.14M; ddos 6.17M; dos 3.38M; xss 2.11M; password 1.37M; backdoor 508k; injection 453k; ransomware 72.8k; mitm 1,052 (arXiv 2212.13994).
  - *Unverified:* the file count (reportedly 23) and whether each file is sorted by `ts`. Plan: concatenate, then sort by `ts` ourselves. **Use: the chronological replay stream.**
- **Known problems** (arXiv 2212.13994):
  - Duplicate flows carry different attack labels.
  - Traffic leaving the testbed is labeled as attack.
  - Normal exchanges with 192.168.1.1 (router/DNS) are labeled as attack.
  - They proposed filters giving "ToN-IoT-R" (18.9M flows).
  - The attacker hosts are 192.168.159.30–39, so IPs and ports leak the label.
- **Consequence for MVM:** the attack classes were run on separate days (NF-v3 paper). Leaf drift will therefore arrive in class-sized blocks, and floods (scanning plus ddos, about 13M) will dominate. Report per-phase and benign-only windows so the reported locality is not an artifact.

### NF-ToN-IoT (UQ, Sarhan/Luay) — https://staff.itee.uq.edu.au/marius/NIDS_datasets/

| Version | Features | Flows | Timestamps |
|---|---|---|---|
| v1 | 12 | 1.38M | none |
| v2 | 43 | 16.94M | none |
| v3 | 53 | 27.52M | `FLOW_START_MILLISECONDS`, `FLOW_END_MILLISECONDS` and IAT features (arXiv 2503.04404) |

- **Use:** v3 as a stretch cross-check.

### IoT-23 (Stratosphere) — https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/
- Full archive with pcaps is 20 GB. The small archive (labeled `conn.log` files only) is 8.7 GB. Scenarios can also be downloaded individually.
- Small verified scenarios: 34-1 (23,145 flows) and 44-1 (237 flows). **Dropped from scope** for time.

### Chronological-evaluation references
- TESSERACT reassessment: arXiv 2506.23814
- Time-aware NIDS taxonomy: arXiv 2511.03799

## 2. Toolchain

**Local environment**

| Component | Status |
|---|---|
| bmv2 1.15.0 (`simple_switch`, `simple_switch_grpc`) | installed |
| p4c 1.2.4.2 (`p4c-bm2-ss`) | installed |
| Mininet (`/usr/local/bin/mn`) | installed |
| P4Runtime protos (`/usr/lib/python3/dist-packages/p4/v1/`), grpcio 1.70, protobuf 3.20.3, scapy 2.4.3 | installed in system Python |
| `p4runtime_sh` | **missing** |
| Docker | installed, but the socket gives permission denied |
| `~/.venvs/research` (py3.12) | sklearn 1.9.0, pandas 2.3.3, numpy 2.3.5, scipy 1.16.3, matplotlib 3.11.0 |
| Disk | 1.2 TB free |

### Planter (Apache-2.0, v0.1.0) — https://github.com/In-Network-Machine-Learning/Planter
- **Decision: not used.**
- Its DT Type_EB mapping has per-feature ternary code tables, then an exact-match code table. `generate_code_table_for_path()` takes the cartesian product of codes, so **one leaf becomes many entries**. That breaks "one leaf = one page".
- It has no miss-to-controller path, and its model is static.

### Chosen route: one range-match entry per leaf
- **Table:** `leaf_tbl { key = { f1: range; …; fN: range; } actions = { set_class; to_cpu; } default_action = to_cpu; }`. Features a path never tests get the full range.
- **Why no priorities or dependencies:** leaves of one tree are disjoint boxes that together cover the whole feature space, so a constant priority is enough. This does not hold for random forests.
- **BMv2 behavior:** range lookup is a linear scan. Its throughput baseline is about 80 kpps.
- **Miss path:** P4Runtime packet-in (`--cpu-port`, `@controller_header("packet_in")`). The controller computes the verdict and installs the leaf. Alternatives: a digest, or clone-to-CPU.
- **Write rate:** no published figure for BMv2; we measure it. Tofino bfrt measurements (arXiv 2501.17271):

  | Controller | Entries/s |
  |---|---|
  | Python, single entry per request, local | 746 |
  | Python, single entry per request, remote | 553 |
  | RBFRT, batched | about 50k |

### Tofino-1 (future work only)
- A range key is limited to about 20 bits per table, so features must be quantized to 4–8 bits or the table split.
- A learn digest is limited to 48 bytes.
- A stateful action cannot be the default action.
- Shared-chip rules apply: `gc-switchd` must be stopped and masked, and `bf_switchd` restarts need Philip's approval.

## 3. Prior work and novelty

| Work | Venue | Relevance |
|---|---|---|
| IIsy | arXiv 2205.08243; IEEE/ACM ToN 2024 | Closest: a small model on the switch, a large model on a backend, table-based updates. The switch holds a whole small model, not a traffic-driven cache of the big one. |
| NetBeacon | USENIX Security'23 | Multi-phase early exit plus per-packet fallback. |
| Leo | NSDI'24 | Runtime-reprogrammable decision trees at Tbps on Tofino; swaps whole models. |
| Henna | NativeNI@CoNEXT'22 | Cascaded in-switch trees. |
| SpliDT | SIGCOMM'25 | Splits trees into subtrees structurally, not by popularity. |
| Planter | arXiv 2205.08824 | Model-to-switch mapping framework. |
| Mousika | INFOCOM'22 | Model-to-switch mapping framework. |
| Cruise Control | arXiv 2412.15146 | Picks among whole models online. |
| CacheFlow | SOSR'16 | Caches popular rules in TCAM with the rest in software, but needs dependency handling. |
| CAB | HotSDN'14 | Same caching problem, handled with buckets. |
| PACSET | arXiv 2011.05383 | Lays out tree nodes by leaf cardinality (static, offline). |
| Gupta & Johnston | SysML'18 | "Cache-friendly decision trees": reorders nodes by branch skew. |
| Forest Packing | arXiv 1806.07300 | Node layout by traversal frequency. |
| Clipper | NSDI'17 | Prediction memoization. |
| Tahoe | EuroSys'21 | GPU tree-inference layout. |
| QuickScorer | SIGIR'15 | Fast tree-ensemble scoring. |
| Denning | CACM 1968 | Origin of the working-set concept (cite from standard knowledge). |

- **Already done:**
  - trees on switches;
  - switch+backend hybrids;
  - early exit;
  - model updates through table writes;
  - rule caching with a controller;
  - tree layout by leaf popularity.
- **Gap MVM-Lite occupies:**
  1. Measuring leaf-level locality (top-K coverage, W90, entropy, reuse distance, drift) under chronological traffic.
  2. Tree depth and pruning as an accuracy-vs-cacheability trade-off.
  3. Leaf-granularity cache policies compared against static top-K and an oracle, made simple by the disjointness of leaves.
- **Safe framing:** a measurement study plus simulation that applies SDN rule-caching ideas to in-network decision-tree inference.
- **Do not claim:**
  - "first partial model offload";
  - anything about line rate;
  - Tofino results, unless they were measured.
- **Must-cite:** IIsy, NetBeacon, Leo, CacheFlow (+CAB), PACSET/Clipper.
