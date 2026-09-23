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
- [ ] **W5:** BMv2 — mvm.p4, controller, write-rate measurement, fidelity
- [ ] **W6:** BMv2 end-to-end replay and latency (labeled "BMv2 ≠ ASIC"); NF-ToN-IoT-v3 cross-check as stretch
- [ ] **W7:** report and slides

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

## Next action
1. Philip: re-download `Train_Test_datasets/Train_Test_Network_dataset/train_test_network.csv` on its own, as a single file.
2. Once it arrives: check the no-`ts` claim and 461,043 rows, match its rows against the full set
   (overlap removal), then re-run the pilot on the real training file.
3. W5: BMv2 prototype. Build `p4/mvm.p4` (range-match leaf table, packet-in on miss) and a
   P4Runtime controller running decayed LFU (γ=.99), K=8, depth-10 tree. Check fidelity against
   `tree.predict`, and measure the write rate.
4. (done) W3 (RQ2/RQ3): locality metrics on the saved leaf streams
   (`results/w2/{grouped,forward}/leaves/seed*_dp_DT_depth*.npy`, `replay_mask_seed*.npy`).
   - Three orderings: file order, within-second shuffle, and flow-end time.
   - Three streams: full, benign-only, per-phase.
   - Pareto frontier of macro-F1 vs W90, and the ccp trees.
