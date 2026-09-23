# Pre-registration: downgrade attacks on stateful in-network classifiers

Committed on 2026-09-23, before gate G1 runs and before any attack or defense result exists. These hypotheses, metrics and thresholds are frozen. Any later change is recorded in the change log at the end, with its date and reason, and the paper reports both the original and the amended version.

## Fixed definitions

- **Victims.**
  - **V1: NetBeacon.** The shipped PeerRush build (commit 06c6127), run in a table-level emulator from its shipped table pickles.
  - **V1′: NetBeacon-faithful retrain on CICIoT2023.** Our re-implementation of NetBeacon's phase-tree training, which we must write because none ships. It is validated against the structure of the shipped PeerRush tables before it is used.
  - **V2: BoS.** The single-pipe build (commit 38aafd9), with `T_conf`/`T_esc` re-derived under the paper's rule that at most 5% of flows escalate. The per-packet forest is retrained, because it does not ship.
  - **Control: MVM.** Never counted as a victim.
  - **Generality point: Flowrest.** It has no fallback model, so a flow without a slot gets no verdict.
- **Published provisioning.** 65,536 slots with each victim's shipped timeout, hash and admission rule, as recorded in `docs/results_g0.md`. No attack result may use a smaller table.
- **Benign concurrency.** A MAWI trace (a specific day chosen before G2, recorded here), replayed at its native rate and at the rates NetBeacon's paper used (up to 1,555 new flows/s).
- **B0.** Random spoofed new flows at the **same new-flow rate** as the attack being compared.
- **Downgraded flow.** A flow that has a verdict path in the full model but is classified, in whole or in part, by the fallback model (NetBeacon, BoS) or receives no verdict (Flowrest), because of slot contention.
- **Silent.** The drop rate changes by no more than 0.1 percentage points and p99 latency by no more than 10% against the no-attack run.
- **Detectors (fixed now).**
  - A new-flow-rate threshold per /24 source and global, Jaqen/Poseidon-style, set at the benign p99 of the chosen MAWI trace.
  - A volumetric bytes/s threshold at the benign p99.

## Hypotheses (one primary metric each)

| H | Primary metric | Pass | Falsifier |
|---|---|---|---|
| H1 gap | full minus fallback, on flows downgraded under attack. Metric per task: **macro-F1 over the degraded classes** for V1/V2 application classification; **macro-recall over attack classes** for V1′ on CICIoT2023 | ≥ 0.10 on at least one victim | < 0.03 on every victim → the fallback is "harmless" (kill criterion f′) |
| H2 amplification | benign flows downgraded per attacker packet, crafted ÷ B0 | ≥ 5× | < 2× (kill criterion d) |
| H3 stealth | ρ\* to downgrade 50% of benign flows at published provisioning, in new flows/s ÷ the victim's slot reclamation rate | both detectors silent at ρ\* | ρ\* > 1, or either detector fires (kill criterion e) |
| H4 evasion | recall on the attacker's concurrent CICIoT2023 attack flows, on V1′ | drop ≥ 20 pp | drop < 10 pp |
| H5 defense | benign macro-F1 recovered under the adaptive attacker (rate-mimicking and forging value) at the undefended ρ\* | recovers ≥ 50% of the loss, beats baselines 2–13 by ≥ 5 pp, costs ≤ 1 pp with no attack | not better than keyed hashing plus keep-heavier |

H1 is also reported, as secondary results, on (ii) the attacker's own attack classes (V1′) and (iii) each class separately, together with the benign-only downgrade rate at the chosen MAWI concurrency.

## Statistics

- 10 seeds for every stochastic element (flow sampling, spoofed sources, hash salt).
- Block bootstrap over 1-second blocks for 95% confidence intervals.
- Holm correction across H1–H5.
- Every victim configuration is frozen from its artifact before any attack run.
- Hardware runs last at least 10 minutes.

## Kill criteria

