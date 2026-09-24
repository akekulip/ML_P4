# MORNING SUMMARY / STATUS (updated during the 2026-09-24 overnight run)

Plan: `/home/philip/.claude/plans/write-this-down-and-snappy-spindle.md` (section "8-hour autonomous run"). Rules: commits only as akekulip, no trailers, no push, nothing on the switch.

## Hurdles (symptom, cause, fix, file)
- Report script took 25 min and timed out: flow bootstrap recomputed confusion sums per replicate -> precompute weighted totals once per run (`scripts/g5_peerrush_report.py`).
- D1 looked worse under attack on PeerRush: not a bug; the wrap window incidentally evicts holders (d1w alone causes it). MAWI split shows D1 near-neutral there (`docs/results_g4a_d1parts.md`).
- MAWI D1-parts report showed only the replication day: filter `"_p_" not in name` also matched the day letter -> regex on the file suffix (`scripts/g4a_d1parts_report.py`).
- `test_dgrade_targeted` failed after adding `Attack.slot2`: `TargetedAttack(..., failed)` was positional -> keyword call (`src/dgrade/inject_targeted.py`).
- Own new test wrong (flow 2 took table A slot, not B) -> test corrected (`tests/test_dgrade_twoway.py`); emulator behaviour was right.
- Code review: D4 holders were not paired with the one-table draw -> slots2 drawn last in `build_fill`; guard against identical hashes in both tables.

# WORKING_NOTES — MVM-Lite (ML class project)

## Task
Graduate ML class project: *MVM — Workload-Adaptive Virtual Memory for Decision-Tree Inference*.
Measure decision-tree inference locality under chronological network traffic, the trade-off
between accuracy and cacheability, and adaptive leaf caching (K pages in the switch, misses go to
the backend). The P4/BMv2 part is the deployment proof.
- Brief: `docs/brief.md`
- Research: `docs/research_findings.md`
- Full plan: `~/.claude/plans/write-this-down-and-snappy-spindle.md`

## Decisions (Philip, 2026-09-22)
- Train and tune on TON_IoT `Train_Test_Network.csv`. Freeze the model. Replay the full
  processed network set sorted by `ts`, with rows that overlap Train_Test removed.
- Python is the must tier, BMv2 the should tier, Tofino is future work (write-up only).
- Timeline: about 7 weeks, due early to mid November 2026.
- Do not use Planter. Use a hand-written range-match table with one entry per leaf.
- Leave IPs and ports out of the main feature sets; add them back only as an ablation.
- Framing: a measurement study plus simulation. Make no novelty or line-rate overclaims.

## Milestones
- [ ] **W1:** repo, uv env, data download, check ts/order/overlap, locality pilot (DT depth 8, C(32)) — go/no-go
- [x] **W2 (done 2026-09-22, stand-in training pools):** RQ1 — LR/DT/RF, depth and ccp sweep, metrics with bootstrap CIs, feature ablations
- [x] **W3 (done 2026-09-22 21:51, stand-in pools):** RQ2/RQ3 — locality metrics, Pareto frontier of F1 vs W90, drift (JS), shuffled vs chronological, per-phase windows
- [x] **W4 (done 2026-09-22 22:00, stand-in pools):** RQ4 — cache simulator (static, LRU, LFU, decayed-LFU, oracle), K sweep, recovery time, regret, churn
- [x] **W5 (done 2026-09-22):** BMv2 — mvm.p4, controller, write-rate measurement, fidelity
- [x] **W6 (done 2026-09-22; NF-ToN-IoT-v3 stretch NOT done):** BMv2 end-to-end replay and latency (labeled "BMv2 ≠ ASIC"); NF-ToN-IoT-v3 cross-check as stretch
- [x] **W7 (done 2026-09-22):** report and slides
- [x] **W8 (done 2026-09-23):** MVM on the real Tofino-1 with Vision and Hulk, compared with CPU-only

## Status (2026-09-22)
- Repo created (local git on `main`, no remote).
- Saved the brief, the research findings and these notes.
- uv env `.venv` (py3.12, sklearn 1.9.1, pandas 3.0.6, pyarrow 25).
- Core modules built test-first at the three agreed seams. `uv run pytest`: **21 passed**.
  - `src/mvm/leaves.py`: tree → disjoint leaf boxes; `lookup` equals `tree.apply` exactly, including on-threshold samples (float32 cast mirrored).
  - `src/mvm/locality.py`: C(K), W_q, normalized entropy, reuse distance (Fenwick tree), windowed JS.
  - `src/mvm/cache.py`: LRU, LFU, DecayedLFU, StaticTopK, WindowOracle, Belady.
