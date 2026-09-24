# Literature check: two-choice (d-left) admission as a defence, 2026-09-24

Source: literature-reviewer agent. **Tooling caveat:** the Semantic Scholar and arXiv tools were not available to it; it used web search and page fetches. Semantic Scholar returned HTTP 429 and ACM pages returned 403; the NetBeacon PDF was not text-extractable. Items marked *snippet* come from search-result text, not from reading the paper. The search was shallow; absence of a hit is not proof of absence.

| Paper | Venue, year | Id | Relevance | Read? |
|---|---|---|---|---|
| NetBeacon (Zhou et al.) | USENIX Security 2023 | ACM 10.5555/3620237.3620584 | A colliding new flow takes an occupied slot only if the incumbent is determined or finished; otherwise it falls back | snippet |
| Heracles / Shield (Nam et al.) | NDSS 2026 | none found | Memory contention in data-plane DoS defences; no multi-choice or classifier content | abstract |
| SketchFeature (Kim et al.) | NDSS 2025 | none found | Sketch-based per-flow features; no adversarial-occupancy analysis seen | snippet |
| HashFlow | arXiv | 1812.01846 | Multi-hash collision resolution for flow records (multi-choice, not adversarial) | abstract snippet |
| HashPipe (Sivaraman et al.) | SOSR 2017 | 10.1145/3050220.3063772 | Multi-stage hash tables with eviction of lighter flows | snippet |
| TurboFlow (Sonchack et al.) | EuroSys 2018 | 10.1145/3190508.3190558 | Collision evicts the incumbent record | snippet |
| LOFT attack | IEEE/ACM ToN 2022 | 10.1109/TNET.2022.3225211 | Low-rate flow-table overflow in SDN switches (closest attack analogue) | snippet |
| Secure Keyed Hashing on Programmable Switches (Yoo, Chen) | SPIN at SIGCOMM 2021 | 10.1145/3472873.3472881 | Weak switch hashes lose randomness under adversaries (precedent for keyed hashing) | snippet |
| Data-plane security applications in adversarial settings | SIGCOMM CCR 2022 | 10.1145/3544912.3544914 | **Not read (403). Read before submission.** | no |
| Yeo, Cuckoo Hashing in Cryptography | CRYPTO 2023 | arXiv 2306.11220 | Standard bounds assume inputs independent of the hashes; robust variants need more hash functions | abstract |

**Verdict: overlaps, not a kill.** Multi-choice hashing is established for flow tables. No paper found proposes or evaluates it against slot-holding downgrade of a stateful classifier, and none measures classifier accuracy loss under contested state.

**Safe claim wording.** "Splitting NetBeacon's flow-state capacity into two independently hashed half-size tables reduces the fraction of benign flows refused a slot under random-fill slot-holding, from about o to about o² at occupancy o. In our emulator this reduces classifier downgrade accordingly. The gain is limited to attackers who cannot target slots: with public hashes the cost of denying a specific victim rises by only a constant factor, and a keyed hash removes targeting only until the attacker can probe the mapping. Multi-choice hashing is an established flow-table technique; our contribution is the evaluation of its effect on classifier accuracy under slot-holding."

Do not claim novelty of the mechanism, general defence, or security against adaptive attackers.