- (d) H2 falsified → drop the attack claims and pivot to a TDSC defense-only paper.
- (e) H3 falsified → same pivot.
- (f′) H1 falsified → a short negative-result note, and the defense goes into TDSC.
- (g) Neither port runs on SDE 9.13.2 within 4 weeks → emulation-only TDSC.
- (h) The defense cannot fit next to the unmodified victims (already true from G0: both use all 12 stages) → deploy it on a NetBeacon build with fewer phases, and state the reduced resource claim.
- (i) H5 fails while H1–H3 pass → an ACSAC attack paper with the defense sketched.
- Keyed hashing alone restores ≥ 80% of the loss → the attack section becomes a configuration advisory.

## Change log

- 2026-09-23: initial version.
  - H1's metric was made per task, and H4 was moved to CICIoT2023 with V1′, because G0 found that no victim dataset contains both benign traffic and attacks.
  - (h) was recorded as triggered by G0.
- 2026-09-23 (before any G1 result): the flow key was defined. The full-model reference for H1 is an isolated replay that gives each bidirectional 5-tuple its own slot and removes only contention. It does **not** split flows on idle gaps, because the switch identifies a flow by its 32-bit hash alone (`switch.p4:606`), so a tuple that resumes after a pause continues its old state. A first isolated run that split flows at 256 ms gaps was discarded for this reason: it made the reference restart flows the switch would have continued (392k takeovers against 20k under contention). Flow-level statistics use the same tuple keys.
- 2026-09-23: "downgraded" counts only refusals by an active slot holder (collisions) and later slot loss. Two other routes to the fallback are reported separately and are not counted: refusals at a never-claimed slot after a clock wrap, and flows the flow-size model predicts short. NetBeacon's design intends the latter.
- 2026-09-23 (before any G1b run): **G1b, hash comparison on benign PeerRush, NetBeacon emulator, 65,536 slots.**
  - **Hash arms.**
    1. Unkeyed CRC32, as shipped.
    2. XOR-salt CRC32 (a salt XORed into the input or init). This is a negative control. CRC is affine over GF(2), so a salt shifts every slot by one constant and does not change which tuples collide. **Prediction: the downgraded-flow set is identical to arm 1.** Any deviation means an emulator bug.
    3. Secret-polynomial CRC (a random 32-bit polynomial per draw). This changes which tuples collide and is the keyed baseline.
    4. Tabulation hash. A nonlinear reference bound, not a deployable design at 12 stages.
  - **Factors.** Hash draw crossed with clock start. Clock starts come from a fixed equally spaced grid over the 4.295 s wrap period. Unkeyed with a fixed clock is deterministic and is run once. Planned draws: 30 per arm. The 10 G1 seeds are reused for arm 1.
  - **Reference.** Each contended run is paired with an isolated reference at the **same clock start**. This is because inter-packet gaps are computed from a 32-bit timestamp that wraps every 4.295 s, so the reference depends on the clock. The G1 report compared seeds 1 to 9 against seed 0's reference, so its per-seed gaps are re-derived and superseded. Gate: the isolated run is repeated at 3 or more clock starts; if per-packet verdicts are identical, one reference suffices.
  - **Primary metric.** L = macro-F1(isolated) − macro-F1(contended) over all flows. Secondary: downgraded-packet share, the per-flow contribution to net packets lost (top 20 flows against the rest), p_big = the share of draws with L > 0.004, and the H1 downgraded-flow gap (unchanged from H1 and not used to decide neutrality).
  - **Inference.** The draw is the unit for hash and clock effects, using a percentile bootstrap over draws. Within a draw, uncertainty comes from a flow-cluster bootstrap.
  - **Neutral on benign traffic** holds iff all of: (a) the 90% CI of mean L(keyed) − mean L(unkeyed) lies within ±0.002; (b) the downgraded-packet-share difference is within ±0.1 pp; (c) the p_big intervals overlap. Otherwise the changed distribution is reported as is. If the intervals are too wide, the report says "not shown neutral".
  - **Not evaluated here:** the kill rule "keyed hashing alone restores ≥ 80% of the loss". It needs the attack arms in G2, including a targeted-displacement arm (known hash against secret polynomial).
  - **Uncertainty carried by all G1 and G1b counts:** the emulator hashes the sorted 5-tuple, while the switch may build `@symmetric` from a different construction. This is checked on the SDE model before any collision count is used in the paper.