- **Plan correction:** the brief's "oracle" (each window's top-K) is not an upper bound, because
  LRU can adapt inside a window. Belady MIN with bypass was added as the provable offline bound.
  Tests assert Belady ≥ LRU, LFU and DecayedLFU.
- **Speed on 1M synthetic Zipf requests, K=256:**

  | Run | Time |
  |---|---|
  | LRU | 0.2 s |
  | LFU | 8.8 s |
  | DecayedLFU | 12.8 s |
  | Belady | 1.1 s |
  | reuse distance | 6.3 s |

  At 22M that is about 3–5 minutes per LFU-family run, so the full sweep uses windows (or numba LFU).
- **Data (2026-09-22):** `Processed_datasets.zip` holds 23 network CSVs; the zip tested OK and
  they are extracted to `data/raw/network`, then converted to `data/processed/network/*.parquet`
  (`experiments/w1_data_audit.py`).
  - 22,339,021 rows, 46 columns including `ts` (1 s resolution, only 392,633 distinct values, so ties are heavy).
  - The files are contiguous in time and in order. There are only 21 within-file backsteps, fixed by a stable sort on `ts`.
  - 869 malformed rows (`src_bytes` = "0.0.0.0", all normal) are dropped.
  - Counts: normal 796,380 (3.6%), scanning 7.14M, ddos 6.17M, dos 3.38M, xss 2.11M,
    password 1.72M (the literature says 1.37M, so this differs), backdoor 508k, injection 453k, ransomware 72.8k, mitm 1,052.
  - Attacks come in day blocks:

    | Days | Traffic |
    |---|---|
    | 04-02..04 | normal only |
    | 04-23 | scanning |
    | 04-24 | scanning + dos |
    | 04-25 | ddos + dos + injection |
    | 04-26 | ddos + password |
    | 04-27 | password + xss |
    | 04-28 | backdoor + ransomware |
    | 04-29 | backdoor + mitm |

    These are natural phase shifts for RQ4.
  - **Still missing:** `train_test_network.csv`. The SharePoint throttling stub is still in Train_Test_datasets.zip.
- **PROVISIONAL pilot** (`w1_pilot.py`, `w1_depth_probe.py`). The tree is trained on a ≤20k-per-type
  stratified sample of the full set, those rows are removed from the replay, features are the
  data-plane set with no IPs or ports, and the stream is replayed in time order:

  | depth | leaves | macro-F1 | W90 | W99 | benign W90 | LRU K8 | benign LRU K8 |
  |---|---|---|---|---|---|---|---|
  | 4 | 16 | .876 | 2 | 9 | 8 | 1.000 | .998 |
  | 8 | 124 | .921 | 3 | 25 | 24 | .994 | .917 |
  | 12 | 319 | .949 | 11 | 58 | 46 | .977 | .825 |
  | 16 | 552 | .958 | 15 | 87 | 55 | .969 | .806 |
  | None | 789 | .959 | 21 | 122 | 56 | .956 | .804 |

  - H1 holds: at depth 8, one leaf serves 85% of the stream. H2's shape holds too: F1 rises while the working set grows, with a knee around depth 12–16.
  - The full stream is **flood-dominated and trivially cacheable** (K=32 LRU ≥ 99%).
  - Capacity matters only for **small K (≤16)** and the **benign-only** stream.
  - LRU beats the window oracle at every K, which confirms the Belady correction.
  - Adjustments proposed:
    1. Change the K grid to {1,2,4,8,16,32,64}.
    2. Report every result on three streams: full, benign-only, and a flood-thinned or per-phase stream.
    3. Headline the benign and small-K regime.
- First commit made in Philip's name only (no co-author lines, ever).

## Methodology review (research-scientist agent, 2026-09-22) — adopted
- **B1, duplicate leakage.** 59% of IID-test rows exactly matched a training feature vector
  (ransomware 99.8%). Fix: **grouped split**, where each distinct data-plane vector is hashed to
  exactly one pool (60/20/20). Measured afterwards: 0.5% seen.
