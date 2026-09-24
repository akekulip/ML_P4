# D4c on Tofino-1: offline compile study

Compile-only study with the **local** SDE 9.13.1 compiler (`p4c 9.13.1`, `bf-p4c --target tofino --arch tna`) by the p4-dataplane-engineer agent; the key numbers below were re-read from its saved compile logs. **Nothing was run on the switch, a lab host, `bf_switchd` or the model.** The switch runs 9.13.2, so these results carry over only by inference from the same 9.13 line. Sources and diff: `p4/dgrade_d4c/`. Emulator behaviour to be matched: `src/dgrade/netbeacon_sim.py` (`two_way`, policy `unclaimed_first`).

## Result

| build | compiles? | stages | critical path | stateful ALUs | SRAM | map RAM | TCAM | hash bits | hash-dist units | gateways | PHV |
|---|---|---|---|---|---|---|---|---|---|---|---|
| unmodified NetBeacon | yes (0 errors, 15 warnings) | **12** | 10 | 13 | 186 | 150 | 90 | 272 | 12 | 35 | 66 containers (29.5%) |
| **D4c, variant P-b** | **yes** (0 errors, 15 warnings) | **12** | 11 | 14 | 191 | 155 | 90 | 330 | 15 | 44 | 63 containers (28.1%) |
| NetBeacon with 131,072 slots, stage pins kept | **no**: `tofino supports up to 12 stages, using 15` | 15 | 10 | 13 | | | | | | | |
| same, stage pins removed | **no**: `... using 16` | 16 | 10 | 13 | | | | | | | |

P-b costs **+1 stateful ALU, +5 SRAM blocks, +5 map RAMs, +58 hash bits, +3 hash-distribution units, +9 gateways** over the baseline and adds one stage of dependency depth (critical path 10 to 11), still inside 12 stages.

**G9-A (2026-09-24): confirmed on the switch host's real SDE 9.13.2 toolchain.** Compiled in a separate build directory (`~/ml_p4/build_new/d4c_g9a`), no `bf_switchd` restart, no change to the running program (MVM was, and remains, running throughout). `rc=0`, `0 errors, 15 warnings generated.` — **every number below is identical to the 9.13.1 compile**: 12 stages, critical path 11, 14 stateful ALUs, 191 SRAM, 155 map RAM, 90 TCAM, 330 hash bits, 15 hash-distribution units, 44 gateways, 61 VLIW instructions, 91 logical tables. The full resource log is saved at `docs/g9a_9.13.2_mau.resources.log`. This settles the "the 9.13.1 result may not carry over" caveat for D4c: it does, exactly, on this switch's actual toolchain. Stage 1 becomes completely full (4 of 4 stateful ALUs, 44 of 48 stateful RAMs). The doubled-table baseline **does not fit**: a 131,072 x 32-bit register needs 33 of a stage's 48 map RAMs, so NetBeacon's six 32-bit registers can no longer share stages (memory limit, not dependency depth). Doubling the table is therefore not an available alternative on this hardware, and the largest direct-mapped NetBeacon that compiled is the original 65,536 slots (non-power-of-two sizes were not tested). Resource-matched comparison: P-b keeps the same slot count as the baseline (2 x 32,768 identity slots, 65,536 feature slots).

## What P-b implements