- 2026-09-23 (after independent code review, after a partial G1b dry run of 19 draws per arm had been viewed): **amendments to G1b.** They are recorded here because they postdate partial results. None was chosen to favour a hypothesis; each closes a gap between the text above and what was run.
  1. **Downgrade definition.** A flow that held a slot, lost it, and is later answered as "predicted short" is also counted as downgraded (the review measured 61 to 66 such flows per run, about 7.5% of the downgraded set). This is the "later slot loss" of the earlier entry. Counts are recomputed from the saved runs; no run was repeated.
  2. **Verdict logic.** Each neutrality rule is pass, fail (interval entirely outside the bound) or inconclusive. Any fail reads "changed distribution"; "not shown neutral" is reserved for inconclusive intervals, as the addendum states.
  3. **Polynomial arm split.** The 32-bit random polynomials drawn for arm 3 are mostly reducible (the review found 1 irreducible of 30 seeds), and keyed-CRC collision bounds assume irreducibility. Arm 3 is kept as **random polynomial (as run)**, and a new arm **3b, irreducible polynomial**, is added with 30 draws per column, chosen by rejection sampling and checked against sympy. The keyed baseline for neutrality and for G2 is 3b; the other arm is reported beside it.
  4. **Clock design.** The design is a diagonal (draw g at clock g) plus one fixed-clock column (30 keys at grid 0), not a full salts × clocks cross. The 10 G1 seeds are not reused; the clock grid replaces them. A draw with key 0 at grid 0 belongs to both columns. The tabulation hash has a clock-varied column only.
  5. **Attribution.** "Top 20 flows" means the 20 largest flows by packet count; the five largest contributors to the loss are listed for the largest-L run.
  6. **Within-draw uncertainty.** The flow-cluster bootstrap is reported for the grid-0 draw of each arm, not for every draw.
  7. **Reference gate.** Reported in the results document: references differ by 134 to 2,145 of 4.85 M packets (the first draft of this line said 135) across clock starts, so all comparisons are paired.
- 2026-09-23 (before any G2 data is downloaded or opened): **G2 benign traffic is fixed.**
  - **Source:** MAWI Working Group Traffic Archive, samplepoint F (Tokyo transit link), the 14:00 to 14:15 daily capture. Headers only (96-byte capture length). Research use only.
  - **Primary day:** Wednesday 2022-09-14 (`samplepoint-F/2022/202209141400.pcap.gz`; 125,402,386 packets, 8,662.83 MB raw, 2,847.89 MB gzipped).
  - **Replication day, chosen by a mechanical rule** (exactly 26 weeks later, same weekday, still before the August 2023 change that added a 10 Gbps link to the capture point): Wednesday 2023-03-15 (`samplepoint-F/2023/202303151400.pcap.gz`; 108,803,846 packets, 7,902.78 MB raw, 2,917.26 MB gzipped).
  - **Selection basis:** the primary day was chosen on stated criteria (mid-week, not a Japanese public holiday, before the 2023 link change, high packet count), not by a mechanical rule and not from looking at its contents. Neither trace had been opened when this entry was written.
  - **Slice:** the first 120 seconds of each trace, taken as the first 120.0 s after the first packet's timestamp. This is fixed in advance to keep the emulator's run time practical and covers about 28 clock-wrap periods and 450 idle timeouts. The gzip file is downloaded only in part (the first 500,000,000 bytes) and cut at the last whole packet.
  - **Filter:** the same parser filter as the PeerRush loader (IPv4 without options or fragmentation, TCP or UDP).
  - **Detectors:** the new-flow-rate and volumetric thresholds are set at the benign p99 of the primary-day slice, measured in 1-second bins.
  - **Reporting:** every G2 number is reported on both days. A result that holds on only one day is reported as such.