- **B2, closed-world replay.** Fix: a **forward** split, where pools come only from the first half
  (by ts) of each local day and the replay covers the second halves.
  - Injection lies entirely in the second half of 04-25, so forward mode is an **unseen-attack**
    test for injection.
  - Password lies almost entirely in first halves.
- The **random** split is kept only to quantify the inflation.
- **Days are Canberra local time** (Australia/Sydney). The phases get cleaner that way:

  | Days | Traffic |
  |---|---|
  | 04-23..24 | scanning |
  | 04-25 | dos + injection |
  | 04-26 | ddos |
  | 04-27 | password + xss |
  | 04-28 | ransomware + backdoor |
  | 04-29..30 | backdoor + mitm |

- **Other changes adopted:**
  - Categoricals are coded by training attack-rate rank.
  - Added an HGB baseline and an always-attack baseline.
  - Per-type recall is recorded.
  - Seen vs novel test vectors are reported separately.
  - A Bayes ceiling is computed.
  - Pools are capped at 50% of a class (mitm).
  - Every seed is replayed; counts are kept per hour × type for a block bootstrap.
  - The primary interval is mean ± sd over seeds.
  - IID metrics are also reweighted to the stream's class mix.
- **Deferred to W3/W4:**
  - replay-order robustness (file order, within-second shuffle, flow-end time `ts+duration`);
  - static top-K warm-up taken from the stream, not the training mix;
  - removing Train_Test rows from the replay as a multiset once that file arrives (it has no ts or row id).
- **W1 pilot table above is NOT comparable to W2.** The pilot used `service`, 20k normal rows, a
  random split and UTC days.
- **First signal (grouped, seed 0, val).** Once duplicates are removed, deeper DTs do worse:
  depth 6 scores 0.958 and unlimited depth 0.910. LR is weak on novel benign vectors (0.55).
  Confirm on the test set across all seeds.

## W2 results (2026-09-22) — full tables in `docs/results_w2.md`
- **Leakage is large.** IID macro-F1 with data-plane features: random vs grouped split for each model

  | Model | random | grouped | inflation |
  |---|---|---|---|
  | RF | .967 | .894 | +.074 |
  | DT | .967 | .910 | +.057 |
  | HGB | .962 | .925 | +.037 |
  | LR | .866 | .860 | +.006 |

- **H2 is an artifact of leakage.** On the random split, macro-F1 rises monotonically with depth
  (.863 → .967). On the grouped split it peaks at depth 10 (.929, 439 leaves); ccp pruning reaches
  about .93 at roughly 100 leaves, and unlimited depth falls back to .898 (1,944 leaves). On novel
  vectors, small trees win on both accuracy and cacheability.
- **Best models, grouped data-plane features:**
  - HGB .925;
  - DT: val-selected depth 6 scores .910, and depth 10 scores .929;
  - Bayes ceiling .958.
  - Zeek fields add about +.01. Ports lift DT to .968, and IPs plus ports reach .9999 (topology memorization).
- **Forward (temporal) split:**
  - Replay macro-F1: DT d12 .851 [.761, .935], RF .853, always-attack .491.
  - **Injection is unseen in training** and is still detected at recall .64–.74.
  - mitm recall is .40–.51 (172 training rows).
  - Seed variance is high at depth 10 and 12 (sd up to .057).
- **Replay vs IID.** The stream is 96% attack, so benign precision drags macro-F1 down: grouped
  replay DT is .72–.78 against .91 IID. Reweighting IID per-type recall to the stream mix predicts this (.73).
- **Weak classes.** Ransomware recall is .29 (grouped DT) and mitm .57. In the 10-class
  task, ransomware is almost never identified (.008) and scanning is .64.

## W3 results (2026-09-22) — full tables in `docs/results_w3.md`
- **Working set grows with tree size.** Grouped split, data-plane DTs, 5 seeds, mean values:

  | depth | leaves | full W90 | benign W90 |
  |---|---|---|---|
  | 4 | 16 | 4 | 8.8 |
  | 6 | 61 | 6.2 | 14.6 |
  | 10 | 439 | 12.8 | 30.6 |
  | None | 1,944 | 26 | 46 |

- **H2 as revised holds.** Depths 4, 6, 8 and 10 are Pareto-optimal on macro-F1 against benign W90.
  Depths 12, 16 and None are **dominated**: they are both less accurate and less cacheable. This holds for
  grouped and forward splits alike.