- **Hash B:** a custom CRC (`CRCPolynomial` with `HashAlgorithm_t.CUSTOM`, coefficient 0x09c8be85 = the emulator's `polyirr` polynomial for `hash2_seed` 7919), marked `@symmetric`; bfrt exposes `hash_b.algorithm`, so the key can be changed at runtime (untested).
- **Per way:** one pair register (hi = 32-bit tag, lo = last-seen time) plus a 16-bit result register (bit 8 = claimed). One stateful ALU per way does the tag compare, the last-seen refresh for the owner and the idle test in one access (compiled `equ`, `alu_a`, `lss.u`, output predicate; `build_pb_final/pipe/switch.bfa` lines 1373 to 1378 and 1580 to 1585). The decision is a gateway chain in stage 2; **no two timestamps are compared**. The D4c rule "never-claimed candidate first, else A" uses the claimed bit, not a tag-zero check (the probe's outputs were already used).
- **Features:** the chosen slot {way, index} indexes the eleven unchanged 65,536-entry feature registers. The way bit rides in `hdr.ethernet.dst_addr[0]` on the recirculated pass; pass 2 writes only the tag, so last-seen is not refreshed at takeover (as in NetBeacon).

## Compile errors met and how each was fixed

1. A stateful ALU has one output source (predicate) and cannot return different constants per branch: return `this.predicate(own, recent)`.
2. A boolean local built from a subtraction compare is not allowed inside a RegisterAction: write both conditions inline.
3. One action can drive only one stateful ALU (meter-address hardware overlap): split the claim into two actions.
4. Two 32-bit hash computations merged into one action exceeded the 32-bit immediate pathway: one explicit action per hash.
5. Copying `flow_hash[14:0]` into a metadata index cost a whole stage: index the ALUs with the hash slice directly.
6. Init and Update tables in separate `if` statements could not be shown mutually exclusive: one if/else chain (critical path 11, compile succeeds).

## What the compiled P4 does not reproduce from the emulator

1. **The "symmetric" hash is an XOR fold, not a sorted tuple** (compiled expression `crc_rev(..., 104, {40: src_addr, 40: dst_addr})` and `{0: protocol, 8: src_port, 8: dst_port}`, baseline `switch.bfa:896-906`, P-b `switch.bfa:914-970`): both hashes see only (src XOR dst, sport XOR dport, proto). Inferred from the compiled expression; the bit order of the 104-bit message is unverified. **Effect on the traces (measured here):** 242 of 82,922 PeerRush tuples (0.29%) and 78 of 1,153,218 (0.01%) and 99 of 1,409,439 (0.01%) tuples of the two MAWI days share an XOR-fold key with another tuple, so benign aliasing is negligible and the emulator's benign numbers stand. **Caution for the attack side:** a spoofing sender can choose a tuple with the same fold as a victim; it would then share the victim's slot in every hash *and* the same tag, under any polynomial, so it would be treated as the same flow (state corruption) rather than as a collision. A keyed second polynomial therefore protects only the displacement attack, which needs the same index bits with a different tag, not this aliasing.
2. **Recirculation delay:** tag and result are written in pass 2, so packets arriving before the write lands see the old state (Init runs again; a second newcomer can take the same slot; the last pass-2 write wins). The emulator assumes instantaneous recirculation.
3. **A flow can own both ways** if slot state changes between its pass 1 and pass 2; the P4 then refreshes last-seen in both, pinning way B. The emulator cannot reach this state.
4. **Tag width:** both ways store the full 32-bit hash, so way A distinguishes flows by 17 bits (15 are the index) and way B by 32; the emulator compares 32-bit identities.
5. **Clock:** the P4 keeps NetBeacon's wrapped 12-bit clock and matches the emulator only with `wrap_window=True`; emulator arms with `wrap_window=False` (D1 clock, D4d1, D4age) are not what this P4 does.
6. **Predicate encoding** (one-hot 1, 2, 4, 8 in the gateways) and the unsigned idle test (`lss.u`) are assumptions to check on the model; only four constants in `headers.p4` would change.
7. Minor: the way bit is left in the output destination MAC; the P4 (like the baseline) writes every phase result in pass 2 while the emulator writes the result register only at phase 2048.

## What this does and does not establish

Established (offline, one compiler version): D4c (variant P-b) fits within NetBeacon's 12 stages at the stated extra cost, and a doubled-table alternative does not fit. Not established: behaviour on the 9.13.2 toolchain, on the software model or on the chip; the recirculation hazards; the runtime rotation of hash B. The compile on the switch host in a separate build directory with SDE 9.13.2, and the software-model diff, remain owed and need approval (`docs/sde_validation_request.md`).
