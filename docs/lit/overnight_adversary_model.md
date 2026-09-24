# Adversary model for two-choice admission (D4/D5), 2026-09-24

Source: sdn-networks-expert agent. All numbers are model-derived, not measured. Assumptions: Poisson holder arrivals, first come first served, protected incumbents, benign occupancy b, holder load f per slot.

- One table: refusal R1 = 1 − (1−b)e^(−f). Two tables of N/2, oblivious holders: R4a = R1². Holders that use both candidates: x = tanh(f + atanh b), R4b = x².
- At b = 0.2: f = 0.1, 0.25, 0.5 give R1 = 0.276, 0.377, 0.515; R4a = 0.076, 0.142, 0.265; R4b = 0.086, 0.180, 0.367.
- Attacker cost multiple to restore the one-table refusal rate: about f^(−1/2) at small f (3.2 to 5.2× at f = 0.1; 1.4 to 2.1× at f = 0.5). The advantage is largest against small attacks and shrinks as f grows.
- **Targeted attackers.** Known hashes: 2 holders per victim instead of 1 (a constant factor; finding matching tuples for a linear hash is offline linear algebra). Secret second hash: blind fill of table B needs about 1.15 N holders for a 90% chance; learning a small-keyspace polynomial by refusal probes takes about 20 to 35 probes after a 50% fill; a full GF(2) matrix needs about 1.6 thousand probes at least, and about 1.5 million by the collision route. Use a keyed non-linear or rotating second hash, not a polynomial choice alone.
- **Adaptive holders.** Mimicking benign long flows shortens the hold (faster flows reach 2,048 packets sooner); the stealthy strategy is the 3.73 packets/s floor, only 7% below 4. Against a lease rule, the attacker rotates tuples at handover cost of about 268 ms per rotation.
- **Defender-aware attacker.** Concentrating on one table lowers refusal (R = 0.141 against 0.265 at b = 0.2, f = 0.5), so an even split is the attacker's best response for equal tables; unequal table sizes let the attacker load the small table (about +13% relative refusal in the worked case), so equal tables are the defender's optimum under this model.
- Caveats: independence of slots and no finite-N variance; two-choice insertion would also lower benign occupancy (not modelled).