- **Attacks are cache-friendly; benign traffic sets the table size.** W90 per type at depth 10:

  | type | W90 |
  |---|---|
  | backdoor | 1 |
  | dos | 1 |
  | scanning | 3.8 |
  | xss | 4.2 |
  | password | 5 |
  | ddos | 7 |
  | normal | 30.6 |
  | mitm | 35 (n=527) |

- **An online cache beats the best static table.** At depth 10 with K=8:

  | stream | LRU | best fixed table in hindsight, C(8) |
  |---|---|---|
  | full | .978 | .826 |
  | benign | .870 | .584 |

  The traffic has temporal locality beyond raw frequency, because the attack phases shift.
- **Ordering robustness (methodology review M4).**
  - File order and a within-second shuffle are identical.
  - Flow-end order raises only small-K hit rates (full stream, K=1: .58 → .81).
  - All orderings converge by K=8, so conclusions for K≥8 hold under every ordering.
- **Engineering note.** The earlier multi-hour W3 attempts were pure resource failures: a fork deadlock
  and OOM kills leaving the Pool hung. With per-process units (`experiments/overnight.sh`) and category
  codes, one unit takes about 5 minutes at a 4.8 GB peak, and the whole stage takes 9 minutes.

## W4 results (2026-09-22) — full tables in `docs/results_w4.md`
- **Hit rate by policy** (grouped split, full stream, depth 10, mean over 5 seeds):

  | Policy | K=1 | K=4 | K=8 | K=32 | churn at K=8 |
  |---|---|---|---|---|---|
  | Belady (offline optimum) | .719 | .961 | .987 | .998 | .013 |
  | decayed LFU γ=.99 | .580 | .937 | .980 | .997 | .039 writes/flow |
  | LRU | .580 | .928 | .978 | .997 | .045 |
  | hourly oracle | .537 | .912 | .971 | .996 | – |
  | LFU | .580 | .742 | .887 | .982 | .226 |
  | best static in hindsight C(K) | .256 | .638 | .826 | .974 | – |
  | static top-K from first hour | .004 | .006 | .007 | .007 | – |

  - The first hour is benign-only (04-02), weeks before any attack, which is why the first-hour static table is useless.
  - Regret of decayed LFU vs Belady at K=8: .007 (full stream, depth 10) and .016 (depth None).
- **Benign stream, depth 10, K=8:** Belady .929, decayed LFU .888.
- **LFU is the one bad online policy.** It holds on to stale phase popularity: it has 5× the churn of LRU
  and recovers slowest after phase changes.
- **Adaptation, measured in flows** (`experiments/w4_recovery.py`, K=8, depth 10):
  - Online policies reach a day's steady hit rate within 0–5,500 flows of a phase boundary;
    LFU takes up to 11,500.
  - Excess misses in the first 10k flows: at most about 770 for LRU and decayed LFU, 2,067 for LFU (04-27).
  - The hourly-bin recovery table was **dropped**: it could not resolve adaptation, which finishes well
    inside an hour.
- **Caveats:**
  - A static policy is not a fair online baseline once phases drift. C(K) is shown as the hindsight bound.
  - Everything still uses stand-in training pools.

## Morning summary (overnight run, 2026-09-22)
- **Ran:**
  - W3: 10/10 units in 9 minutes. Gates passed first; the quick gate caught one bug (non-categorical key columns).
  - W4: 10/10 units in 9 minutes, plus the recovery analysis.
  - No unit needed a retry.
- **Committed** locally as akekulip, with no trailers.
- **Open items:**
  - `train_test_network.csv` is still missing; W2–W4 all use stand-in pools.
  - W5 (BMv2 prototype) is next.
  - The report and slides (W7) should use the revised framing in `docs/framing.md`.

## Code review and re-run (2026-09-22 late evening) — supersedes the W2–W4 numbers above
- The code-reviewer agent found no blockers. It found four majors, all fixed:
  1. The group partition was the same for every seed. It is now seed-mixed.
  2. The depth-10 headline model had been picked on test. Headlines now use the validation-selected depth.
  3. The recovery threshold was too loose. Recovery now counts only true phase boundaries, uses a relative miss-rate test, and treats excess misses as the primary measure.
  4. Re-running a report deleted the recovery section. Recovery now lives in its own doc.
