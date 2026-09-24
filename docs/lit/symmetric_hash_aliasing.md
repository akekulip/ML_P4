# XOR-fold identity aliasing: a separate thread, not part of the D4 evaluation

Kept explicitly out of the D4/D4c claims (`docs/REPORT.md`) per Philip's direction: this is a different attack class (identity aliasing, not state displacement) and deserves its own track if it turns out to matter.

## What was found

The offline compile of D4c (`docs/results_d4c_compile.md`) showed that Tofino-1's `@symmetric` hash annotation compiles to a message in which the two addresses are XORed into one lane and the two ports into another before the CRC. Two distinct real 5-tuples with equal `src⊕dst`, `sport⊕dport` and `proto` therefore produce the **identical 32-bit hash**, under any CRC polynomial. Because NetBeacon (and D4c) use this hash both as the table index and as the stored identity tag, such a pair does not merely collide on a slot — the switch cannot tell the two flows apart at all. That is qualitatively different from D4's subject, which is contention between distinguishable identities for a shared slot.

## Literature check (verified by a literature-reviewer agent, sources actually opened)

- **Established, for the general XOR-fold transform:** Linux documents its "Symmetric-XOR" RSS hash input transform as XORing source/destination address and port before hashing, and warns: *"this XORing reduces the input set entropy and could be exploited to reduce the RSS queue spread"* (`include/uapi/linux/ethtool.h`; the same wording appears in `Documentation/networking/scaling.rst` and the `ethtool(8)` man page). The stated harm is entropy loss and queue-spread reduction, not identity collision.
- **Established, for XOR-structured hash tables generally:** Crosby and Wallach (USENIX Security 2003, pp. 33, 36) showed that hash tables whose function is a direct XOR of their inputs (their examples: the Linux protocol stack and Bro's port-scan table) admit collisions computable directly from the hash's algebraic structure — "collisions may be directly computed from the algebraic structure of the hash function."
- **Not found:** any published statement of this consequence for in-network ML classifiers, for stateful flow-tracking switches, or for Tofino's `@symmetric` specifically. NetBeacon's own paper stores the full 5-tuple alongside the hash index precisely to detect collisions (its collision check is therefore exact and unaffected by this issue); the vulnerability here is specific to a design, like the compiled D4c program, that uses the same hash as both index and tag.
- **Not established (own inference from the compile, not from any public Tofino documentation):** the exact bit layout of the 104-bit hash message; whether `@symmetric` is documented anywhere by Intel/Barefoot as an XOR pre-fold.

Safest wording: "Linux documents a symmetric-XOR RSS transform with an entropy-loss warning; XOR-structured hash tables are known (Crosby and Wallach 2003) to admit algebraically-computable collisions; we found no published treatment of this specific consequence — index-and-tag identity aliasing — for in-network ML classifiers or Tofino's `@symmetric`."

## GA-1: falsification test (run; result below)

Pre-registered in `docs/preregistration.md` (GA entry) before running. Method: for the 20 largest long flows (more than 50 packets) on PeerRush and each MAWI day, construct one alias tuple per victim with an equal XOR fold — `alias_src = src⊕k1`, `alias_dst = dst⊕k1`, `alias_sport = sport⊕k2`, `alias_dport = dport⊕k2`, protocol unchanged (any k1, k2 ≠ 0 preserves the fold, since `(a⊕k)⊕(b⊕k) = a⊕b`) — merge the alias's packets (one per 250 ms, starting at the victim's midpoint) into the victim's stream, and replay through `TofinoSim` (fold hash on) via `scripts/ga_alias_check.py`.

**Result (`docs/results_ga_alias.md`, 60 victims across the three traces): FALSIFIED.** All 60 aliases were confirmed to share the victim's 32-bit tag and were admitted as owner of the victim's slot (the definitional check). **Zero of 60 victim verdicts changed** with the alias present, at an alias rate of 4 packets/s starting mid-flow.

## Reading

At this packet rate, injection point and duration, on these three traces, the identity alias is a confirmed hash property but not shown to cause a classification error. This does not rule out the effect at a different rate, a longer injection, multiple simultaneous aliases per victim, or an alias timed to coincide with a phase boundary (2, 4, 8, 32, 256, 512 or 2048 packets) rather than an arbitrary midpoint — none of which were tested. Per the pre-registered falsifier, the honest conclusion is: **confirmed as a hash property, not (yet) shown to be a security-relevant effect.** No further work on this thread is planned unless a specific reason emerges to test a different rate or injection timing.

## Not claimed

Attack feasibility (how a real sender would discover or reach an alias tuple; the construction above assumes the fold structure, which is only known from an offline compile of one candidate P4 program), hardware behaviour (nothing here ran on the switch or the model), or any claim about D4c (unaffected by this thread's outcome either way).
