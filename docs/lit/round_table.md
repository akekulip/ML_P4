# Round-table record (2026-09-23)

Round 1 positions, Round 2 proposals and reviews, the artifact audit and the SketchFeature read, as recorded while planning. Only papers opened through a tool this session are cited; items marked UNVERIFIED were not confirmed.


**Philip's direction (2026-09-23):** no hurry to implement. The foundations exist, so the goal is to
get the idea right first.
- A **critical reviewer** judges the ideas for novelty, whether the problem is real, and the gap.
- Its feedback goes into the plan.
- Experts hold a **round table**: research, history, prior work.
- Once they **agree on one novel idea**, an **end-to-end plan** follows: motivation, design,
  implementation and evaluation.

**Process (all agents read-only while planning; results come back to the planner):**
- **Round 1: independent positions** (six experts in parallel).
  1. `ieee-journal-reviewer`: critical review of MVM as it stands and of A–D. For each: is the problem
     real, what prior work would be cited against it, the gap, the top objections, a score, and any better direction.
  2. general-purpose + Semantic Scholar/arXiv: prior work on attacks against inference caches —
     SDN timing and overflow attacks, control-plane saturation, cache pollution, attacks on in-network ML.
  3. general-purpose + Semantic Scholar/arXiv: history and state of the art of in-network ML, 2018–2026,
     including forward citations of Leo, NetBeacon, IIsy and SpliDT, and per-flow state bounding.
  4. `sdn-networks-expert`: how realistic the deployment is, the threat model for A, probes needed for
     the timing channel, defenses; B and D feasibility; a recommendation.
  5. `p4-dataplane-engineer`: Tofino-1 and Tofino-2 feasibility — data-plane replacement, install
     speed, stateful features, defense costs, hiding the timing difference. Paper analysis only.
  6. `research-scientist`: datasets for external validity, evaluation design with pre-registered
     hypotheses, which results can be reused, the biggest methodological risk.
- **Round 2: round table.** Every Round 1 finding goes to the principal-investigator, which proposes
  one converged idea. The critical reviewer then attacks that proposal, and the experts rebut. Repeat
  until the reviewer rates it at least "weak accept assuming the evidence is delivered", or until
  the panel agrees it cannot get there; then pick the next candidate.
- **Round 3: end-to-end plan** for the agreed idea, written into this file:
  - motivation and the problem;
  - threat or system model;
  - design;
  - implementation on the existing testbed;
  - evaluation, with hypotheses, datasets, baselines and metrics;
  - risks;
  - timeline and target venue.

  The critical reviewer does a final pass on it.
- **Philip approves** the idea and the plan before anything is built.

## Round 1 findings (filled in as experts report)
**Critical reviewer (ieee-journal-reviewer):**
- **Premise undercut.** The 394-leaf tree fits in Tofino TCAM without caching. K=8 was chosen, not forced.
  The binding constraint was **key width** (361 of 440 bits), which caching does not relieve.
- **Weak CPU baseline.** The CPU computes the tree in 30 ns, so the offload and round-trip gains are
  host-stack effects.
- **Features.** They are precomputed off-switch.
- **Scores:**

  | Direction | Score |
  |---|---|
  | MVM as it stands | reject (workshop at best) |
  | A, MVM only | weak reject |
  | A, generalized to published hybrids with a real harm model | borderline to weak accept |
  | B | reject (SpliDT subsumes it; the feature union over any working set is likely all 10) |
  | C | reject as a paper (but "fit deeper trees into 440 bits" is interesting) |
  | D | a section |

- **Proposed better direction: "Slow-Path Attacks on Hybrid In-Network ML"** (USENIX Security / NDSS).
  - Reproduce at least three published hybrid designs on the same Tofino (BoS or IIsy confidence
    escalation, NetBeacon fallback, SpliDT recirculation, MVM residency).
  - Show (i) a timing oracle an off-path attacker observes through its own flows, leaking decision
    regions and co-tenants' traffic classes.
  - Show (ii) query-efficient steering into the slow path, making detection fail open or late.
  - Build (iii) a data-plane defense: admission filter, per-source escalation budgets, register memo
    (absorbing D). Measure its cost on real background traffic.
  - **Kill criterion:** no attacker-observable timing channel without the query-response harness means stop.