- **Minor fixes:**
  - exact decayed-LFU eviction key, with a test in the underflow regime;
  - the static policy can no longer hit in its own warm-up hour;
  - full replay-alignment assert.
- Re-ran W2 → W3 → W4 through `experiments/rerun_after_review.sh`: gates first, about 70 minutes, all passed.
- **Numbers that changed** (grouped split, data-plane DT):
  - **Accuracy plateaus; it does not decline.** Depth 10: .904. Depth 12: .921 ± .027. Unpruned: .918 ± .040. The earlier
    "deeper trees lose accuracy" (.929 → .898) was partly an artifact of the fixed partition.
  - **Validation selection is unstable.** The five seeds picked unpruned ×2, depth 10, depth 12 and depth 16.
    The headline tree is therefore the unpruned tree (1,880 leaves).
  - **Leakage inflation:**

    | Model | random | grouped | inflation |
    |---|---|---|---|
    | DT | .967 | .918 | +.049 |
    | RF | .967 | .919 | +.048 |
    | HGB | .962 | .909 | +.053 |
    | LR | .866 | .780 | +.086 |

  - **Replay macro-F1 is far below IID** (96% attack stream):

    | Split | DT (val depth) | HGB | always-attack |
    |---|---|---|---|
    | grouped | .555 | – | .495 |
    | forward | .624 | .827 | .491 |

    Forward-split recall on unseen injection is .51.
  - **Locality at the unpruned depth:** full W90 26 and W99 266; benign W90 43; attack types W90 1.6–17.8; mitm 96.
  - **Caching at the unpruned depth, K=8, full stream:**

    | Policy | Hit rate |
    |---|---|
    | Belady | .964 |
    | decayed LFU | .947 |
    | LRU | .936 |
    | hourly oracle | .929 |
    | LFU | .778 |
    | C(8) | .709 |
    | static | .013 |

    Regret of decayed LFU vs Belady is .017.
  - **Recovery** (depth 10, true phase boundaries): mean excess misses in the first 10k flows are 119 for decayed LFU,
    133 for LRU and 836 for LFU. Phase 04-27 takes about 16k flows even for Belady.

## W5/W6 results (BMv2) — `docs/results_w5.md`
- The validation-selected tree for seed 0 is unpruned (1,720 leaves). K=8 entries, decayed LFU with γ=.99.
  Two 30k-query slices across phase changes.
- **All checks pass:**
  - served prediction equals `tree.predict` on 60,000/60,000 queries;
  - the switch hits exactly when the policy says the leaf is resident;
  - the hit sequence equals the offline simulator;
  - occupancy never exceeds 8.
- **Hit rates:** .922 (full slice) and .856 (benign slice).
- **Timing on BMv2:**

  | Measure | full slice | benign slice |
  |---|---|---|
  | hit round trip p50 / p99 | .21 / .28 ms | .24 / .31 ms |
  | miss service p50 | .85 ms | 1.02 ms |

- **P4Runtime writes on BMv2:** 3,866/s single, 33,622/s batched 100.
- **Design:** exact float32 order-preserving 32-bit keys (`src/mvm/p4encode.py`). No sudo or interfaces are needed, because packet-out and packet-in go over P4Runtime.

## W7 deliverables — `docs/report/`
- `report.md` → `report.pdf` (11 pages) and `slides.md` → `slides.pdf` (13 Beamer slides). Build with
  `pandoc report.md -o report.pdf --pdf-engine=tectonic`. Every number comes from `experiments/w7_numbers.py` → `docs/report/numbers.json`.
- **Writing gates:**
  - `natural-voice`: PASS, with no regression across the edit pass. The first edit pass was rejected and redone.
  - `voice_check`: 9 deviations, all justified. Every one points to a plainer, more readable text than the corpus
    (Flesch 52 vs 16–29, fewer nominalizations), appropriate for a class report.
  - `density_check`: fails on too MANY numbers. It was kept, because removing numbers regressed `natural-voice` grounding, and the voice gate outranks it.
  - `academic-humanizer` was not run as a separate skill. Claim/evidence hedging was done by hand.
  - `remove-ai-marks` Layer A: 0 marks; PDF metadata stripped.
