# Paper plan: downgrade attacks on stateful in-network classifiers

Agreed by the expert round table on 2026-09-23 and approved by Philip. The full round-table record is in `docs/lit/round_table.md`.


## Context
- **The request.** Philip asked for a critical review of the MVM idea for novelty, whether its problem is
  real, and its gap, followed by an expert round table and an end-to-end plan once the experts agree.
  He was explicit that there is no hurry to implement.
- **The rounds.** Three Round 1 experts, two literature scouts, PI proposals v1 and v2, two reviewer
  passes, an artifact code audit, and a full read of SketchFeature. The record is below this section.
- **Where it landed.**
  - **MVM caching itself is not the paper.** All 394 leaves fit on the switch, and CacheFlow, IIsy
    and Proteus sit on either side of it. The v1 slow-tier overload idea is also out: Smith ACSAC'06,
    Pigasus, AESOP, and our own W8 data (the CPU slow tier absorbs 100% escalation) cover or refute it.
  - **What survived both reviews** is the *accuracy* cost of how stateful in-network classifiers ration
    their accurate path.
  - **Reviewer verdict:** *converged at ACSAC* if items 1–6 of its v2 review are adopted and SketchFeature
    does not already measure fallback accuracy loss on NetBeacon. **The full read confirms it does not**:
    SketchFeature attacks FlowLens and NetWarden, and its NetBeacon numbers are clean-traffic only.
  - **Fallback venue:** TDSC, as the admission-control paper.

## 1. Paper
- **Title:** *Downgrade Attacks on Stateful In-Network Classifiers and Value-Aware Slot Admission*.
  The name is kept plain for ACSAC.
- **Thesis:**
  - Stateful in-network classifiers (NetBeacon USENIX Security'23, BoS NSDI'24) give their accurate
    per-flow model only to flows that win a hash-indexed storage slot. All other flows silently drop to a
    weaker per-packet model.
  - An external attacker can hold those slots and push benign third-party flows, and its own concurrent
    attack flows, onto the weak model. Nothing is dropped and latency does not change; only accuracy falls.
  - NetBeacon's authors argue this fallback is harmless and never measure it. We measure it. Then we
    make slots something a flow must keep earning.
- **Novelty claimed, per the SketchFeature read and both reviews:**
  1. **Downgrade through fallback routing on slot contention** in in-data-plane classifiers.
     Occupancy attacks as such belong to LOFT and Heracles; SketchFeature exploits FlowLens's storage limits.
  2. The **downgrade gap measured on the population actually downgraded**.
  3. **Collateral harm to third-party flows through a classifier**, which no prior work measures.
  4. **Value-aware, rent-based admission** in place of sketches.
  5. An **adaptive-attacker** evaluation, including keyed hashing.
- **Not claimed:**
  - that state exhaustion, IDS fail-open, or sensitivity attacks are new;
  - a timing oracle;
  - anything about slow-tier throughput.