- **Questions for the scouts:**
  1. Any timing or side-channel attack on in-network ML or switch KV caches.
  2. Any adaptive residency of model parts after 2024 (including arXiv 2512.09809).
  3. Whether SpliDT bounds mid-flow feature loss.
  4. What Sonchack ACSAC'16 and LOFT'17 claim exactly.
  5. Whether tree extraction through timing oracles is published.
  6. Public code for BoS, IIsy and NetBeacon on Tofino-1.
  7. Whether threshold sharing under a key-width budget is published.
  8. Locality on real traces (MAWI or CAIDA).

**Research scientist:**
- **Recommends A with D as its defense.** A's core evidence does not depend on the missing training
  file or on accuracy claims: the hardware timing gap, the control-plane lag, and flood-driven skew
  (which becomes the attacker's lever).
- **Biggest shared risk: external validity of locality.**
  - **Gate E0, run before anything else:** W90/W99, benign W90 and LRU/dLFU/Belady at K=8 on
    NF-ToN-IoT-v3 (27.5M flows, 61% benign), NF-UNSW-v3 (94.6% benign) and UGR'16, each with its own tree.
  - **Pre-registered falsifier:** benign W90 above 25% of the leaves on two or more external datasets
    rejects locality.
- **Datasets:**
  - suitable: NF-v3 family, UGR'16, MAWI, CAIDA, CESNET-TLS/QUIC22, LANL 2017;
  - unsuitable: CIC-DDoS2019, IoT-23 (attack-dominated);
  - CIC-IDS2017/2018: only with corrected labels.
- **A's design:**
  - Hypotheses: HA1 miss-flood amplification of at least 5× at 10% attack rate; HA2 knowledgeable
    pollution beats random; HA3 remote residency inference at AUC ≥ 0.9 within N probes.
  - Victim configuration fixed in advance, before any attack.
  - Defenses: TinyLFU admission, per-source quotas, partitioned or pinned cache, latency padding.
  - Statistics: 10 seeds, block bootstrap, Holm correction.
- **Re-runs needed:** everything on the official `train_test_network.csv`; the load sweep with runs of
  at least 10 minutes.

**P4 dataplane engineer (analysis only):**
- **No Tofino (TNA/T2NA) can add table entries from the data plane.**
- **All 394 leaves likely fit in one stage** (confirm by compiling at size 512), so K=8 is a choice.
- **The 12-stage use is probably an artifact** of the serialized `if (!fine.hit) coarse` chains. Merging
  them into one ternary table per feature gives a critical path of about 3 stages and frees 8–9 stages.
- **Controller-free residency:** pre-install every leaf and gate hits with a per-leaf `active[]` register
  that **Hulk's reply packets set** as they pass back through the switch. Lag drops from about 6 ms to
  about 130 µs, with no CPU in the path. An alternative is a hashed-fingerprint memo (4K–16K entries).
- **Install latency estimates:** C++ BF-RT about 20–200 µs per install; Python batching raises
  throughput, not latency.
- **Defenses:**
  - per-source meter on the query path;
  - per-leaf admission counter on the reply path (the digest then carries the leaf id);
  - randomized forwarding of hits to Hulk.

  All fit without new stages.
- **Timing equalization:** echoing every hit through Hulk is exact but costs the whole latency
  benefit. Recirculation delay is jittery. Queue pause needs Tofino-2 (API unchecked).
- **Direction B:** fits after the stage merge (64K flows × 8 features ≈ 2 stages).

**SDN networks expert:**
- **Honest deployment model:** a fast-path cache in front of an existing **slow-path IDS farm**
  (Zeek, Suricata, Snort), as in campus/enterprise IDS, ISP security and OT/ICS. Not line-rate
  verdicts; SpliDT (NSDI'26) owns that story.
- **Threat model:**
  - An on-path external sender times its own round trips (the main setting).
  - A co-resident tenant is the secondary setting.
  - The sender controls proto, packet and byte counts, duration and state, so flows can be aimed at chosen leaves.
- **Timing channel over distance:** probes needed n ≈ 2(zα+zβ)²σ²/Δ² with Δ≈130 µs.

  | Setting | Jitter σ | Probes per leaf |
  |---|---|---|
  | LAN | ~20 µs | single digits |
  | data center / metro | ~200 µs | ~60 |
  | WAN | ~2 ms | ~6,100 |

  **This probes-vs-jitter curve is a core deliverable.**
- **Most compelling attack:** miss amplification and cache pollution (availability degradation of the
  slow path), not the timing channel alone.
- **Defenses:**
  - count-min miss quotas per source;
  - reuse-gated admission (this is where C fuses in);
  - randomized promotion;
  - constant-time responses (a knob that trades away the latency win).
- **Recommendation: A + C, framed as a defense paper**, "Attacking and hardening the in-network inference
  cache". B is dropped (SpliDT shares state rather than losing it); D is a mechanism inside A.
- **Flag:** check 2026 NDSS/CCS/S&P for any attack on in-network ML caches. Also check "Data-Plane
  Security Applications in Adversarial Settings" (arXiv 2111.02268).

**Literature scout, security (Semantic Scholar + web; the arXiv MCP failed with HTTP 406):**
- **Closest prior work: Heracles (Nam, Lim, Zhou, Gu & Kang, NDSS 2026).** Timing side channels on real
  Tofino drive memory augmentation and contention between the data plane and the control plane, against
  Cerberus (S&P 2024); the defense is Shield. It targets DoS-mitigation memory, not an ML model: no leaves,
  no feature-space targeting, no class leakage, no miss-cost asymmetry.
- **Also verified:**
  - Sonchack et al., ACSAC'16 (DOI 10.1145/2991079.2991081), and Liu/Reiter/Sekar ICDCS'17: timing
    inference of rule presence;
  - LOFT (SecureComm'17), Tuple Space Explosion (CoNEXT'19), AVANT-GUARD, FloodGuard, SPHINX;
  - Wang/Mittal/Rexford, CCR 2022 (DOI 10.1145/3544912.3544914): limited memory and control-plane fallback as pitfalls;
  - TrEEStealer (2026): tree extraction through control-flow side channels in trusted execution environments;
  - evasion work on P4 classifiers (JNSM 2023/2025);
  - Poseidon (NDSS'20), Jaqen (USENIX Security'21);
  - TinyLFU.
- **Verdicts:**
  - (i) Miss flooding: **overlaps**. Open only as inference-specific amplification.
  - (ii) Pollution: **overlaps**. Open only as feature-space pollution that pushes benign classes onto the slow path.
  - (iii) Timing: **killed as a mechanism, open as a leakage target**, meaning class composition of
    co-located traffic and a model-extraction oracle.
- **Defensible gap:** residency is set by the feature-space distribution of traffic, so timing reveals the
  class composition of co-located traffic and crafted inputs push chosen benign classes onto the slow path.
  **No prior work analyzes an in-network model cache.**
- **Must read in full before committing:** Heracles, and Wang/Mittal/Rexford.

**Literature scout, in-network ML history 2019–2026 (Semantic Scholar; forward citations of Leo,
NetBeacon, IIsy and SpliDT):**
- **No system pages one tree's leaves by traffic popularity with an exact CPU fallback.**
- **Closest:**
  - CacheFlow (SOSR'16): rule caching with a software miss path; not ML, and its rules overlap so
    need splicing, which MVM's disjoint leaves avoid.
  - IIsy-hybrid (ToN'24), BoS (NSDI'24), Turbolearn (APNet'26): split work between switch and
    server by *confidence*; the resident part is static.
  - **Proteus (WWW'26, DOI 10.1145/3774904.3792381):** migrates subtrees at runtime, driven by
    accuracy and resources, not per-leaf traffic, and with no CPU miss path. **Must cite and contrast.**
  - LoFi (NetSoft'26) and approximate-key caching (INFOCOM'21) cache inference *results*, not model pieces.
  - Dryad (ICNP'23) resizes a tree when the resource budget changes.
- **Per-flow state** (NetBeacon, pForest, SpliDT, FlowLens, Flowrest, Jewel) is always bounded by a
  **fixed offline schedule**. None couples the tracked features to which model parts are resident, or
  budgets state that is lost for good because a flow's early packets were never counted.
- **Verdicts:**
  - MVM: **moderate** novelty ("CacheFlow for tree leaves plus IIsy's fallback"). Defensible angles:
    exactness from disjoint leaves, a hit-rate model tied to skew, and Tofino-1 feasibility.
  - Feature-state paging (B): **higher** novelty, less proven; SpliDT and NetBeacon are the baselines.
    (The reviewer and the SDN expert rejected B because the feature union over any working set is
    likely all 10 features. That is testable offline.)
- **Named open gap:** "robustness to adversarial churn … no paper evaluates this for in-switch ML."

## Round 1 synthesis (planner)
**Where the panel converges:**
- MVM as a caching system is not a paper, for two reasons: the premise is weak (all the leaves fit),
  and CacheFlow, IIsy and Proteus sit on either side of it.
- The live direction is **security of hybrid in-network inference, i.e. the fast-path/slow-path
  boundary**. The reviewer, the research scientist and the SDN expert all rank it first, and the
  history scout independently names adversarial churn as an unevaluated gap.
- **The mechanism is not novel** (Heracles, SDN timing attacks). **The target is** — model-structured
  residency and escalation.

**Unresolved questions for Round 2:**
1. **Scope.** MVM alone (weak reject), or several published hybrid designs (the reviewer's condition)?
   This changes the effort by months.
2. **Headline.** Availability (miss amplification and slow-path overload) or leakage (class
   composition of co-located traffic and model extraction)? The panel splits.
3. **Premise.** How to answer "all 394 leaves fit": frame by deployment (the fast path sits in
   front of a slow-path IDS farm, and confidence-routed hybrids escalate *by design*), not by TCAM size.
4. **Defense.** Is it a contribution, or a section?

**Where each lands:**
- Gate E0 (locality on external datasets) is needed only if MVM-style caching stays in scope.
- The P4 engineer's residency register (≈130 µs) is a defense or baseline mechanism.

## Round 2, PI proposal v1: "SlowLane: escalation-steering attacks and defenses for hybrid in-network inference"
- **Thesis.** Tiered in-network classifiers route between a fast tier on the switch and a
  slow/weaker tier using model-internal signals: confidence, residency, per-flow storage. A
  label-blind external attacker can reach and deplete this *shared escalation budget*. The result:
  - **fail-open**: the attacker's concurrent attack flows go undetected; or
  - **fail-closed**: benign co-tenants are degraded.

  This is the "escalation dilemma".
- **New prior-work threat surfaced:** DeepSloth (ICLR'21) and AESOP (arXiv 2605.10987) already
  force the expensive path in a single model. Separation from them rests on three things:
  - **cross-flow harm**, not self-slowdown;
  - a **label-free** attacker;
  - a **shared** budget.
- **Premise answer.** Confidence-routed systems escalate by design. MVM is conceded as the
  white-box dissection victim, with an all-resident control configuration.
- **Target class:** four triggers.
  1. low confidence (IIsy-hybrid, BoS, Turbolearn);
  2. residency miss (MVM);
  3. storage overflow to a weaker model (BoS per-packet tree; NetBeacon unverified);
  4. phase fallback (NetBeacon, unverified).
- **Inline vs mirrored escalation.** Checked per system. Only inline gives a data-path timing oracle.
- **Contributions:**
  - C1 systematization plus benign escalation and overload behaviour;
  - C2 label-free oracle plus steering (inline only);
  - **C3 (headline):** budget exhaustion causes fail-open detection or co-tenant collateral, on ≥3 systems;
  - C4 per-region + per-source escalation budget in the data plane, against an adaptive attacker.
- **Victims:** MVM + IIsy-hybrid + BoS + NetBeacon, all with public repos (SDE-version fit
  unverified). Needs ≥3/4 showing C3; otherwise re-scope to TDSC.
- **Hypotheses:**
  - H1 oracle AUC ≥ 0.9;
  - H2 steering needs 5× fewer queries than random;
  - H3 5× amplification at ρ = 0.10;
  - **H4 recall drops ≥ 20 pp at ρ ≤ 0.25;**
  - H5 collateral: macro-F1 −0.05 or p99 3×;
  - H6 ≥ 3/4 systems;
  - H7 defense within 5 pp at ≤ 1% benign denial, against 100 sources.
- **Kill criterion:** stop if any holds:
  - (a) H4 and H5 fail everywhere;
  - (b) H6 fails;
  - (c) two published systems will not reproduce within 6 weeks.
- **Predicted:** NDSS/USENIX Security borderline to weak accept (~25–35%); TDSC major revision then
  likely accept. Effort about 5–7 months.
- **Top risks:**
  - "DeepSloth on a switch";
  - reproduction and SDE-version fit;
  - mirrored rather than inline escalation;
  - overload-policy strawman;
  - two-host realism;
  - packet-level traffic needed.

## Round 2, reviewer on v1: **weak reject (~10–15%)**
- **M1. The separators fail.** Cross-flow, shared-budget, label-free IDS fail-open is already published:
  - Smith/Estan/Jha ACSAC'06: algorithmic-complexity attack on Snort; one packet every 3 s disables
    detection; defense = memoization;
  - Ptacek & Newsham 1998: passive IDS is inherently fail-open;
  - Papadogiannakis EuroSec'10 / ATC'12: overload as evasion; defense = randomized shedding;
  - Pigasus OSDI'20: fast/slow IDS that resets flows under overload;
  - FloodGuard: per-protocol queues;
  - AESOP: attacks shared pipelines with confidence thresholds.

  **Survives only:** amplification per attacker packet that comes from the model's decision geometry,
  beyond a naive flood, plus the fact that escalated traffic is by construction what the fast model gets wrong.
- **M2.** No naive-flood baseline B0. Out-of-distribution junk may already escalate at about 100%, which would make steering pointless.
- **M3. Our own W8 data refutes C3 on MVM.** K=0 answers 100% at 100k qps, and the CPU computes the
  tree in 30 ns. BoS claims IMIS handles 10 Mpps. The overload policy has to come from each victim's
  code, followed by a headroom sweep: find ρ* at the published provisioning.
- **M4.** H3 is configuration arithmetic: A = 1 + ρp/e, with BoS e ≤ 5% giving A ≤ 3. Redefine it as
  slow-tier work per attacker packet, normalized by B0.
- **M5.** The threat model is inconsistent: the oracle needs replies and so unspoofed sources, while
  exhaustion can be spoofed. Split it into T-oracle and T-exhaust.
- **M6.** ρ must be stated in the bottleneck's unit (flows/s) and in bytes. At 25% of bytes, a
  volumetric detector catches it.
- **S1.** The defense as specified is obvious (control-plane policing, FloodGuard, Papadogiannakis, memoization).
  It is novel only as **error-weighted admission** across regions, with a bound against an attacker who
  copies benign region proportions (fair share gives the attacker ρ/(1+ρ)).
- **S2. Eight required baselines:**
  1. naive flood B0;
  2. per-source limit;
  3. global cap with random admission;
  4. per-region round-robin;
  5. scaled-out slow tier with its cost;
  6. fail-closed policies;
  7. memoization;
  8. all-resident control.
- **S3/S4.**
  - One primary metric for H5.
  - H6 counts the 3 non-MVM systems only.
  - New kill criteria: steered harm < 2× B0; ρ* > 1 at published provisioning; mostly mirrored escalation.
- **Path to weak accept:**
  - model-geometry amplification normalized by B0, on 3 non-MVM systems at published provisioning;
  - overload policies taken from the victims' own code;
  - split threat model;
  - error-weighted admission that beats baselines 2–7;
  - the M1 prior-work block in related work;
  - the oracle demoted to a section.
- **Fallback if B0 comes close or ρ* > 1:** a defense and provisioning paper for ToN/TDSC,
  **"Admission control for the slow tier of cascaded in-network classifiers."**

## Round 2, artifact scout (code read from cloned repos)
- **IIsy hybrid.** The public artifact is a **Python simulation on Iris only**, with no P4. The
  confidence trigger is `confidence <= 0.95`. The overload policy is unspecified. The paper used
  SDE 9.2.0 and 9.6.0 on a BF6064X; its datasets are not in the repo. **It cannot be reproduced as a hardware victim.**
- **BoS: the only real inline slow tier.**
  - **Triggers:** ambiguous-packet count ≥ T_esc (tuned so that ≤ 5% of flows escalate), and
    flow-storage collision. A code-only global collision budget sends colliders to the server model
    (IMIS) up to a threshold, then to the per-packet tree.
  - **Pre-analysis packets:** the first 7 packets of a flow have no verdict. The paper itself warns
    about "very short flows".
  - **Inline:** the escalated flow is diverted to the IMIS server, where packets wait in queue for the verdict.
  - **IMIS saturation policy:** unspecified.
  - **Toolchain:** Tofino-1 Wedge 100BF, SDE 9.7.0, 2 pipes with recirculation, and a hand-edited
    .conf. IMIS needs DPDK and an A100 GPU.
  - **No adversarial evaluation.**
- **NetBeacon: no slow ML tier.**
  - When per-flow storage collides, or a flow is predicted short, it falls back to the on-switch
    per-packet model. The verdict is only logged to the TTL field.
  - Its paper *discusses*, without measuring, resource exhaustion ("will not fully break down … falls
    back to per-packet features") and low-rate long flows.
- **Turbolearn and Proteus:** no public code (Proteus likely targets Tofino-2).
- **Consequence:** the victim set with a server slow tier is **BoS only**, plus MVM. "≥3 non-MVM
  systems with a server slow tier" is infeasible. The common, reproducible degradation path is instead
  **fallback to a weaker model on flow-state exhaustion**, which BoS and NetBeacon share and which
  NetBeacon's authors *claim* is benign without measuring it.

## Round 2, PI proposal v2: "Who Gets the Good Model? Degradation attacks and rent-aware admission for stateful in-network classifiers"
- **Status.** Accepts reviewer M1–M6 and S1–S4, and the artifact findings, without rebuttal. It is
  option (a) + (b), ordered by offline gates.
- **Thesis.** The accurate path, i.e. a per-flow storage slot or a server slot, is rationed by hash
  collision and first-come order. Everything else silently drops to a weaker per-packet model.
  - A spoofing attacker spending few bytes holds the slots.
  - Benign co-tenants are pushed onto the weak model, and the attacker's concurrent attack flows are
    judged by the model that misses them.
  - The harm is **silent accuracy loss**: no drops, no latency change.
  - NetBeacon's authors claim this fallback is harmless and never measured it. We test the claim.
- **Not claimed:** state exhaustion as new, IDS fail-open, a label-free separator, an oracle
  contribution, anything about slow-tier throughput.
- **Threat models:**
  - **T-exhaust** (spoofed; K1 = public P4 defaults; ρ in new flows/s, slot-seconds and bytes; target ≤ 1% of benign bytes);
  - **T-evade** (concurrent real attack flows);
  - T-oracle as one section only.
- **Victims:**
  - **NetBeacon** on hardware;
  - **BoS on-switch part** on hardware, with IMIS replaced by a CPU stand-in on Hulk (labelled);
  - MVM as control;
  - Flowrest (public repo) in emulation, or on hardware if it ports.
  - Per-artifact policy emulators, validated packet-for-packet against hardware.
  - **This is below the reviewer's 3-system hardware bar, stated openly.**
- **Contributions:**
  - C1 the downgrade gap between full and fallback models;
  - C2 degradation attacks: benign flows downgraded per attacker packet ÷ B0, and ρ* at published provisioning on MAWI/CAIDA concurrency;
  - C3 concurrent attack-flow evasion;
  - C4 **rent-aware, value-weighted admission.**
- **The C4 defense.**
  - An incumbent keeps its slot only if its packets per slot-second exceed the newcomer's prior and it has no confident verdict yet.
  - Confident verdicts move to the memo table.
  - Value = predicted accuracy gain of the full model over the fallback, from first-packet features.
  - Rent forces the attacker to pay about the benign byte rate per displaced flow, which is what beats fair share.
  - Stateful-ALU fit next to NetBeacon's 12 stages is unverified.
- **Baselines:** the 8, adapted to storage.
- **Hypotheses:**
  - H1 gap ≥ 0.10 attack macro-recall;
  - H2 ≥ 5× B0;
  - H3 ρ* ≤ 1% of benign bytes;
  - H4 recall drop ≥ 20 pp;
  - H5 defense recovers ≥ 50% of the loss, beats baselines 2–7 by ≥ 5 pp, costs ≤ 1 pp with no attack;
  - H6 holds on both hardware victims.
- **Kill criteria:**
  - (d) < 2× B0 → pivot to (b), a journal;
  - (e) ρ* > 1 → pivot to (b);
  - (f′) fallback harmless → negative-result note plus (b);
  - (g) ports fail within 4 weeks → emulation only, journal.
- **Offline gates first (2–3 weeks, no switch):**
  - G0 extract the artifacts' parameters;
  - **G1 the full-vs-fallback gap, which decides (a) vs (b);**
  - G2 policy emulator plus MAWI/CAIDA concurrency, giving amplification and ρ*;
  - G3 offline evasion;
  - G4 defense in simulation.
- **Venue (PI estimate):**
  - USENIX Security / NDSS about 15–20%;
  - **ACSAC about 30–40% (primary);**
  - TDSC about 50–60% after major revision.

  Effort about 5 months.

## Round 2, reviewer on v2: **not converged yet**

| Venue | Score |
|---|---|
| ACSAC | weak reject (~20–25%) |
| TDSC | major revision (~40–50%) |
| NDSS/USENIX Security | reject (<10%) |

- **M1. SketchFeature (Kim et al., NDSS 2025) is unaddressed.** Data-plane feature extractors, constrained
  by hardware, open attack surfaces that let adversaries evade in-network IDSs; the defense is an
  "All-flow" sketch extractor. The full text was not verified. Also the sketch-pollution preprint arXiv 2503.11777.
- **M2. Adversarial probabilistic data structures:** Clayton/Patton/Shrimpton CCS'19; Markelon CCS'23
  (Count-Keeper). **A keyed-hash baseline is required**: if salting fixes the problem, the paper is a
  configuration advisory.
- **M3. "Sensitivity attacks":** Kang/Xing/Chen CSET'19 and CASTAN SIGCOMM'18. The surviving delta is harm
  measured as *model accuracy on third-party flows*.
- **M4. C4 vs keep-the-heavy eviction** (HashPipe, Elastic Sketch Ostracism, HeavyKeeper, PRECISION, TinyLFU). Needs:
  - an ablation of the value term;
  - a stated lemma bounding the cost to a rate-mimicking adaptive attacker;
  - a **compiled** Tofino-1 fit next to NetBeacon.
- **M5. H1 must be measured on the downgraded population**, at published provisioning, with a numeric "harmless" threshold:
  - benign flows downgraded under attack;
  - the attacker's own attack classes;
  - per class.

  Also report the benign-only collision rate at MAWI/CAIDA concurrency.
- **M6.** Spoofing + K1 makes exhaustion obvious. State ρ in new flows/s against the reclamation rate,
  show that volumetric and new-flow detectors stay silent at ρ*, and add keyed-hash and
  spoofing-filtered variants.
- **S1–S6:**
  - 2 hardware victims + validated emulator is acceptable at ACSAC/TDSC;
  - generality via an emulator sweep;
  - pre-register B0 in one unit;
  - one primary metric for H5;
  - the BoS 7-packet pre-analysis window: scope it out or include it;
  - state deployment realism.
- **Converged at ACSAC if items 1–6 are adopted**, *provided SketchFeature does not already measure
  fallback accuracy loss on NetBeacon*. Otherwise converge as a **TDSC defense and provisioning paper**:
  "Admission control for stateful in-network classifiers". **The decisive step is reading SketchFeature in full.**