- **Before submission, Philip must:**
  - verify references [6], [12], [13], [14] (authors and titles marked "[to be verified]"; check them in Zotero);
  - add any AI-use disclosure the course requires;
  - revise the prose in his own words where he wants it to be his.

## W8 results (Tofino-1 hardware, 2026-09-23) — `docs/results_w8.md`, `hw/README.md`
- **Encoding.** The 20-bit range limit is met with per-feature fine and coarse thermometer tables plus
  a ternary `leaf_tbl`, one entry per leaf.
  - Depth 10 (394 leaves, 361-bit key) is the deepest tree that fits; depth 12 needs 602 bits.
  - The program uses all 12 ingress stages.
  - Emulation is exact against `tree.apply` (unit-tested).
- **Takeover.** The DNP3 anchor-fix program was snapshotted to `~/ml_p4/snapshot_dnp3_20260923/`,
  with `~/ml_p4/RESTORE_dnp3_20260923.sh` ready, and then stopped.
  - **MVM is left running**, as Philip decided.
  - Hulk's switch link (dp10) was brought up for the first time in this setup.
- **Bugs found and fixed on hardware:**
  1. A direct counter must run in every action of its table.
  2. Range entries take about 1.5 TCAM rows each, so range tables are sized at 4×.
  3. The conf path rewrite missed `build_new`.
  4. Reflected hits were dropped by the NIC because the source MAC was its own; the hit action now swaps MACs.
  5. The backend's `recvmmsg` blocked until 64 packets arrived; it now uses `MSG_WAITFORONE`.
  6. The feature offset was wrong (16, not 20). Found by the fidelity check on the smoke run.
  7. The controller log was corrupted by unsynchronized thread writes; one early log is affected and parsed leniently.
- **Campaign:** 36 runs; **1,080,000 queries answered, and served class and leaf equal the tree in 100% of
  them.**
- **Hit rate at 1k qps:**

  | Slice | hardware | ideal / BMv2 | hardware-policy sim, lag 10–50 queries |
  |---|---|---|---|
  | full | .956 | .963 | brackets it |
  | benign | .846 | .885 | brackets it |

  The controller takes 6.1 ms at the median from digest to completed write (24.4 ms at the 99th percentile).
- **Latency:**

  | Path | Value |
  |---|---|
  | on-chip pipeline, per hit | 362 ns (p99 391 ns) |
  | round trip at Vision, switch hit | 102.5 µs |
  | round trip at Vision, miss via Hulk | 232 µs |
  | round trip at Vision, CPU-only (K=0) | 300.7 µs |
  | CPU compute, Hulk Xeon Gold 6140 | 30 ns/query, 0 mismatches |

  The host stacks dominate the round trips: the hit round trip falls to 32.5 µs at 100k qps.
- **Load sweep to 100k qps:** both modes answered everything, and MVM's median round trip is 2–3× lower at
  every load.
  - The switch hit rate falls to .676–.809 at 5k–100k qps, non-monotone. The hypothesis is control-plane lag in
    queries, plus short runs at high rates.
- **Security note for Philip:** `~/.claude/projects/-home-philip/memory/feedback_ssh_sudo.md`
  contains the lab password in plain text. Remove it and rely on `~/.lab_env`.

## Next action
1. Philip: re-download `Train_Test_datasets/Train_Test_Network_dataset/train_test_network.csv` on its own, as a single file.
2. Once it arrives: check the no-`ts` claim and 461,043 rows, match its rows against the full set
   (overlap removal), then re-run the pilot on the real training file.
3. All milestones W1–W8 are done. MVM stays on the switch; restore DNP3 with ~/ml_p4/RESTORE_dnp3_20260923.sh when needed. Remaining: get the official `train_test_network.csv` and re-run
   everything with it (the pools are stand-ins); optionally run the NF-ToN-IoT-v3 cross-check; verify the references.
4. (done) W3 (RQ2/RQ3): locality metrics on the saved leaf streams
   (`results/w2/{grouped,forward}/leaves/seed*_dp_DT_depth*.npy`, `replay_mask_seed*.npy`).
   - Three orderings: file order, within-second shuffle, and flow-end time.
   - Three streams: full, benign-only, per-phase.
   - Pareto frontier of macro-F1 vs W90, and the ccp trees.