- **Related-work positioning (must appear in the paper's first related-work paragraph):**

  | Line of work | Papers |
  |---|---|
  | Flow-table and rule-state exhaustion | LOFT, Tuple Space Explosion, AVANT-GUARD, FloodGuard, Sonchack ACSAC'16, Liu ICDCS'17, Heracles NDSS'26 |
  | IDS overload | Ptacek & Newsham'98, Smith/Estan/Jha ACSAC'06, Papadogiannakis ATC'12, Pigasus OSDI'20 |
  | Adversarial data structures | Clayton CCS'19, Markelon CCS'23, sketch pollution arXiv 2503.11777 |
  | Sensitivity attacks | Kang CSET'19, CASTAN SIGCOMM'18 |
  | Feature-extractor attacks | SketchFeature NDSS'25 |
  | Compute-forcing attacks | DeepSloth, AESOP |
  | Evasion | NetMasquerade |
  | Keep-the-heavy eviction | HashPipe, Elastic Sketch, HeavyKeeper, PRECISION, TinyLFU |
  | Hybrid classifiers | IIsy, BoS, Turbolearn, Proteus, SpliDT, Flowrest |

## 2. Threat model
- **T-exhaust (primary).**
  - An external sender, possibly spoofing sources, needing no replies.
  - **K1:** the attacker knows the public P4 defaults (hash, table size, timeouts, short-flow predictor).
    **K0:** the attacker knows none of them. **Keyed-hash variant:** the hash seed is salted per boot.
  - The budget ρ is reported three ways:
    - new flows/s against the victim's slot reclamation rate (the binding unit);
    - slot-seconds held;
    - bytes/s as a share of benign bytes.
  - The claim is made only where standard volumetric and new-flow-rate detectors stay silent.
- **T-evade.** The same attacker also runs real attack-class flows while exhaustion is active.
- **Deployment cases.**
  - An unfiltered edge, e.g. campus or ISP ingress.
  - A spoofing-filtered edge (source-address validation, OT enclave). We state which results survive there.
- **Silent:** drop rate and p99 latency change by no more than a stated tolerance, fixed in pre-registration.
- **Out of scope, stated explicitly:**
  - BoS's 7-packet pre-analysis window (reported as context in G1 only);
  - IMIS provisioning;
  - poisoning.

## 3. Design
- **Downgrade-gap analysis (C1).** For each victim, compare the full per-flow model with its fallback
  model, per class, on three populations:
  - (i) benign flows downgraded under attack, which skew late-arriving and short;
  - (ii) the attacker's own attack classes;
  - (iii) every class separately.

  Evaluated at **published provisioning**. The benign-only collision and downgrade rate at MAWI/CAIDA
  concurrency is reported first, to separate the provisioning problem from the security problem.
- **Attack families (C2, C3), described at research level only:**
  - slot-holding flows kept alive just inside the victim's timeout and reclamation rule;
  - collision targeting under K1;
  - flows shaped to game the short-flow predictor so benign flows lose slots.

  Figures of merit, each normalized by **B0**, where B0 is random spoofed new flows at the **same
  new-flow rate** (the single pre-registered unit):
  - benign flows downgraded per attacker packet;
  - ρ\*.
- **Defense (C4): value-aware rent admission.** Keyed hashing is always on, and the salt is a baseline too.
  - **Rent.** On a collision, the incumbent keeps its slot only while its packets per slot-second exceed
    the newcomer's prior and it has no confident verdict yet.
  - **Memo.** Flows with confident verdicts move to NetBeacon's existing verdict table, which frees their slots.
  - **Value.** A first-packet-feature table predicts the full-vs-fallback accuracy gain from C1, and
    biases admission toward flows the fallback gets wrong.
  - **Value is treated as adversarial**, because first-packet features are attacker-controlled. A flow
    earns value credit only after k packets whose behaviour matches the value predictor. Before that,
    value acts only as a tie-breaker inside rent.
  - **Lemma (stated and proved) with value maximized by the attacker.** Against a policy-aware attacker
    who mimics benign packet rates and forges value, the attacker's cost per displaced benign flow is
    at least the benign per-slot packet rate.
    - Value can only add cost, through the k-packet credit, never subtract.
    - Any gain beyond fair share ρ/(1+ρ) is claimed only where it is measured under value forgery.
  - **Ablation:** rent only / value only / both.

## 4. Implementation on the existing testbed
- **Offline code** goes in a new package, `src/dgrade/`. It reuses the style of `src/mvm/cache.py`
  (numba kernels, checked against reference Python policies), `mvm.metrics`, and the block bootstrap
  from `experiments/w2_rq1.py`.
  - `emulate.py`: a per-artifact policy emulator for storage, hash, timeout, predictor and fallback
    routing, written from each artifact's P4 and controller code.
  - `models.py`: loads NetBeacon's shipped trees and tables and BoS's retrained models, as full and fallback pairs.
  - `attacks.py`: attack families, B0 and the adaptive attacker.
  - `defense.py`: rent + value admission and baselines 2–7.

  Tests come first (`mp-tdd`): emulator-vs-reference equivalence, admission invariants, and fidelity of
  the emulator against the P4 tables.
- **Hardware victims.** On the UfiSpace Tofino-1 with SDE 9.13.2, built only in `~/ml_p4/build_new`
  style directories, with a snapshot plus restore script before any displacement of MVM or DNP3.
  - **NetBeacon:** a port of the artifact P4 (12 stages).
  - **BoS on-switch part:** a port from SDE 9.7.0 and a 2-pipe recirculation layout to our pipe
    layout, verified in G0. Its IMIS escalations go to a **labelled CPU stand-in on Hulk**, adapting
    `hw/hulk_backend.c`.
  - **MVM:** control only, never counted as a victim.
- **Traffic.** `hw/vision_client.c` is extended into a pcap replayer for benign packet-level traces, plus
  an attack generator with a spoofed source set, run only inside the lab testbed. Controller, timestamp
  and log plumbing are reused from `hw/controller.py`.
- **Emulator validation.** Packet-for-packet on the same traces against both hardware victims, with
  divergence reported. This is the same pattern as the W8 per-query fidelity check.
- **Defense P4.** Compiled next to NetBeacon, with its stage, SRAM and stateful-ALU report.

## 5. Evaluation
**Gates, run in order: offline, no switch time, about 3 weeks.**
- **G−1 (done):** SketchFeature and 2503.11777 read in full; overlaps partly, core safe.
- **G0:** from the artifacts, extract and cite by `file:line`:
  - table sizes, hashes, timeouts and reclamation, the short-flow predictor, BoS T_esc and its collision budget;
  - published provisioning;
  - dataset availability;
  - SDE and pipe needs against our switch.
- **G1:** the downgrade gap on the three populations (H1). **This gate decides ACSAC (attack + defense)
  vs TDSC (defense only).**
- **G2:** emulator + MAWI/CAIDA concurrency, giving:
  - the benign-only downgrade rate;
  - B0 vs crafted amplification (H2);
  - ρ\* in all three units against a volumetric and new-flow detector model (H3);
  - the keyed-hash variant.
- **G3:** offline T-evade (H4).
- **G4:** defense in the emulator against every baseline and the adaptive attacker, including value
  forgery (H5), before any P4.
- **G4b (weeks 3–4, before the ports):** compile a defense skeleton next to NetBeacon's P4 with SDE
  9.13.2 bf-p4c, in a separate build directory on the switch. Compile only: no `bf_switchd` restart,
  no displacement of the running program.

**Hardware campaigns (only after the gates pass):**
- E1 port and fidelity;
- E2 downgrade-gap replay;
- E3 attack vs B0, with a provisioning sweep;
- E4 concurrent-attack evasion;
- E5 defense on hardware with its resource report;
- E6 emulator validation.

**Baselines:**
1. B0;
2. per-source limit;
3. global cap with random admission;
4. per-region round-robin (fair share);
5. larger table at its measured cost;
6. fail-closed handling;
7. memoization (NetBeacon native, and added to BoS);
8. unbounded-storage oracle, plus MVM all-resident;
9. keyed hashing alone;
10. HashPipe-style keep-heavier;
11. Elastic Sketch Ostracism;
12. TinyLFU admission;
13. a SketchFeature-style all-flow sketch, in the emulator only: the artifact ships no P4, and the classifier must be retrained on decoded features. Its about 13% F1 cost was measured at 6 MB; the 3 MB, 7-stage figure describes the prototype (see `docs/results_g0.md`).

**Pre-registered hypotheses (one primary metric each):**

| H | Primary metric | Pass | Falsifier |
|---|---|---|---|
| H1 | gap, full − fallback, on the attack-downgraded population. Metric per task: macro-recall on attack classes (BoS BoT-IoT / CICIoT2022); macro-F1 on the degraded classes (NetBeacon traffic-classification sets) | ≥ 0.10 on a victim | < 0.03 on both → the fallback is "harmless" |
| H2 | benign flows downgraded per attacker packet, crafted ÷ B0 | ≥ 5× | < 2× |
| H3 | ρ\* to downgrade 50% of benign flows at published provisioning, in new flows/s ÷ reclamation rate | detectors silent at ρ\*. The detectors are fixed in pre-registration: a Jaqen/Poseidon-style new-flow-rate threshold and a volumetric threshold, both at the benign p99 | ρ\* > 1, or detectors fire |
| H4 | recall on concurrent attack flows (run on BoS's BoT-IoT / CICIoT2022 attack classes; TON_IoT optional) | drop ≥ 20 pp | drop < 10 pp |
| H5 | benign macro-F1 recovered under the adaptive attacker at the undefended ρ\* | ≥ 50% recovered, beats baselines 2–13 by ≥ 5 pp, costs ≤ 1 pp with no attack | not better than keyed hashing + keep-heavier |

- **Generality:** argued through an emulator sweep over table size, hash layout, timeout and fallback type.
  The two hardware victims are validation points.
- **Datasets:**
  - the victims' own datasets (NetBeacon: PeerRush, MAWI, ISCXVPN; BoS: ISCXVPN2016, BoT-IoT, CICIoT2022, PeerRush);
  - MAWI and CAIDA for concurrency (CAIDA needs an access request);
  - TON_IoT attack classes for T-evade, which needs pcaps that we do not yet have.
- **Statistics:** 10 seeds, block bootstrap, Holm correction. Victim configurations are frozen from the
  artifacts before any attack run. Runs last at least 10 minutes.

**Kill criteria:**
- **(d)** H2 < 2× → drop the attack claims and pivot to TDSC defense-only.
- **(e)** ρ\* > 1, or the detectors fire → same pivot.
- **(f′)** H1 is "harmless" → a short negative-result note, and the defense folds into TDSC.
- **(g)** Neither port runs on SDE 9.13.2 within 4 weeks → emulation-only TDSC. C1, C2 and C4 survive
  in emulation; hardware evasion and resource claims do not.
- **Keyed-hash case.** If keyed hashing alone restores ≥ 80% of the loss, the attack section becomes a
  configuration advisory. Only the defense's win over keyed hashing is claimed.
- **(h)** The defense does not fit next to NetBeacon (G4b) → deploy it next to BoS, or next to a
  NetBeacon build with fewer stages, and state the reduced resource claim.
- **(i)** H5 fails while H1–H3 pass → an attack paper at ACSAC with the defense sketched; the full
  defense is deferred to the TDSC extension.
- **Spoofing-filtered run in G2:** unspoofed slot holding, capped by a per-source limit. Report which
  of H2–H4 survive it.

## 6. Risks
1. **The gap is small (H1)**: the victims' own claim holds. This is decided in G1 in about a week.
2. **Port feasibility**: BoS's 2-pipe layout and SDE 9.7.0; NetBeacon uses all 12 stages, so the
   defense may not fit next to it.
3. **Keyed hashing trivializes the attack.**
4. **Missing packet-level datasets**: TON_IoT pcaps, CAIDA access.
5. **Switch time**: shared with DNP3 and GridCloak. MVM is displaced with a snapshot and restore script.
6. **Two-host realism**: the attacker, benign traffic and measurement share Vision.

## 7. Timeline (from approval; estimates, not measurements)

| Weeks | Work |
|---|---|
| 1–3 | gates G0–G4, offline |
| 4–8 | ports + E1 |
| 9–12 | E2–E4 |
| 13–17 | defense P4 + E5–E6 |
| 18–21 | writing, run through the paper-voice → academic-humanizer → natural-voice → remove-ai-marks chain |

- **About 5 months.** Primary venue ACSAC; extended version TDSC. **ACSAC 2027's deadline is unverified.**
- **Ethics and disclosure section.** All spoofed traffic stays on the isolated testbed. Findings are
  disclosed to the NetBeacon and BoS authors before submission, if Philip agrees.

## 8. First actions after approval (offline only; nothing touches the switch)
1. Save the round-table record and a bibliography to `docs/lit/` (`SYNTHESIS.md` plus per-scout notes,
   citing only DOIs, arXiv ids and URLs returned this session), and add the two scratchpad PDFs'
   citations. Commit locally as akekulip with no trailers.
2. Run `setup-matt-pocock-skills` once for this repo (`docs/agents/` is missing), then `to-spec` for the gates.
3. **G0:** clone NetBeacon, BoS, Flowrest and SketchFeature into `third_party/` (gitignored), then extract the parameters table.
4. **G1** with tests first; report H1 before any further work.

## Verification of this plan
- **Traceable claims.** Every prior-work claim traces to a tool result in this session (listed in the round-table record below).
- **Reviewer conditions.** Every must-fix item from the v2 review maps to a plan item:

  | Reviewer item | Plan location |
  |---|---|
  | 1 | G−1 + §1 |
  | 2 | §1 related work |
  | 3 | H1 |
  | 4 | baselines 9–13 |
  | 5 | §3 lemma + ablation + E5 resource fit |
  | 6 | §2 units + H3 |

- **Reviewer final pass: CONVERGED at ACSAC.**
  - Conditions: H1 passes in G1, and edits 1–5 are applied.
  - Edits 1–5 are all in this section: value forgery, G4b + (h), novelty wording, per-task H1 metric, detectors + spoof-filtered run + (i).
  - Expected outcome: ACSAC weak accept (~35–40%) if G1–G2 pass; TDSC fallback about 55%.
- **Gate outputs.** Each gate writes a results doc (`docs/results_g*.md`) generated from logged files. H1–H5 are committed in a pre-registration file before G1 runs.

