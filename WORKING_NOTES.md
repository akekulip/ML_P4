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
- [ ] **W2:** RQ1 — LR/DT/RF, depth and ccp sweep, metrics with bootstrap CIs, feature ablations
- [ ] **W3:** RQ2/RQ3 — locality metrics, Pareto frontier of F1 vs W90, drift (JS), shuffled vs chronological, per-phase windows
- [ ] **W4:** RQ4 — cache simulator (static, LRU, LFU, decayed-LFU, oracle), K sweep, recovery time, regret, churn
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
- **Waiting on Philip:** TON_IoT download from the official UNSW SharePoint into `data/raw/`.
- Nothing committed yet: the repo is initialized but has no commits.

## Next action
1. Get the TON_IoT `Train_Test_datasets/Train_Test_Network_dataset/Train_Test_Network.csv` and the
   `Processed_datasets/Processed_Network_dataset/*.csv` files into `data/raw/`.
2. `head -1` both. Confirm there is no `ts` in Train_Test and that `ts` exists in the processed
   files. Check `ts` monotonicity.
3. Run the pilot.