## 2026-09-23: paper direction agreed (round table), gates next
- Round table converged; plan approved by Philip: `docs/paper_plan.md`.
  Paper: *Downgrade Attacks on Stateful In-Network Classifiers and Value-Aware Slot Admission*.
  Target ACSAC; TDSC fallback.
- Record and sources: `docs/lit/round_table.md`, `docs/lit/bibliography.md`.
- Next action: gate G0, offline only.
  - Clone NetBeacon, BoS, Flowrest and SketchFeature into `third_party/` (gitignored).
  - Extract table sizes, hashes, timeouts, reclamation, predictor, T_esc and the collision budget, with `file:line`, into `docs/results_g0.md`.
- Then G1: the downgrade gap (H1), tests first. H1–H5 are committed in a pre-registration file before G1 runs.
- No switch time until the gates pass. G4b is compile-only.

## 2026-09-23 (later): G0 done, emulator ready, waiting on data
- Done and committed:
  - G0 (`docs/results_g0.md`);
  - pre-registration (`docs/preregistration.md`);
  - NetBeacon table emulator (`src/dgrade/netbeacon.py`, 100% table-vs-tree fidelity);
  - packet-level flow-state emulator (`src/dgrade/netbeacon_sim.py`).
  84 tests pass.
- The flow-state emulator has not yet had an independent code review (the builder agent was stopped; I wrote it directly).
- Blocked on data:
  - PeerRush from the BoS Google Drive folder, into `data/raw/`;
  - CICIoT2023 pcaps, needed later for H4.
- Next action once PeerRush lands:
  1. Build a pcap→packet-array loader.
  2. Measure the benign-only downgrade rate at MAWI-like concurrency.
  3. Run G1 (H1) on NetBeacon.

## 2026-09-23: repo regrouped
- The MVM-Lite class project now lives in `mvm_lite/`, which holds:
  - code (`src/mvm`, `src/p4gen`), `experiments/`, `hw/`, `p4/`, `figures/`;
  - its tests and its docs (results docs and report);
  - the untracked `data/` (TON_IoT) and `results/`.
- Every script resolves paths relative to `mvm_lite/`. See `mvm_lite/README.md`.
- The paper work stays at the top level: `src/dgrade`, `tests/test_dgrade_*`, the paper docs, `third_party/`, `data/raw/bos_datasets`, and `data/raw/CIC_IOT_Dataset2023`.
- Verified after the move:
  - 84 tests pass;
  - `w7_numbers.py` regenerates `numbers.json` identically;
  - the report rebuilds at 13 pages with all figures.
- File paths in the entries above this one predate the move and are relative to `mvm_lite/`.

## 2026-09-23: G1 benign reference done (NetBeacon, PeerRush)
- Results are in `docs/results_g1.md`, made by `scripts/g1_netbeacon.py`. Runs are in `results/g1/`, which is untracked.
- About 1% of flows (about 820 of 82,922) are downgraded under benign load at 65,536 slots. That is stable across seeds.
- The gap between the full and fallback models on downgraded flows is bimodal:
  - median +0.039;
  - eight seeds near +0.035;
  - two seeds near +0.32, when a few very large flows lose their slot.
- Seeds differ only in the clock start, because NetBeacon's hash is unkeyed.
- H1 is neither passed nor falsified on this benign population. The pre-registered H1 population is flows downgraded under attack, and that is still open.
- The first isolated reference was discarded and re-run without idle splitting (see the `preregistration.md` change log).
- The keyed-hash baseline and the attack model are still to do.

## 2026-09-23: G1b hash comparison done (`docs/results_g1b.md`)
- 267 runs: 30 paired isolated references, unkeyed CRC at 30 clock starts, and 30-draw arms for XOR-salt, random polynomial, irreducible polynomial and tabulation hash (clock varied and clock fixed where planned).
- **The XOR-salt negative control held:** outcomes were identical to the unkeyed run in 30 of 30 runs in each column. A plain salt on a CRC is not a keyed defense.
- The downgraded-flow share is about 1.07% in every arm. The share of **packets** downgraded is 1.1% to 1.2% for the shipped hash and 2.1% to 3.9% for keyed hashes. Only 1 of 30 keyed draws at fixed clock is at or below the shipped value. That is the "changed distribution" verdict under pre-registered rule (b).
- The accuracy loss L is tiny in every arm (mean about 0.001), so rule (a) passes everywhere.
- G1's bimodal gap is real: 3 of 30 clock starts give a gap near +0.33, driven by one uTorrent flow of about 40,000 packets. The G1 erratum says so.
- The pre-registration was amended after a code review and a partial look at the data; see its change log.
- Next: read the re-review, then revise the plan and move to G2 (targeted-displacement arm: known hash against secret irreducible polynomial), which needs a MAWI trace day fixed in the pre-registration.

## 2026-09-23: G2a done (`docs/results_g2a.md`)
- MAWI slices: two pre-registered days (2022-09-14, 2023-03-15), first 120 s, headers only. 240 runs (oracle and model gates, 30 draws each).
- Shipped flow-size gate: 9% to 11% of flows and 26% to 33% of packets downgraded. Oracle gate: 0.03% to 0.05% of flows and 1.6% to 3.2% of packets.
- Keyed against unkeyed: the sign flips by day under the oracle gate; under the model gate keyed draws are all lower. No consistent benign effect. The G1b "lucky shipped hash" remark does not generalise.
- The clock-wrap artefact refuses as many packets at empty slots as true collisions do under the oracle gate.
- Per-run memory is about 7 GB even after the per-day precomputation. Parallelism 3.
- In progress: K0 baselines (keyed hash at its own clock, 116 runs), then the chunked emulator loop, then the G2b fill pilot.

## 2026-09-23 (evening): G2b fill, G4 core running
- Done and committed:
  - G2a (240 runs; `docs/results_g2a.md`);
  - G2b fill runner and report; the pilot (1 draw) showed the fill excess per attacker packet is the same with slot knowledge (K1 vs B0-L about 1.03x), as predicted;
  - targeted-arm module, runner and pilot, then **paused by Philip** (H2 stays open; recorded in the pre-registration);
  - G4 pre-registered (statistician and Tofino reviews merged);
  - emulator defences D1, D3 (credit, age-only, literal-rate); 146 tests pass.
- Running: the G2b fill grid (960 runs, frozen source snapshot in `results/frozen_src` at commit cb86b43 plus `defences.py`) and the G4a core (500 runs, parallelism 2). The defended PeerRush runs (150) wait for memory; job list at `<scratchpad>/g4_peerrush_jobs.txt`, launcher `run_g4pr.sh`.
- Memory is the constraint: about 3.7 GB per MAWI run at small fills, 8.5 GB at f = 90%, 2.5 GB for PeerRush. Never run more than about 6 workers together.
- Naming hazard: the primary day prefix `p` collides with the defence suffix `_p_`; defended files end in `_p_d<name>.npz`. Monitors must match that suffix, not `_p_`.
- Pending on Philip: CICIoT2023 attack folders (G3); approval for the SDE-model diff and the compile-only fit check on the switch host.
- Next: G4a report (`scripts/g4_report.py`) when the runs finish; defended PeerRush accuracy; then the plan revision.

## 2026-09-23 (night): fill grid paused, G4a prioritised
- Available memory fell to 1 GB while the fill grid (about 4.5 GB per job at f = 25%), G4a and a separate ML_FDNA job (about 16 cores, 6 GB, another session's `run_baselines.py`) all ran. The fill pool was stopped by PID (no partial outputs). Finished fill runs: 233 of 960.
- To resume the fill grid: rerun the staged command with the job lists `g2b_stage1.txt`, `g2b_stage2.txt` and `g2b_model.txt` (scratchpad), launcher `run_g2b.sh` (uses `results/frozen_src`).
- G4a runs as two pools (forward and reverse job order, parallelism 2 each).

## 2026-09-23 (late): G4a and H3 done
- Reports: `docs/results_g4a.md`, `docs/results_g4a_diagnosis.md`, `docs/results_g4_peerrush.md`, `docs/results_g2b_h3.md`.
- Rent admission (D3) fails M2 on both days; D1 is a free benign improvement; D2 and XOR-salt do nothing against fills. H3 passes only against the two pre-registered volumetric detectors; a packet-rate detector catches the attack. Details and the revised paper thesis are in the plan file.
- The fill grid is paused at the runs listed in the reports (undefended fill arms present: oracle f = 1, 10, 50, 75, 90 and 25 for both days; model gate not run).
- Owed: SDE model diff and compile check (need approval), G3 (needs CICIoT2023 attack folders), a pre-registered discriminating defence.
